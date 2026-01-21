# Build stage for frontend
FROM node:20-slim AS frontend-builder

WORKDIR /app/frontend

# Copy frontend files
COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# Production stage
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY pyproject.toml ./
RUN pip install --no-cache-dir .

# Copy backend code
COPY backend/ ./backend/
COPY agent/ ./agent/
COPY scripts/ ./scripts/

# Copy built frontend to static directory
COPY --from=frontend-builder /app/frontend/dist ./static

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

# Expose port
EXPOSE 8080

# Run the application
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8080"]
