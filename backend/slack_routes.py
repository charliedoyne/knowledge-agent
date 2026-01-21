"""Slack integration routes for the Knowledge Agent."""

import hashlib
import hmac
import os
import time

from fastapi import APIRouter, HTTPException, Request
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

router = APIRouter(prefix="/api/slack", tags=["slack"])

# Slack credentials from environment
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")
SLACK_SIGNING_SECRET = os.environ.get("SLACK_SIGNING_SECRET")


def verify_slack_signature(request_body: bytes, timestamp: str, signature: str) -> bool:
    """Verify that the request came from Slack."""
    if not SLACK_SIGNING_SECRET:
        return False

    # Check timestamp is recent (within 5 minutes)
    if abs(time.time() - int(timestamp)) > 60 * 5:
        return False

    # Compute expected signature
    sig_basestring = f"v0:{timestamp}:{request_body.decode('utf-8')}"
    expected_sig = (
        "v0="
        + hmac.new(
            SLACK_SIGNING_SECRET.encode(), sig_basestring.encode(), hashlib.sha256
        ).hexdigest()
    )

    return hmac.compare_digest(expected_sig, signature)


async def run_slack_agent(message: str, notes: dict) -> str:
    """Run the Slack agent and return the response."""
    # Configure ADK to use Vertex AI
    os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "TRUE"

    project_id = os.environ.get("GCP_PROJECT_ID") or os.environ.get(
        "GOOGLE_CLOUD_PROJECT"
    )
    location = os.environ.get(
        "GCP_REGION", os.environ.get("GOOGLE_CLOUD_LOCATION", "europe-west2")
    )

    if project_id:
        os.environ["GOOGLE_CLOUD_PROJECT"] = project_id
    if location:
        os.environ["GOOGLE_CLOUD_LOCATION"] = location

    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.genai import types

    from agent.slack_agent import slack_agent

    APP_NAME = "knowledge_slack_agent"
    USER_ID = "slack_user"
    SESSION_ID = f"slack_session_{hash(message) % 10000}"

    # Create session service and session with notes in state
    session_service = InMemorySessionService()
    await session_service.create_session(
        app_name=APP_NAME,
        user_id=USER_ID,
        session_id=SESSION_ID,
        state={"notes": notes},
    )

    # Create runner
    runner = Runner(
        agent=slack_agent,
        app_name=APP_NAME,
        session_service=session_service,
    )

    # Run agent and collect response
    new_message = types.Content(role="user", parts=[types.Part(text=message)])

    response_text = ""
    async for event in runner.run_async(
        user_id=USER_ID,
        session_id=SESSION_ID,
        new_message=new_message,
    ):
        if hasattr(event, "content") and event.content:
            for part in event.content.parts:
                if hasattr(part, "text") and part.text:
                    response_text += part.text

    return response_text


@router.post("/events")
async def slack_events(request: Request):
    """Handle Slack events (mentions, messages)."""
    # Get raw body for signature verification
    body = await request.body()
    data = await request.json()

    # Verify request is from Slack (skip in local dev if no secret)
    if SLACK_SIGNING_SECRET:
        timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
        signature = request.headers.get("X-Slack-Signature", "")

        if not verify_slack_signature(body, timestamp, signature):
            raise HTTPException(status_code=401, detail="Invalid signature")

    # Handle URL verification challenge
    if data.get("type") == "url_verification":
        return {"challenge": data.get("challenge")}

    # Handle events
    event = data.get("event", {})
    event_type = event.get("type")

    if event_type == "app_mention":
        # Someone mentioned the bot
        await handle_mention(event, data)
        return {"ok": True}

    if event_type == "message" and event.get("channel_type") == "im":
        # Direct message to the bot
        # Skip bot's own messages
        if event.get("bot_id"):
            return {"ok": True}
        await handle_mention(event, data)
        return {"ok": True}

    return {"ok": True}


async def handle_mention(event: dict, data: dict):
    """Handle when the bot is mentioned or DM'd."""
    if not SLACK_BOT_TOKEN:
        print("SLACK_BOT_TOKEN not configured")
        return

    client = WebClient(token=SLACK_BOT_TOKEN)
    channel = event.get("channel")
    thread_ts = event.get("thread_ts") or event.get("ts")
    user_message = event.get("text", "")

    # Remove the bot mention from the message
    # Format is usually "<@BOTID> message"
    import re

    user_message = re.sub(r"<@[A-Z0-9]+>\s*", "", user_message).strip()

    if not user_message:
        user_message = "What can you help me with?"

    try:
        # Send typing indicator
        # Note: Slack doesn't have a typing indicator API for bots,
        # so we'll just respond as quickly as possible

        # Import notes cache from main module
        from backend.main import _notes_cache

        # Run the agent
        response = await run_slack_agent(user_message, _notes_cache)

        if not response:
            response = "I couldn't generate a response. Please try again."

        # Send response in thread
        client.chat_postMessage(channel=channel, thread_ts=thread_ts, text=response)

    except SlackApiError as e:
        print(f"Slack API error: {e.response['error']}")
    except Exception as e:
        print(f"Error handling mention: {e}")
        try:
            client.chat_postMessage(
                channel=channel,
                thread_ts=thread_ts,
                text=f"Sorry, I encountered an error: {str(e)[:100]}",
            )
        except Exception:
            pass


@router.get("/health")
async def slack_health():
    """Health check for Slack integration."""
    return {
        "status": "ok",
        "bot_token_configured": bool(SLACK_BOT_TOKEN),
        "signing_secret_configured": bool(SLACK_SIGNING_SECRET),
    }
