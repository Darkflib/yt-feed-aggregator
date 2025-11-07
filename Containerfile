# Multi-stage Containerfile for YouTube Feed Aggregator
# Stage 1: Build frontend
FROM node:24-bookworm AS frontend
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build

# Stage 2: Python backend
FROM python:3.13-slim AS backend
ENV PYTHONUNBUFFERED=1

# Install curl for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install uv for faster Python package management
RUN pip install --no-cache-dir uv

# Copy dependency files
COPY pyproject.toml uv.lock* ./

# Install Python dependencies using uv
RUN uv pip install --system --no-cache -r pyproject.toml

# Copy application source code
COPY app ./app
COPY main.py ./
COPY alembic.ini ./
COPY alembic ./alembic

# Copy built frontend from stage 1
COPY --from=frontend /app/frontend/dist ./static

# Copy entrypoint script
COPY entrypoint.sh ./
RUN chmod +x entrypoint.sh

# Expose port 8080
EXPOSE 8080

# Health check on /healthz endpoint (only for web mode)
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/healthz || exit 1

# Use entrypoint script that supports both web and worker modes
ENTRYPOINT ["./entrypoint.sh"]

# Default to web mode
CMD ["web"]
