"""GitHub App client for creating PRs and fetching knowledge base."""

import hashlib
import hmac
import json
import os
import re
import time
from typing import Optional

from github import Auth, Github, GithubIntegration, InputGitAuthor


def get_github_client() -> Optional[Github]:
    """Get an authenticated GitHub client using GitHub App credentials.

    Required environment variables:
    - GITHUB_APP_ID: The GitHub App ID
    - GITHUB_APP_PRIVATE_KEY: The private key (PEM format, can be base64 encoded)
    - GITHUB_APP_INSTALLATION_ID: The installation ID for the target repo

    Returns:
        Authenticated Github client, or None if credentials are not configured.
    """
    app_id = os.environ.get("GITHUB_APP_ID")
    private_key = os.environ.get("GITHUB_APP_PRIVATE_KEY")
    installation_id = os.environ.get("GITHUB_APP_INSTALLATION_ID")

    if not all([app_id, private_key, installation_id]):
        return None

    # Handle base64-encoded private key (useful for environment variables)
    if not private_key.startswith("-----BEGIN"):
        import base64

        private_key = base64.b64decode(private_key).decode("utf-8")

    # Create GitHub App authentication
    auth = Auth.AppAuth(int(app_id), private_key)
    gi = GithubIntegration(auth=auth)

    # Get installation access token
    installation = gi.get_app_installation(int(installation_id))
    access_token = gi.get_access_token(installation.id)

    # Create authenticated client
    return Github(auth=Auth.Token(access_token.token))


def create_pr(
    repo_name: str,
    file_path: str,
    content: str,
    title: str,
    user_name: str,
    user_email: str,
    is_new: bool = False,
    target_branch: str | None = None,
) -> dict:
    """Create a PR with note changes.

    Args:
        repo_name: Full repo name (e.g., "org/knowledge-base")
        file_path: Path to the file in the repo (e.g., "my-note.md")
        content: New content for the file
        title: Title of the note (used in PR title/description)
        user_name: Display name of the contributor (for commit author)
        user_email: Email of the contributor (for commit author)
        is_new: Whether this is a new file or an update

    Returns:
        Dict with PR info: {"pr_url": "...", "pr_number": 123}

    Raises:
        ValueError: If GitHub is not configured
        Exception: If PR creation fails
    """
    client = get_github_client()
    if not client:
        raise ValueError(
            "GitHub App not configured. Set GITHUB_APP_ID, GITHUB_APP_PRIVATE_KEY, and GITHUB_APP_INSTALLATION_ID."
        )

    repo = client.get_repo(repo_name)

    # Create a unique branch name
    timestamp = int(time.time())
    safe_title = "".join(c if c.isalnum() else "-" for c in title.lower())[:30]
    branch_name = f"kb/{safe_title}-{timestamp}"

    # Get the target branch (default to repo's default branch)
    base_branch = target_branch or repo.default_branch
    base_ref = repo.get_branch(base_branch)

    # Create new branch from base
    repo.create_git_ref(ref=f"refs/heads/{branch_name}", sha=base_ref.commit.sha)

    # Create author object for the commit - this shows the user as the author
    author = InputGitAuthor(name=user_name, email=user_email)

    # Create or update the file
    action = "Add" if is_new else "Update"
    commit_message = f"{action} {title}"

    if is_new:
        repo.create_file(
            path=file_path,
            message=commit_message,
            content=content,
            branch=branch_name,
            author=author,  # User shown as author
        )
    else:
        # Get current file to get its SHA
        try:
            current_file = repo.get_contents(file_path, ref=base_branch)
            repo.update_file(
                path=file_path,
                message=commit_message,
                content=content,
                sha=current_file.sha,
                branch=branch_name,
                author=author,  # User shown as author
            )
        except Exception:
            # File doesn't exist, create it
            repo.create_file(
                path=file_path,
                message=commit_message,
                content=content,
                branch=branch_name,
                author=author,
            )

    # Create PR
    pr_title = f"{action}: {title}"
    pr_body = f"""## Knowledge Base Contribution

**Note:** {title}
**File:** `{file_path}`
**Action:** {action}
**Contributed by:** {user_name} ({user_email})

---

Please review the changes and merge if appropriate.
"""

    pr = repo.create_pull(
        title=pr_title,
        body=pr_body,
        head=branch_name,
        base=base_branch,
    )

    return {
        "pr_url": pr.html_url,
        "pr_number": pr.number,
        "branch": branch_name,
    }


