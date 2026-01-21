---
name: knowledge-note-writer
description: Creates well-structured knowledge notes for the company knowledge base. Use when helping users document processes, guides, best practices, or any organizational knowledge. Ensures consistent formatting and comprehensive coverage.
license: Apache-2.0
compatibility: Google ADK agents, Claude Code, and similar AI assistants
metadata:
  author: knowledge-agent
  version: "1.0"
  category: documentation
---

# Knowledge Note Writer

You are helping create a knowledge note for the company knowledge base. Follow these guidelines to ensure the note is useful, discoverable, and consistent with existing documentation.

## Note Structure

Every knowledge note should follow this structure:

```markdown
# Title

Brief overview paragraph (2-3 sentences) explaining what this note covers and who it's for.

## Section 1: Context/Background
Why this matters, when to use this knowledge.

## Section 2: Main Content
The core information, broken into logical subsections.

### Subsection (if needed)
More detailed information.

## Section 3: Examples (if applicable)
Concrete examples, code snippets, or scenarios.

## Section 4: Related Resources
Links to related notes, external docs, or contacts.
```

## Writing Guidelines

### Titles
- Use clear, searchable titles
- Start with a noun or action verb
- Bad: "Some Notes on Python"
- Good: "Python Best Practices" or "How to Deploy to Cloud Run"

### Content
- Write for someone who has context about the company but not about this specific topic
- Use bullet points for lists of items
- Use numbered lists for sequential steps
- Include code blocks with language hints for technical content
- Define acronyms on first use

### Tone
- Professional but approachable
- Direct and concise
- Avoid jargon unless necessary (and define it when used)

### Length
- Aim for 200-800 words for most notes
- Break very long topics into multiple linked notes
- Every section should add value - remove filler

## Metadata to Consider

When creating a note, determine:
1. **Topic/Category**: Which folder should this live in? (engineering, processes, security, clients, etc.)
2. **Audience**: Who needs this information?
3. **Related Notes**: What existing notes should link to/from this?

## Quality Checklist

Before finalizing a note, verify:
- [ ] Title is clear and searchable
- [ ] Overview explains what and why
- [ ] Steps are numbered and actionable
- [ ] Code examples are tested/realistic
- [ ] Related resources are linked
- [ ] No sensitive information included

## Example Note

```markdown
# Setting Up Local Development Environment

This guide walks through setting up your local development environment for Python projects at the company.

## Prerequisites

- macOS or Linux (Windows users: use WSL2)
- Homebrew (macOS) or apt (Linux)
- Git installed and configured

## Installation Steps

1. **Install Python 3.11+**
   ```bash
   brew install python@3.11
   ```

2. **Install uv (package manager)**
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

3. **Clone the project**
   ```bash
   git clone <repo-url>
   cd project-name
   ```

4. **Install dependencies**
   ```bash
   uv sync
   ```

## Verification

Run the test suite to verify setup:
```bash
uv run pytest
```

You should see all tests passing.

## Common Issues

**Issue**: `uv: command not found`
**Solution**: Restart your terminal or run `source ~/.bashrc`

## Related

- [Python Best Practices](engineering/python-best-practices.md)
- [GCP Deployment Guide](engineering/gcp-deployment.md)
```

## When Helping Users

1. Ask clarifying questions about the topic if needed
2. Suggest an appropriate category/topic folder
3. Draft the note following this structure
4. Highlight any areas that need more detail from the user
5. Suggest related existing notes to link to
