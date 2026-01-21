# Knowledge Sharing Agent

**[Demo Video](TODO: Add link)**

A company-wide knowledge sharing agent with a chat-focused interface. Employees can ask questions, search documentation, and contribute new knowledge.

## Value Proposition

- **Single Chat Interface**: One place to ask questions and get answers
- **AI-Powered Search**: Natural language queries against the knowledge base
- **Easy Contributions**: Draft new knowledge with AI assistance
- **Version Controlled**: Knowledge stored as markdown in git

## Features

- **Chat Interface**: Ask questions, get answers with source citations
- **Knowledge Browser**: Sidebar to explore available documentation
- **Contribute**: Draft new documentation through the chat
- **Streaming Responses**: Real-time AI responses

## Architecture

```
┌─────────────────────────────────────────┐
│  React Frontend (Vite + Tailwind)       │
│  - Chat-focused UI                      │
│  - Knowledge sidebar                    │
│  - Streaming responses                  │
└──────────────────┬──────────────────────┘
                   │ /api/*
                   ▼
┌─────────────────────────────────────────┐
│  FastAPI Backend                        │
│  - /api/chat - Agent queries            │
│  - /api/notes - Knowledge listing       │
│  - Connects to Agent Engine             │
└──────────────────┬──────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────┐
│  Agent Engine (Vertex AI)               │
│  - Google ADK agent                     │
│  - Knowledge tools                      │
└──────────────────┬──────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────┐
│  Knowledge Base (Markdown in Git)       │
└─────────────────────────────────────────┘
```

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- [uv](https://github.com/astral-sh/uv) (Python package manager)

### Installation

```bash
# Install all dependencies
make install

# Or manually:
uv sync
cd frontend && npm install
```

### Development

Run in two terminals:

```bash
# Terminal 1: Backend (FastAPI on :8000)
make backend

# Terminal 2: Frontend (React on :3000)
make frontend
```

Then open http://localhost:3000

### Test Agent Locally

```bash
# Run ADK web UI (no frontend needed)
make adk-web
```

## Project Structure

```
my_agent/
├── agent/                 # Google ADK Agent
│   ├── agent.py          # Main agent definition
│   ├── prompts/          # Agent instructions
│   └── tools/            # search, get_note, list_notes
├── backend/              # FastAPI backend
│   └── main.py          # API endpoints
├── frontend/             # React frontend
│   ├── src/
│   │   ├── App.tsx      # Main chat UI
│   │   └── main.tsx
│   └── package.json
├── knowledge/            # Knowledge base (markdown)
│   ├── engineering/
│   ├── processes/
│   ├── security/
│   └── clients/
├── skills/               # Agent Skills definitions
├── pyproject.toml
├── Makefile
└── README.md
```

## Environment Variables

```bash
# For Agent Engine connection (optional for local dev)
GCP_PROJECT_ID=your-project-id
GCP_REGION=europe-west2
AGENT_ENGINE_ID=your-agent-engine-id
```

## Deployment

```bash
# Deploy agent to Agent Engine
make create-agent PROJECT_ID=your-project

# Update existing agent
make deploy-agent PROJECT_ID=your-project AGENT_ENGINE_ID=your-id

# Build frontend for production
make build-frontend
```

## Technology Stack

- **Agent**: Google ADK + Gemini 2.5 Flash
- **Backend**: FastAPI + Uvicorn
- **Frontend**: React + Vite + Tailwind CSS
- **Knowledge**: Markdown files in Git

## Competition

Built for the **Agents in SDLC Competition (Q4 2025)** - Category 4: Wildcard

---

Built with Google ADK and Gemini
