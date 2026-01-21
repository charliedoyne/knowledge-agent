"""FastAPI backend for Knowledge Sharing Agent."""

import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request

# Load .env file from project root
load_dotenv(Path(__file__).parent.parent / ".env")
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

app = FastAPI(title="Knowledge Agent API")

# Import and include Slack routes
from backend.slack_routes import router as slack_router

app.include_router(slack_router)

# CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    """Chat request model."""

    message: str


class Note(BaseModel):
    """Note model."""

    path: str
    title: str
    topic: str
    content: str


class ContributeRequest(BaseModel):
    """Request to contribute a note change."""

    path: str
    title: str
    content: str
    is_new: bool = False


class FileChange(BaseModel):
    """A single file change in a batch."""

    path: str
    title: str
    content: str
    is_new: bool = False


class ContributeBatchRequest(BaseModel):
    """Request to contribute multiple note changes in one PR."""

    changes: list[FileChange]
    pr_title: str = "Knowledge base updates"


class SubmittedPR(BaseModel):
    """Tracked submitted PR."""

    pr_number: int
    pr_url: str
    branch: str
    user_email: str
    files: list[str]
    status: str = "open"
    submitted_at: str
    merged_at: Optional[str] = None
    closed_at: Optional[str] = None


# ============================================================================
# Knowledge Base Cache (fetched from GitHub)
# ============================================================================

_notes_cache: dict[str, dict] = {}
_cache_timestamp: float = 0
_CACHE_TTL = 300  # 5 minutes

# PR tracking (in-memory, could be persisted to file/db)
_submitted_prs: dict[int, dict] = {}


async def refresh_notes_cache(force: bool = False) -> dict[str, dict]:
    """Refresh notes cache from GitHub if stale or forced."""
    global _notes_cache, _cache_timestamp

    # Check if cache is still valid
    if not force and _notes_cache and (time.time() - _cache_timestamp) < _CACHE_TTL:
        return _notes_cache

    repo_name = os.environ.get("KNOWLEDGE_REPO")
    if not repo_name:
        print("KNOWLEDGE_REPO not set, using empty knowledge base")
        return {}

    try:
        from backend.github_client import fetch_knowledge_base

        branch = os.environ.get("KNOWLEDGE_BRANCH")
        print(f"Fetching knowledge base from {repo_name} (branch: {branch or 'default'})...")

        _notes_cache = fetch_knowledge_base(repo_name, branch)
        _cache_timestamp = time.time()

        print(f"Loaded {len(_notes_cache)} notes from GitHub")
        return _notes_cache

    except Exception as e:
        print(f"Failed to fetch from GitHub: {e}")
        # Return existing cache if available
        if _notes_cache:
            print("Using stale cache")
            return _notes_cache
        return {}


@app.on_event("startup")
async def startup():
    """Load notes on startup from GitHub."""
    await refresh_notes_cache(force=True)


@app.get("/api/notes")
async def get_notes():
    """Get all knowledge notes."""
    notes = await refresh_notes_cache()
    notes_list = [
        Note(
            path=data["path"],
            title=data["title"],
            topic=data["topic"],
            content=data["content"],
        )
        for data in notes.values()
    ]
    return {"notes": notes_list}


@app.get("/api/notes/{path:path}")
async def get_note(path: str):
    """Get a specific note by path."""
    notes = await refresh_notes_cache()
    if path not in notes:
        raise HTTPException(status_code=404, detail="Note not found")

    data = notes[path]
    return Note(
        path=data["path"],
        title=data["title"],
        topic=data["topic"],
        content=data["content"],
    )


@app.post("/api/notes/refresh")
async def refresh_notes():
    """Force refresh notes from GitHub."""
    notes = await refresh_notes_cache(force=True)
    return {"message": f"Refreshed {len(notes)} notes from GitHub"}


