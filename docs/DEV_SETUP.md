# Development Setup Guide

## Quick Start (New Laptop)

### 1. Clone the Repos

```bash
# Agent repo
git clone https://github.com/charliedoyne/knowledge-agent.git
cd knowledge-agent

# Knowledge base repo (in a separate directory)
cd ..
git clone https://github.com/charliedoyne/knowledge-base.git
```

### 2. Install Dependencies

```bash
# Python (using uv)
cd knowledge-agent
uv sync

# Frontend
cd frontend
npm install
```

### 3. Set Up Environment Variables

Copy the example and fill in your values:

```bash
cp .env.example .env
```

Edit `.env` with these values:

```bash
# GCP
GCP_PROJECT_ID=agent-competition
GCP_REGION=europe-west2

# GitHub App
GITHUB_APP_ID=2702919
GITHUB_APP_INSTALLATION_ID=105429479
GITHUB_APP_PRIVATE_KEY="<paste the private key from the .pem file>"

# Knowledge Base
KNOWLEDGE_REPO=charliedoyne/knowledge-base
KNOWLEDGE_BRANCH=main

# Local Dev Identity (so PRs show your name)
DEV_USER_EMAIL=charlie@datatonic.com
DEV_USER_NAME=Charlie
```

**Important**: You'll need the GitHub App private key. It's in a `.pem` file that was downloaded when you created the app. If you don't have it, you can generate a new one from the GitHub App settings.

### 4. Authenticate to GCP

```bash
gcloud auth login
gcloud auth application-default login
gcloud config set project agent-competition
```

### 5. Run Locally

Terminal 1 - Backend:
```bash
cd knowledge-agent
uv run poe backend
# Runs on http://localhost:8000
```

Terminal 2 - Frontend:
```bash
cd knowledge-agent/frontend
npm run dev
# Runs on http://localhost:3000
```

Open http://localhost:3000

---

## Current State of the Project

### What's Deployed

| Resource | URL/Value |
|----------|-----------|
| **App URL** | https://knowledge-agent-620272240818.europe-west2.run.app |
| **Webhook URL** | https://knowledge-agent-620272240818.europe-west2.run.app/api/github-webhook |
| **GCP Project** | agent-competition |
| **Region** | europe-west2 |

### What's Working

- ✅ Cloud Run deployment
- ✅ Notes fetched from GitHub (charliedoyne/knowledge-base)
- ✅ Chat with AI agent about notes
- ✅ Edit notes and create PRs
- ✅ Staging area for batching multiple changes
- ✅ Diff highlighting (green=added, red=removed, blue=PR pending)
- ✅ GitHub Actions CI/CD for auto-deploy
- ⚠️ Webhook (configured, was getting 401 - may need testing)

### What Still Needs Work

**Immediate:**
- [ ] Verify webhook is working (check GitHub App → Advanced → Recent Deliveries)
- [ ] Test PR merge → auto-refresh flow

**Feature Backlog:**
- [ ] Wiki-style linking between notes `[[note-name]]` (partially implemented)
- [ ] Random page button
- [ ] Admin recommended notes section
- [ ] IAP authentication (restrict to @datatonic.com)
- [ ] Clustering workflow for knowledge repo

---

## Key Files

| File | Purpose |
|------|---------|
| `backend/main.py` | FastAPI backend, API endpoints |
| `backend/github_client.py` | GitHub App integration, PR creation |
| `frontend/src/App.tsx` | React frontend |
| `agent/agent.py` | AI agent definition |
| `infra/` | Terraform for Cloud Run, IAM, etc. |
| `.github/workflows/deploy.yaml` | Auto-deploy on push to main |

---

## Useful Commands

```bash
# Run backend
uv run poe backend

# Run frontend
cd frontend && npm run dev

# Deploy manually (if needed)
cd infra && terraform apply

# Build Docker image via Cloud Build
gcloud builds submit --tag europe-west2-docker.pkg.dev/agent-competition/knowledge-agent/knowledge-agent:latest --project=agent-competition

# Check Cloud Run logs
gcloud run services logs read knowledge-agent --region=europe-west2 --project=agent-competition

# Get webhook secret
gcloud secrets versions access latest --secret=knowledge-agent-github-webhook-secret --project=agent-competition
```

---

## GitHub App Settings

**App URL**: https://github.com/settings/apps/knowledge-sharing-agent (or check your GitHub Apps list)

**Webhook Configuration:**
- URL: `https://knowledge-agent-620272240818.europe-west2.run.app/api/github-webhook`
- Secret: `c31807400fbc415bc4c95267cc9ff89678ab3317873edc6b9cc4b96e60efcbff`
- Events: Pull requests, Pushes

**Permissions needed:**
- Repository contents: Read & Write
- Pull requests: Read & Write
- Metadata: Read

---

## Troubleshooting

### "KNOWLEDGE_REPO not set"
Make sure your `.env` file has `KNOWLEDGE_REPO=charliedoyne/knowledge-base`

### "GitHub App not configured"
Check that `GITHUB_APP_ID`, `GITHUB_APP_PRIVATE_KEY`, and `GITHUB_APP_INSTALLATION_ID` are all set in `.env`

### Webhook returning 401
The webhook secret in GitHub App settings must exactly match what's in Secret Manager (no trailing spaces/newlines)

### Notes not updating after PR merge
1. Check webhook is configured and active
2. Check Recent Deliveries in GitHub App settings
3. If webhook failing, check Cloud Run logs

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Cloud Run: knowledge-agent                                  │
│  https://knowledge-agent-620272240818.europe-west2.run.app  │
├─────────────────────────────────────────────────────────────┤
│  React Frontend ──► FastAPI Backend ──► Gemini AI           │
│       │                   │                                  │
│       │                   ▼                                  │
│       │            GitHub API                                │
│       │            (fetch notes, create PRs)                 │
│       │                   │                                  │
│       ▼                   ▼                                  │
│  charliedoyne/knowledge-base repo                           │
└─────────────────────────────────────────────────────────────┘
         ▲
         │ Webhook (on PR merge/push)
         │
   GitHub sends POST to /api/github-webhook
   → App refreshes notes cache
```
