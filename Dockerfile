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
# Railway mounts volumes with root ownership, so permissions are set at runtime
RUN mkdir -p /app/data && chmod 777 /app/data

# Railway sets PORT dynamically, default to 8000
ENV PORT=8000

# Note: Running as root on Railway because mounted volumes have root ownership
# For local dev, you can add USER appuser

# Use shell form to allow $PORT expansion
CMD uvicorn main:app --host 0.0.0.0 --port $PORT