async def run_local_agent(message: str, notes: dict):
    """Run the agent locally using ADK Runner with Vertex AI."""
    # Configure ADK to use Vertex AI (uses ADC, no API key needed)
    os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "TRUE"

    # Set project and location for Vertex AI
    project_id = os.environ.get("GCP_PROJECT_ID") or os.environ.get("GOOGLE_CLOUD_PROJECT")
    location = os.environ.get("GCP_REGION") or os.environ.get("GOOGLE_CLOUD_LOCATION", "europe-west2")

    if project_id:
        os.environ["GOOGLE_CLOUD_PROJECT"] = project_id
    if location:
        os.environ["GOOGLE_CLOUD_LOCATION"] = location

    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.genai import types

    # Import our agent
    from agent.agent import root_agent

    APP_NAME = "knowledge_agent"
    USER_ID = "local_user"
    SESSION_ID = "local_session"

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
        agent=root_agent,
        app_name=APP_NAME,
        session_service=session_service,
    )

    # Run agent and yield text chunks
    new_message = types.Content(role="user", parts=[types.Part(text=message)])

    # Track which surface events we've already emitted
    emitted_surfaces = set()

    async for event in runner.run_async(
        user_id=USER_ID,
        session_id=SESSION_ID,
        new_message=new_message,
    ):
        # Check for function calls (tool invocations)
        if hasattr(event, "content") and event.content:
            for part in event.content.parts:
                # Check for function call to surface_note
                if hasattr(part, "function_call") and part.function_call:
                    func_call = part.function_call
                    if func_call.name == "surface_note":
                        # Extract arguments and emit surface event
                        args = dict(func_call.args) if func_call.args else {}
                        path = args.get("path", "")

                        # Only emit once per path
                        if path and path not in emitted_surfaces:
                            emitted_surfaces.add(path)
                            note_data = notes.get(path, {})
                            surface_event = {
                                "type": "surface_note",
                                "path": path,
                                "title": note_data.get("title", path),
                                "highlight_text": args.get("highlight_text"),
                                "section_title": args.get("section_title"),
                            }
                            # Emit as a special marker the frontend will parse
                            yield f"<!--SURFACE:{json.dumps(surface_event)}-->\n"

                # Also yield any text content
                if hasattr(part, "text") and part.text:
                    yield part.text


async def run_agent_engine(message: str, notes: dict):
    """Run the agent via Agent Engine (production)."""
    import vertexai
    from vertexai import agent_engines

    project_id = os.environ.get("GCP_PROJECT_ID")
    agent_engine_id = os.environ.get("AGENT_ENGINE_ID")
    region = os.environ.get("GCP_REGION", "europe-west2")

    vertexai.init(project=project_id, location=region)

    resource_name = f"projects/{project_id}/locations/{region}/reasoningEngines/{agent_engine_id}"
    remote_app = agent_engines.get(resource_name=resource_name)

    # Create session with knowledge base
    session = remote_app.create_session(
        user_id="web-user",
        state={"notes": notes},
    )

    # Stream response
    for event in remote_app.stream_query(
        user_id="web-user",
        session_id=session["id"],
        message=message,
    ):
        content = event.get("content")
        if content and content.get("parts"):
            for part in content["parts"]:
                if "text" in part:
                    yield part["text"]


@app.post("/api/chat")
async def chat(request: ChatRequest):
    """Chat with the knowledge agent."""

    async def generate():
        """Generate streaming response."""
        project_id = os.environ.get("GCP_PROJECT_ID")
        agent_engine_id = os.environ.get("AGENT_ENGINE_ID")
        local_mode = os.environ.get("LOCAL_MODE", "").lower() in ("true", "1", "yes")

        try:
            if project_id and agent_engine_id and not local_mode:
                # Use Agent Engine (production)
                print(f"Using Agent Engine: {agent_engine_id}")
                async for chunk in run_agent_engine(request.message, _notes_cache):
                    yield chunk
            else:
                # Run agent locally (development)
                print("Running agent locally with Vertex AI")
                async for chunk in run_local_agent(request.message, _notes_cache):
                    yield chunk

        except Exception as e:
            print(f"Agent error: {e}")
            yield f"Error: {str(e)}\n\nFalling back to simple search...\n\n"
            yield await fallback_response(request.message)

    return StreamingResponse(generate(), media_type="text/plain")


