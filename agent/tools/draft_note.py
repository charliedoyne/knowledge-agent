"""Tool to draft note changes for user review."""

import json
import re

from google.adk.tools import ToolContext


def draft_note(
    content: str,
    title: str | None = None,
    path: str | None = None,
    tool_context: ToolContext = None,
) -> str:
    """Draft a new note or changes to an existing note for user review.

    Use this tool when:
    - A user shares knowledge they want to add to the knowledge base
    - You need to create a new note
    - You need to update an existing note with new information

    The drafted note will appear in the user's editor where they can review,
    modify, and submit it as a PR.

    Args:
        content: The full markdown content of the note. Include a # Title as the first line.
        title: Optional title for the note. If not provided, extracted from content.
        path: Optional path for the note (e.g., "my-new-note.md"). If not provided,
              generated from the title. For existing notes, use their exact path.
        tool_context: Injected tool context for accessing session state.

    Returns:
        Confirmation message that the draft is ready for user review.
    """
    notes = tool_context.state.get("notes", {}) if tool_context else {}

    # Extract title from content if not provided
    if not title:
        first_line = content.strip().split("\n")[0]
        if first_line.startswith("# "):
            title = first_line[2:].strip()
        else:
            title = "Untitled Note"

    # Generate path if not provided
    if not path:
        # Convert title to kebab-case filename
        slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
        path = f"{slug}.md"

    # Check if this is an existing note or new
    is_new = path not in notes

    # Create the draft event
    draft_event = {
        "type": "draft_note",
        "path": path,
        "title": title,
        "content": content,
        "is_new": is_new,
    }

    # Emit as a marker the frontend will parse
    marker = f"<!--DRAFT:{json.dumps(draft_event)}-->"

    action = "created" if is_new else "updated"
    return f"{marker}\nI've drafted the note '{title}'. Please review the content in the editor above. You can make any changes and then click 'Submit PR' to contribute it to the knowledge base."
