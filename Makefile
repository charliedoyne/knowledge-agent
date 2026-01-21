.PHONY: help install lint format test backend frontend adk-web deploy-agent

PROJECT_ID ?= $(shell gcloud config get-value project)
REGION ?= europe-west2

help:  ## Show this help message
	@echo "Usage: make <target>"
	@echo ""
	@echo "Targets:"
	@grep -h -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install:  ## Install all dependencies
	uv sync
	cd frontend && npm install

lint:  ## Run linter
	uv run ruff check .

format:  ## Format code
	uv run ruff format .

check: lint format  ## Run linter and formatter

test:  ## Run tests
	uv run pytest tests/

backend:  ## Run FastAPI backend (port 8000) - uses LOCAL_MODE from .env
	uv run uvicorn backend.main:app --reload --port 8000

backend-local:  ## Run backend with local agent (Vertex AI)
	LOCAL_MODE=true uv run uvicorn backend.main:app --reload --port 8000

backend-ae:  ## Run backend with Agent Engine (requires AGENT_ENGINE_ID in .env)
	LOCAL_MODE=false uv run uvicorn backend.main:app --reload --port 8000

frontend:  ## Run React frontend (port 3000)
	cd frontend && npm run dev

adk-web:  ## Run ADK web UI for agent testing
	uv run adk web agent/

dev:  ## Run both backend and frontend (use in separate terminals)
	@echo "Run these in separate terminals:"
	@echo "  make backend-local  # Terminal 1: Local agent with Vertex AI"
	@echo "  make backend-ae     # Terminal 1: Agent Engine (production)"
	@echo "  make frontend       # Terminal 2: React on :3000"

create-agent:  ## Create agent on Agent Engine (first time)
	uv run adk deploy agent_engine \
		--project $(PROJECT_ID) \
		--region $(REGION) \
		agent

deploy-agent:  ## Deploy agent updates to Agent Engine
	@if [ -z "$(AGENT_ENGINE_ID)" ]; then \
		echo "Error: AGENT_ENGINE_ID is required. Run: make deploy-agent AGENT_ENGINE_ID=your-id"; \
		exit 1; \
	fi
	uv run adk deploy agent_engine \
		--project $(PROJECT_ID) \
		--region $(REGION) \
		--agent_engine_id $(AGENT_ENGINE_ID) \
		agent

build-frontend:  ## Build React frontend for production
	cd frontend && npm run build

cluster-notes:  ## Run AI clustering on knowledge notes
	uv run python scripts/cluster_notes.py
