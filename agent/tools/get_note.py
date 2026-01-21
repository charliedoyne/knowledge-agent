from google.adk.tools import FunctionTool
from google.adk.tools.tool_context import ToolContext


async def get_note(note_path: str, tool_context: ToolContext) -> str:
    """Retrieve the full content of a specific knowledge note.

    Use this tool to get the complete content of a note after finding it via search.

    Args:
        note_path: The path to the note (e.g., "engineering/python-best-practices.md").

    Returns:
        The full markdown content of the note, or an error message if not found.
    """
    notes = tool_context.state.get("notes", {})

    if not notes:
        return "No knowledge base loaded. Please ensure notes are available."

    # Try exact match first
    if note_path in notes:
        note_data = notes[note_path]
        title = note_data.get("title", note_path)
        content = note_data.get("content", "")
        return f"""<note path="{note_path}" title="{title}">
{content}
</note>"""

    # Try partial match (in case user omits directory or extension)
    for path, note_data in notes.items():
        if note_path in path or path.endswith(note_path):
            title = note_data.get("title", path)
            content = note_data.get("content", "")
            return f"""<note path="{path}" title="{title}">
{content}
</note>"""

    # List available notes to help the user
    available = list(notes.keys())[:5]
    return f"""Note '{note_path}' not found.

Available notes include:
{chr(10).join('- ' + p for p in available)}

Use list_notes to see all available notes."""


get_note_tool = FunctionTool(get_note)
