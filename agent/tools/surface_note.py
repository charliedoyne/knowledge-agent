"""Tool to surface a note to the user with optional highlighting."""

import json

from google.adk.tools import ToolContext


def surface_note(
    path: str,
    highlight_text: str | None = None,
    section_title: str | None = None,
    tool_context: ToolContext = None,
) -> str:
    """Surface a note to the user interface with optional highlighting.

    Use this tool when you want to show a specific note to the user alongside
    your explanation. The note will appear in the user's note viewer with the
    relevant section highlighted.

    Args:
        path: The path to the note (e.g., "engineering/gcp-deployment.md")
        highlight_text: Optional text snippet to highlight in the note. The UI
            will scroll to and highlight this text.
        section_title: Optional section heading to scroll to (e.g., "## Deployment Steps")
        tool_context: Injected tool context for accessing session state.

    Returns:
        Confirmation message that the note has been surfaced.
    """
    notes = tool_context.state.get("notes", {}) if tool_context else {}

    if path not in notes:
        available = list(notes.keys())[:5]
        return f"Note '{path}' not found. Available notes: {', '.join(available)}"

    note = notes[path]
    title = note.get("title", path)

    # Create a special marker that the frontend will parse and remove
    # This allows the surface event to be transmitted through the text stream
    surface_event = {
        "type": "surface_note",
        "path": path,
        "title": title,
        "highlight_text": highlight_text,
        "section_title": section_title,
    }

    # The marker format: <!--SURFACE:{json}-->
    # Frontend will extract these and not display them
    marker = f"<!--SURFACE:{json.dumps(surface_event)}-->"

    # Store in state as well for potential future use
    if tool_context:
        current_surfaces = tool_context.state.get("_surface_requests", [])
        current_surfaces.append(surface_event)
        tool_context.state["_surface_requests"] = current_surfaces

    # Return the marker (which goes in the stream) plus a confirmation for the agent
    return f"{marker}\nNote '{title}' has been surfaced to the user's viewer."
