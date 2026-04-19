# syntax=docker/dockerfile:1.7

# ============================================================
# Online Smart Pick Ecosystem — Backend Dockerfile
# ============================================================
# Multi-stage build:
#   1) "builder" installs dependencies into a wheel cache
#   2) "runtime" is a slim image that only copies what's needed
# ============================================================

FROM python:3.12-slim AS builder

# System deps needed to build some Python packages (cryptography, psycopg2, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Copy only requirements first — better layer caching
COPY requirements.txt .

# Install into a dedicated prefix so we can copy it to the runtime stage
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir --prefix=/install -r requirements.txt


# ============================================================
# Runtime stage
# ============================================================
FROM python:3.12-slim AS runtime

# Runtime libs only (no build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user to run the app
RUN useradd --create-home --shell /bin/bash appuser

WORKDIR /app

# Copy installed Python packages from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY --chown=appuser:appuser . /app

# Switch to non-root user
USER appuser

# FastAPI default port
EXPOSE 8000

# Healthcheck hits the liveness endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -fsS http://localhost:8000/api/v1/health || exit 1

# Use uvicorn with production-friendly settings.
# --reload is NOT set here; docker-compose enables it for dev.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
