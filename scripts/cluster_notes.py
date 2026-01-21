#!/usr/bin/env python3
"""Cluster knowledge notes into topics using AI.

This script:
1. Fetches notes from the GitHub knowledge-base repo
2. Uses AI to cluster them into topics
3. Pushes the clusters.json back to the repo
"""

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Load .env file from project root
load_dotenv(Path(__file__).parent.parent / ".env")

# Configure for Vertex AI
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "TRUE"

from google import genai

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


def fetch_notes_from_github() -> dict[str, dict]:
    """Fetch notes from GitHub repo."""
    from backend.github_client import fetch_knowledge_base

    repo_name = os.environ.get("KNOWLEDGE_REPO")
    branch = os.environ.get("KNOWLEDGE_BRANCH")

    if not repo_name:
        print("ERROR: KNOWLEDGE_REPO environment variable not set")
        sys.exit(1)

    print(f"Fetching notes from {repo_name} (branch: {branch or 'default'})...")
    notes = fetch_knowledge_base(repo_name, branch)

    # Convert to format needed for clustering
    result = {}
    for filename, data in notes.items():
        result[filename] = {
            "title": data["title"],
            "content": data["content"][:500],  # First 500 chars
        }

    return result


def cluster_notes(notes: dict[str, dict]) -> dict:
    """Use AI to cluster notes into topics."""
    # Create a summary of notes for the AI
    notes_summary = "\n".join(
        f"- {filename}: {data['title']}\n  Preview: {data['content'][:200]}..."
        for filename, data in notes.items()
    )

    prompt = f"""Analyze these knowledge base notes and group them into 3-5 logical topic clusters.

Notes:
{notes_summary}

Return a JSON object with this exact structure:
{{
  "clusters": [
    {{
      "name": "Topic Name",
      "description": "Brief description of this topic",
      "notes": ["filename1.md", "filename2.md"]
    }}
  ]
}}

Rules:
- Each note should be in exactly one cluster
- Use clear, concise topic names (1-3 words)
- Group by theme/purpose, not just keywords
- Return ONLY the JSON, no other text
"""

    # Initialize client (uses ADC for Vertex AI)
    project_id = os.environ.get("GCP_PROJECT_ID") or os.environ.get("GOOGLE_CLOUD_PROJECT")
    location = os.environ.get("GCP_REGION", "europe-west2")

    if project_id:
        os.environ["GOOGLE_CLOUD_PROJECT"] = project_id
    os.environ["GOOGLE_CLOUD_LOCATION"] = location

    client = genai.Client()

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
    )

    # Parse the JSON response
    response_text = response.text.strip()
    # Remove markdown code blocks if present
    if response_text.startswith("```"):
        response_text = response_text.split("```")[1]
        if response_text.startswith("json"):
            response_text = response_text[4:]
        response_text = response_text.strip()

    return json.loads(response_text)


def push_clusters_to_github(clusters: dict) -> None:
    """Push clusters.json to GitHub repo."""
    from backend.github_client import push_clusters

    repo_name = os.environ.get("KNOWLEDGE_REPO")
    branch = os.environ.get("KNOWLEDGE_BRANCH")

    print(f"\nPushing clusters.json to {repo_name}...")
    push_clusters(repo_name, clusters, branch)
    print("Done!")


def main():
    """Main entry point."""
    print("=== Knowledge Notes Clustering ===\n")

    # Check for --local flag for local testing
    local_mode = "--local" in sys.argv

    if local_mode:
        # Load from local files (for testing)
        knowledge_dir = Path(__file__).parent.parent / "knowledge"
        print(f"Loading notes from local directory: {knowledge_dir}")

        notes = {}
        for md_file in knowledge_dir.glob("*.md"):
            content = md_file.read_text(encoding="utf-8")
            title = md_file.stem.replace("-", " ").replace("_", " ").title()
            for line in content.split("\n"):
                if line.startswith("# "):
                    title = line[2:].strip()
                    break
            notes[md_file.name] = {"title": title, "content": content[:500]}
    else:
        # Fetch from GitHub
        notes = fetch_notes_from_github()

    print(f"Found {len(notes)} notes")

    if len(notes) == 0:
        print("No notes found, exiting.")
        return

    print("\nClustering notes with AI...")
    clusters = cluster_notes(notes)

    print("\nClusters:")
    for cluster in clusters.get("clusters", []):
        print(f"\n  {cluster['name']}:")
        print(f"    {cluster['description']}")
        for note in cluster.get("notes", []):
            print(f"    - {note}")

    if local_mode:
        # Save locally
        clusters_file = Path(__file__).parent.parent / "knowledge" / "clusters.json"
        print(f"\nSaving to {clusters_file}...")
        with open(clusters_file, "w") as f:
            json.dump(clusters, f, indent=2)
        print("Done!")
    else:
        # Push to GitHub
        push_clusters_to_github(clusters)


if __name__ == "__main__":
    main()
