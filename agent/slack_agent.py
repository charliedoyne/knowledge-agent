"""Slack-optimized agent for knowledge base queries."""

from google.adk.agents.llm_agent import Agent
from google.adk.planners import BuiltInPlanner
from google.genai.types import (
    GenerateContentConfig,
    HarmBlockThreshold,
    HarmCategory,
    SafetySetting,
    ThinkingConfig,
)

from .prompts.slack import SLACK_INSTRUCTION, SLACK_STATIC_INSTRUCTION
from .tools import get_note_tool, list_notes_tool, search_knowledge_tool

# Safety settings
generate_content_config = GenerateContentConfig(
    safety_settings=[
        SafetySetting(
            category=HarmCategory.HARM_CATEGORY_HARASSMENT,
            threshold=HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
        ),
        SafetySetting(
            category=HarmCategory.HARM_CATEGORY_HATE_SPEECH,
            threshold=HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
        ),
        SafetySetting(
            category=HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
            threshold=HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
        ),
        SafetySetting(
            category=HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
            threshold=HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
        ),
        SafetySetting(
            category=HarmCategory.HARM_CATEGORY_CIVIC_INTEGRITY,
            threshold=HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
        ),
    ],
)

# Slack agent - no surface_note tool since Slack can't display the viewer
slack_agent = Agent(
    name="knowledge_slack_agent",
    model="gemini-2.5-flash",
    static_instruction=SLACK_STATIC_INSTRUCTION,
    instruction=SLACK_INSTRUCTION,
    generate_content_config=generate_content_config,
    tools=[
        search_knowledge_tool,
        get_note_tool,
        list_notes_tool,
        # Note: No surface_note - Slack can't display the note viewer
    ],
    planner=BuiltInPlanner(
        thinking_config=ThinkingConfig(
            include_thoughts=True,
            thinking_budget=256,  # Smaller budget for faster Slack responses
        )
    ),
)