def create_pr_batch(
    repo_name: str,
    changes: list[dict],
    pr_title: str,
    user_name: str,
    user_email: str,
    target_branch: str | None = None,
) -> dict:
    """Create a PR with multiple file changes.

    Args:
        repo_name: Full repo name (e.g., "org/knowledge-base")
        changes: List of changes, each with {path, content, title, is_new}
        pr_title: Title for the PR
        user_name: Display name of the contributor (for commit author)
        user_email: Email of the contributor (for commit author)
        target_branch: Branch to target (defaults to repo's default branch)

    Returns:
        Dict with PR info: {"pr_url": "...", "pr_number": 123}
    """
    client = get_github_client()
    if not client:
        raise ValueError(
            "GitHub App not configured. Set GITHUB_APP_ID, GITHUB_APP_PRIVATE_KEY, and GITHUB_APP_INSTALLATION_ID."
        )

    repo = client.get_repo(repo_name)

    # Create a unique branch name
    timestamp = int(time.time())
    safe_title = "".join(c if c.isalnum() else "-" for c in pr_title.lower())[:30]
    branch_name = f"kb/{safe_title}-{timestamp}"

    # Get the target branch (default to repo's default branch)
    base_branch = target_branch or repo.default_branch
    base_ref = repo.get_branch(base_branch)

    # Create new branch from base
    repo.create_git_ref(ref=f"refs/heads/{branch_name}", sha=base_ref.commit.sha)

    # Create author object for commits
    author = InputGitAuthor(name=user_name, email=user_email)

    # Process each change
    files_added = []
    files_updated = []

    for change in changes:
        file_path = change["path"]
        content = change["content"]
        title = change.get("title", file_path)
        is_new = change.get("is_new", False)

        action = "Add" if is_new else "Update"
        commit_message = f"{action} {title}"

        if is_new:
            repo.create_file(
                path=file_path,
                message=commit_message,
                content=content,
                branch=branch_name,
                author=author,
            )
            files_added.append(f"- `{file_path}` (new)")
        else:
            try:
                current_file = repo.get_contents(file_path, ref=base_branch)
                repo.update_file(
                    path=file_path,
                    message=commit_message,
                    content=content,
                    sha=current_file.sha,
                    branch=branch_name,
                    author=author,
                )
                files_updated.append(f"- `{file_path}`")
            except Exception:
                # File doesn't exist, create it
                repo.create_file(
                    path=file_path,
                    message=commit_message,
                    content=content,
                    branch=branch_name,
                    author=author,
                )
                files_added.append(f"- `{file_path}` (new)")

    # Build PR body
    pr_body_parts = ["## Knowledge Base Contribution\n"]
    pr_body_parts.append(f"**Contributed by:** {user_name} ({user_email})\n")

    if files_added:
        pr_body_parts.append("### New Notes")
        pr_body_parts.extend(files_added)
        pr_body_parts.append("")

    if files_updated:
        pr_body_parts.append("### Updated Notes")
        pr_body_parts.extend(files_updated)
        pr_body_parts.append("")

    pr_body_parts.append("---\n")
    pr_body_parts.append("Please review the changes and merge if appropriate.")

    pr = repo.create_pull(
        title=pr_title,
        body="\n".join(pr_body_parts),
        head=branch_name,
        base=base_branch,
    )

    return {
        "pr_url": pr.html_url,
        "pr_number": pr.number,
        "branch": branch_name,
        "files_changed": len(changes),
    }


def get_pr_status(repo_name: str, pr_number: int) -> dict:
    """Get the status of a pull request.

    Args:
        repo_name: Full repo name (e.g., "org/knowledge-base")
        pr_number: The PR number

    Returns:
        Dict with PR status: {"status": "open|merged|closed", "merged_at": "...", "closed_at": "..."}
    """
    client = get_github_client()
    if not client:
        raise ValueError("GitHub App not configured")

    repo = client.get_repo(repo_name)
    pr = repo.get_pull(pr_number)

    status = "open"
    if pr.merged:
        status = "merged"
    elif pr.state == "closed":
        status = "closed"

    return {
        "pr_number": pr_number,
        "status": status,
        "merged_at": pr.merged_at.isoformat() if pr.merged_at else None,
        "closed_at": pr.closed_at.isoformat() if pr.closed_at else None,
        "html_url": pr.html_url,
    }


