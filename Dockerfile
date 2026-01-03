# =============================================================================
# LightRAG EUDI Knowledge Graph Service
# Railway-optimized Docker image
# =============================================================================

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Environment configuration
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create data directory for graph persistence
# This should be mounted as a Railway Volume in production
RUN mkdir -p /app/data

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash appuser \
    && chown -R appuser:appuser /app
USER appuser

# Railway sets PORT dynamically, default to 8000
ENV PORT=8000

# Use shell form to allow $PORT expansion
CMD uvicorn main:app --host 0.0.0.0 --port $PORT
