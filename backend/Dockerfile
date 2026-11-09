# ==============================================================================
# CloudOps Sentinel - Backend Dockerfile
# Python 3.12 Multi-Stage, Minimal Attack Surface, Non-Root Execution
# ==============================================================================

FROM python:3.12-slim-bookworm AS base

# Install system runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Set operational environment flags
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Create a dedicated non-root operational system user
RUN groupadd -g 10001 cloudops && \
    useradd -u 10001 -g cloudops -m -s /bin/bash cloudops

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . .

# Adjust permissions for non-root runtime
RUN chown -R cloudops:cloudops /app

USER cloudops

EXPOSE 8000

# Default entrypoint runs uvicorn with production worker configuration
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

