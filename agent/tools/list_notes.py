from collections import defaultdict

from google.adk.tools import FunctionTool
from google.adk.tools.tool_context import ToolContext


async def list_notes(tool_context: ToolContext) -> str:
    """List all available notes in the knowledge base organized by topic.

    Use this tool to discover what knowledge is available before searching
    or when you need an overview of all topics.

    Returns:
        A hierarchical list of all notes organized by their directory/topic.
    """
    notes = tool_context.state.get("notes", {})

    if not notes:
        return "No knowledge base loaded. Please ensure notes are available."

    # Group notes by their parent directory (topic)
    by_topic: dict[str, list[dict]] = defaultdict(list)

    for path, note_data in notes.items():
        # Extract topic from path (first directory level)
        parts = path.split("/")
        if len(parts) > 1:
            topic = parts[0]
        else:
            topic = "General"

        by_topic[topic].append(
            {
                "path": path,
                "title": note_data.get("title", path),
            }
        )

    # Format output
    result = f"Knowledge Base: {len(notes)} note(s) across {len(by_topic)} topic(s)\n\n"

    for topic in sorted(by_topic.keys()):
        topic_notes = by_topic[topic]
        result += f"## {topic.replace('-', ' ').title()} ({len(topic_notes)} notes)\n"

        for note in sorted(topic_notes, key=lambda x: x["title"]):
            result += f"- **{note['title']}** (`{note['path']}`)\n"

        result += "\n"

    result += "Use search_knowledge to find specific information, or get_note to read a full note."

    return result


list_notes_tool = FunctionTool(list_notes)