@app.post("/api/contribute")
async def contribute(body: ContributeRequest, request: Request):
    """Create a PR with note changes."""
    from backend.github_client import create_pr

    # Get repo name from environment
    repo_name = os.environ.get("KNOWLEDGE_REPO")
    if not repo_name:
        raise HTTPException(
            status_code=500,
            detail="KNOWLEDGE_REPO environment variable not set",
        )

    # Get user identity - check in order: IAP headers, dev env vars, fallback
    user_email = "anonymous@knowledge-agent.local"
    user_name = "Anonymous Contributor"

    # 1. Try IAP headers (production)
    iap_email = request.headers.get("X-Goog-Authenticated-User-Email", "")
    if iap_email and ":" in iap_email:
        user_email = iap_email.split(":", 1)[1]
        user_name = user_email.split("@")[0].replace(".", " ").title()
    # 2. Try dev environment variables (local testing)
    elif os.environ.get("DEV_USER_EMAIL"):
        user_email = os.environ["DEV_USER_EMAIL"]
        user_name = os.environ.get("DEV_USER_NAME") or user_email.split("@")[0].replace(".", " ").title()

    # Get target branch (defaults to repo's default branch if not set)
    target_branch = os.environ.get("KNOWLEDGE_BRANCH")

    try:
        result = create_pr(
            repo_name=repo_name,
            file_path=body.path,
            content=body.content,
            title=body.title,
            user_name=user_name,
            user_email=user_email,
            is_new=body.is_new,
            target_branch=target_branch,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create PR: {str(e)}")


@app.post("/api/contribute-batch")
async def contribute_batch(body: ContributeBatchRequest, request: Request):
    """Create a PR with multiple note changes."""
    from backend.github_client import create_pr_batch

    # Get repo name from environment
    repo_name = os.environ.get("KNOWLEDGE_REPO")
    if not repo_name:
        raise HTTPException(
            status_code=500,
            detail="KNOWLEDGE_REPO environment variable not set",
        )

    # Get user identity
    user_email = "anonymous@knowledge-agent.local"
    user_name = "Anonymous Contributor"

    # 1. Try IAP headers (production)
    iap_email = request.headers.get("X-Goog-Authenticated-User-Email", "")
    if iap_email and ":" in iap_email:
        user_email = iap_email.split(":", 1)[1]
        user_name = user_email.split("@")[0].replace(".", " ").title()
    # 2. Try dev environment variables (local testing)
    elif os.environ.get("DEV_USER_EMAIL"):
        user_email = os.environ["DEV_USER_EMAIL"]
        user_name = os.environ.get("DEV_USER_NAME") or user_email.split("@")[0].replace(".", " ").title()

    # Get target branch
    target_branch = os.environ.get("KNOWLEDGE_BRANCH")

    # Convert Pydantic models to dicts
    changes = [
        {
            "path": change.path,
            "content": change.content,
            "title": change.title,
            "is_new": change.is_new,
        }
        for change in body.changes
    ]

    try:
        result = create_pr_batch(
            repo_name=repo_name,
            changes=changes,
            pr_title=body.pr_title,
            user_name=user_name,
            user_email=user_email,
            target_branch=target_branch,
        )

        # Track the PR
        _submitted_prs[result["pr_number"]] = {
            "pr_number": result["pr_number"],
            "pr_url": result["pr_url"],
            "branch": result["branch"],
            "user_email": user_email,
            "files": [c["path"] for c in changes],
            "status": "open",
            "submitted_at": datetime.utcnow().isoformat(),
        }

        return result
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create PR: {str(e)}")


@app.get("/api/pr-status/{pr_number}")
async def get_pr_status_endpoint(pr_number: int):
    """Get the status of a pull request."""
    from backend.github_client import get_pr_status

    repo_name = os.environ.get("KNOWLEDGE_REPO")
    if not repo_name:
        raise HTTPException(
            status_code=500,
            detail="KNOWLEDGE_REPO environment variable not set",
        )

    try:
        result = get_pr_status(repo_name, pr_number)

        # Update local tracking if we have it
        if pr_number in _submitted_prs:
            _submitted_prs[pr_number]["status"] = result["status"]
            if result.get("merged_at"):
                _submitted_prs[pr_number]["merged_at"] = result["merged_at"]
            if result.get("closed_at"):
                _submitted_prs[pr_number]["closed_at"] = result["closed_at"]

        return result
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"PR not found or error: {str(e)}")


# ============================================================================
# GitHub Webhook Endpoint
# ============================================================================