def fetch_knowledge_base(repo_name: str, branch: str | None = None) -> dict[str, dict]:
    """Fetch all markdown files from the knowledge base repo.

    Args:
        repo_name: Full repo name (e.g., "org/knowledge-base")
        branch: Branch to fetch from (defaults to repo's default branch)

    Returns:
        Dict mapping filename to note data: {path: {content, title, path, topic}}
    """
    client = get_github_client()
    if not client:
        raise ValueError("GitHub App not configured")

    repo = client.get_repo(repo_name)
    target_branch = branch or repo.default_branch

    # Fetch clusters.json for topic mapping
    note_to_cluster = {}
    try:
        clusters_file = repo.get_contents("clusters.json", ref=target_branch)
        clusters_data = json.loads(clusters_file.decoded_content.decode("utf-8"))
        for cluster in clusters_data.get("clusters", []):
            cluster_name = cluster.get("name", "General")
            for note_file in cluster.get("notes", []):
                note_to_cluster[note_file] = cluster_name
    except Exception:
        pass  # No clusters.json or error reading it

    # Fetch all markdown files from root
    notes = {}
    try:
        contents = repo.get_contents("", ref=target_branch)
        for content_file in contents:
            if content_file.type == "file" and content_file.name.endswith(".md"):
                try:
                    file_content = content_file.decoded_content.decode("utf-8")
                    filename = content_file.name
                    title = extract_title_from_content(file_content, filename)
                    topic = note_to_cluster.get(filename, "General")

                    notes[filename] = {
                        "content": file_content,
                        "title": title,
                        "path": filename,
                        "topic": topic,
                    }
                except Exception:
                    pass  # Skip files that can't be decoded
    except Exception as e:
        raise ValueError(f"Failed to fetch knowledge base: {e}")

    return notes


def extract_title_from_content(content: str, filename: str) -> str:
    """Extract title from markdown content."""
    match = re.match(r"^#\s+(.+)$", content.strip(), re.MULTILINE)
    if match:
        return match.group(1).strip()
    return filename.replace("-", " ").replace("_", " ").replace(".md", "").title()


def fetch_clusters(repo_name: str, branch: str | None = None) -> dict:
    """Fetch clusters.json from the repo.

    Args:
        repo_name: Full repo name
        branch: Branch to fetch from

    Returns:
        Clusters data or empty dict if not found
    """
    client = get_github_client()
    if not client:
        return {}

    repo = client.get_repo(repo_name)
    target_branch = branch or repo.default_branch

    try:
        clusters_file = repo.get_contents("clusters.json", ref=target_branch)
        return json.loads(clusters_file.decoded_content.decode("utf-8"))
    except Exception:
        return {}


def verify_webhook_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Verify GitHub webhook signature.

    Args:
        payload: Raw request body
        signature: X-Hub-Signature-256 header value
        secret: Webhook secret

    Returns:
        True if signature is valid
    """
    if not signature or not signature.startswith("sha256="):
        return False

    expected_signature = "sha256=" + hmac.new(
        secret.encode("utf-8"),
        payload,
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(signature, expected_signature)


def push_clusters(repo_name: str, clusters_data: dict, branch: str | None = None) -> bool:
    """Push clusters.json to the repo.

    Args:
        repo_name: Full repo name
        clusters_data: Clusters data to push
        branch: Branch to push to

    Returns:
        True if successful
    """
    client = get_github_client()
    if not client:
        raise ValueError("GitHub App not configured")

    repo = client.get_repo(repo_name)
    target_branch = branch or repo.default_branch

    content = json.dumps(clusters_data, indent=2)

    try:
        # Try to get existing file
        existing = repo.get_contents("clusters.json", ref=target_branch)
        repo.update_file(
            path="clusters.json",
            message="Update clusters.json",
            content=content,
            sha=existing.sha,
            branch=target_branch,
        )
    except Exception:
        # File doesn't exist, create it
        repo.create_file(
            path="clusters.json",
            message="Add clusters.json",
            content=content,
            branch=target_branch,
        )

    return True
