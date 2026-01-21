from google.adk.tools import FunctionTool
from google.adk.tools.tool_context import ToolContext


async def search_knowledge(query: str, tool_context: ToolContext) -> str:
    """Search the knowledge base for notes matching the query.

    Use this tool to find relevant knowledge notes based on a search query.
    Returns a list of matching notes with relevant snippets.

    Args:
        query: The search query string to match against note titles and content.

    Returns:
        A formatted list of matching notes with snippets, or a message if no matches found.
    """
    notes = tool_context.state.get("notes", {})

    if not notes:
        return "No knowledge base loaded. Please ensure notes are available."

    query_lower = query.lower()
    matches = []

    for path, note_data in notes.items():
        title = note_data.get("title", path)
        content = note_data.get("content", "")

        # Simple keyword matching (can be enhanced with semantic search later)
        if query_lower in title.lower() or query_lower in content.lower():
            # Extract a snippet around the match
            content_lower = content.lower()
            match_pos = content_lower.find(query_lower)

            if match_pos != -1:
                start = max(0, match_pos - 100)
                end = min(len(content), match_pos + len(query) + 100)
                snippet = content[start:end]
                if start > 0:
                    snippet = "..." + snippet
                if end < len(content):
                    snippet = snippet + "..."
            else:
                # Match was in title, show first 200 chars of content
                snippet = content[:200] + "..." if len(content) > 200 else content

            matches.append(
                {
                    "path": path,
                    "title": title,
                    "snippet": snippet.strip(),
                }
            )

    if not matches:
        return f"No notes found matching '{query}'. Try different keywords or use list_notes to see all available notes."

    result = f"Found {len(matches)} note(s) matching '{query}':\n\n"
    for match in matches[:10]:  # Limit to top 10
        result += f"**{match['title']}** (`{match['path']}`)\n"
        result += f"> {match['snippet']}\n\n"

    if len(matches) > 10:
        result += f"...and {len(matches) - 10} more results."

    return result


search_knowledge_tool = FunctionTool(search_knowledge)