@app.post("/api/github-webhook")
async def github_webhook(request: Request):
    """Handle GitHub webhook events for PR updates."""
    from backend.github_client import verify_webhook_signature

    # Get webhook secret from environment
    webhook_secret = os.environ.get("GITHUB_WEBHOOK_SECRET")

    # Verify signature if secret is configured
    if webhook_secret:
        signature = request.headers.get("X-Hub-Signature-256", "")
        body = await request.body()

        if not verify_webhook_signature(body, signature, webhook_secret):
            raise HTTPException(status_code=401, detail="Invalid webhook signature")

    # Parse event
    event_type = request.headers.get("X-GitHub-Event", "")
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    print(f"Received GitHub webhook: {event_type}")

    # Handle pull request events
    if event_type == "pull_request":
        action = payload.get("action", "")
        pr = payload.get("pull_request", {})
        pr_number = pr.get("number")

        print(f"PR #{pr_number} action: {action}")

        if action == "closed":
            merged = pr.get("merged", False)

            if merged:
                # PR was merged - refresh knowledge base
                print(f"PR #{pr_number} was merged, refreshing knowledge base...")
                await refresh_notes_cache(force=True)

                # Update tracking
                if pr_number in _submitted_prs:
                    _submitted_prs[pr_number]["status"] = "merged"
                    _submitted_prs[pr_number]["merged_at"] = datetime.utcnow().isoformat()

                return {"message": f"PR #{pr_number} merged, knowledge base refreshed"}
            else:
                # PR was closed without merging
                print(f"PR #{pr_number} was closed without merging")

                if pr_number in _submitted_prs:
                    _submitted_prs[pr_number]["status"] = "closed"
                    _submitted_prs[pr_number]["closed_at"] = datetime.utcnow().isoformat()

                return {"message": f"PR #{pr_number} closed"}

        elif action == "opened" or action == "reopened":
            # Track newly opened PR if it's from our app
            print(f"PR #{pr_number} opened/reopened")

    # Handle push events to main branch (direct pushes, not PR merges)
    elif event_type == "push":
        ref = payload.get("ref", "")
        default_branch = os.environ.get("KNOWLEDGE_BRANCH") or "main"

        if ref == f"refs/heads/{default_branch}":
            print(f"Push to {default_branch}, refreshing knowledge base...")
            await refresh_notes_cache(force=True)
            return {"message": "Knowledge base refreshed"}

    return {"message": "Webhook received"}


@app.get("/api/submitted-prs")
async def get_submitted_prs():
    """Get all tracked submitted PRs."""
    return {"prs": list(_submitted_prs.values())}


@app.post("/api/track-pr")
async def track_pr(pr_data: dict):
    """Track a submitted PR (called after PR creation)."""
    pr_number = pr_data.get("pr_number")
    if not pr_number:
        raise HTTPException(status_code=400, detail="pr_number required")

    _submitted_prs[pr_number] = {
        "pr_number": pr_number,
        "pr_url": pr_data.get("pr_url", ""),
        "branch": pr_data.get("branch", ""),
        "user_email": pr_data.get("user_email", ""),
        "files": pr_data.get("files", []),
        "status": "open",
        "submitted_at": datetime.utcnow().isoformat(),
    }

    return {"message": f"Tracking PR #{pr_number}"}


async def fallback_response(message: str) -> str:
    """Simple fallback when agent fails."""
    message_lower = message.lower()

    # List notes
    if "list" in message_lower or ("what" in message_lower and "available" in message_lower):
        notes_list = "\n".join(
            f"- **{n['title']}** (`{n['path']}`)" for n in _notes_cache.values()
        )
        return f"Available notes:\n\n{notes_list}"

    # Search
    matches = []
    for _path, note in _notes_cache.items():
        if any(
            word in note["title"].lower() or word in note["content"].lower()
            for word in message_lower.split()
            if len(word) > 3
        ):
            matches.append(note)

    if matches:
        response = f"Found {len(matches)} relevant note(s):\n\n"
        for note in matches[:3]:
            snippet = note["content"][:300].replace("\n", " ")
            response += f"**{note['title']}** (`{note['path']}`)\n> {snippet}...\n\n"
        return response

    return "I couldn't find relevant information. Try asking about available topics with 'list notes'."


# ============================================================================
# Static File Serving (Production)
# ============================================================================

# Serve frontend static files in production
# The frontend is built and copied to /app/static in the Docker container
STATIC_DIR = Path(__file__).parent.parent / "static"

if STATIC_DIR.exists():
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import FileResponse

    # Serve static assets (JS, CSS, images)
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    # Serve index.html for all non-API routes (SPA routing)
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """Serve the SPA for all non-API routes."""
        # Don't intercept API routes
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not found")

        # Try to serve the exact file if it exists
        file_path = STATIC_DIR / full_path
        if file_path.is_file():
            return FileResponse(file_path)

        # Otherwise serve index.html (SPA routing)
        return FileResponse(STATIC_DIR / "index.html")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
