# Multi-stage Dockerfile for MCP RAG Server
# Supports both development and production builds

# =============================================================================
# Base Python Image with Common Dependencies
# =============================================================================
FROM python:3.11-slim as base

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    git \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Create app directory and user
RUN useradd --create-home --shell /bin/bash app
WORKDIR /app
RUN chown app:app /app

# Install Python dependencies
COPY requirements/base.txt requirements/base.txt
RUN pip install --upgrade pip && \
    pip install -r requirements/base.txt

# =============================================================================
# Development Stage
# =============================================================================
FROM base as development

# Install development dependencies
COPY requirements/dev.txt requirements/dev.txt
RUN pip install -r requirements/dev.txt

# Copy source code
COPY --chown=app:app . .

USER app

# Default command for development
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# =============================================================================
# Production Stage
# =============================================================================
FROM base as production

# Install production dependencies
COPY requirements/prod.txt requirements/prod.txt
RUN pip install -r requirements/prod.txt

# Copy source code
COPY --chown=app:app . .

USER app

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default command for production
CMD ["python", "-m", "gunicorn", "app.main:app", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000"]

# =============================================================================
# Build Target Selection
# =============================================================================
# Use build argument to select target
ARG BUILD_TARGET=development
FROM (${BUILD_TARGET}) as final