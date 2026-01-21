from google.adk.agents.llm_agent import Agent
from google.adk.apps import App
from google.adk.planners import BuiltInPlanner
from google.adk.plugins import ReflectAndRetryToolPlugin
from google.genai.types import (
    GenerateContentConfig,
    HarmBlockThreshold,
    HarmCategory,
    SafetySetting,
    ThinkingConfig,
)

from .prompts.root import INSTRUCTION, STATIC_INSTRUCTION
from .tools import draft_note, get_note_tool, list_notes_tool, search_knowledge_tool, surface_note

# Safety settings to prevent harmful content
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

# Root agent for knowledge queries
root_agent = Agent(
    name="knowledge_agent",
    model="gemini-2.5-flash",
    static_instruction=STATIC_INSTRUCTION,
    instruction=INSTRUCTION,
    generate_content_config=generate_content_config,
    tools=[
        search_knowledge_tool,
        get_note_tool,
        list_notes_tool,
        surface_note,
        draft_note,
    ],
    planner=BuiltInPlanner(
        thinking_config=ThinkingConfig(
            include_thoughts=True,
            thinking_budget=512,
        )
    ),
)

# Plugins for reliability
plugins = [
    ReflectAndRetryToolPlugin(max_retries=3, throw_exception_if_retry_exceeded=True),
]

# Main application
app = App(name="knowledge_agent", root_agent=root_agent, plugins=plugins)
