# syntax=docker/dockerfile:1
# ============================================================
# Production Dockerfile — DevOps Agent v1.0.0 (CLI-only)
# ============================================================
ARG PYTHON_VERSION=3.12
ARG GIT_SHA=""
ARG APP_VERSION="1.0.0"
ARG BUILD_DATE=""

# ── Stage 1: Builder ─────────────────────────────────────────
FROM python:${PYTHON_VERSION}-slim AS builder

WORKDIR /build

# Install build deps (chroma-hnswlib needs C++ build tools)
# hadolint ignore=DL3008
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc=4:14.2.0-1 g++=4:14.2.0-1 build-essential=12.12 git=1:2.47.3-0+deb13u1 \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip and install build tools
# hadolint ignore=DL3013
RUN pip install --no-cache-dir uv==0.11.28

# Copy source + config
COPY pyproject.toml requirements.txt ./
COPY src/ ./src/
COPY configs/ ./configs/
COPY main.py ./

# Create venv and install deps with pip (needed for chroma-hnswlib compilation)
RUN uv venv /opt/venv
ENV VIRTUAL_ENV=/opt/venv PATH="/opt/venv/bin:$PATH"
RUN uv pip install --python=/opt/venv/bin/python -r requirements.txt \
    && uv pip install --python=/opt/venv/bin/python -e .

# ── Stage 2: Runtime ─────────────────────────────────────────
FROM python:${PYTHON_VERSION}-slim AS runtime

# chroma-hnswlib needs libstdc++ at runtime
# hadolint ignore=DL3008
RUN apt-get update \
    && apt-get upgrade -y --no-install-recommends \
    && apt-get install -y --no-install-recommends libstdc++6=14.2.0-19 \
    && rm -rf /var/lib/apt/lists/*

ARG GIT_SHA
ARG APP_VERSION
ARG BUILD_DATE

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    PATH="/opt/venv/bin:$PATH" \
    APP_VERSION=${APP_VERSION} \
    ENVIRONMENT=production

# Non-root user
RUN groupadd -r -g 10001 appgroup \
    && useradd -r -u 10001 -g appgroup --no-log-init appuser

WORKDIR /app

# Copy venv from builder
COPY --from=builder /opt/venv /opt/venv

# Copy application files
COPY --chown=appuser:appgroup main.py ./
COPY --chown=appuser:appgroup src/ ./src/
COPY --chown=appuser:appgroup configs/ ./configs/

# Ensure app directory and .cache are writable by the non-root user
RUN mkdir -p /app/.cache && chown -R appuser:appgroup /app

# OCI Labels
LABEL org.opencontainers.image.title="devops-agent" \
      org.opencontainers.image.description="AI-powered DevOps file generation tool (NVIDIA CLI)" \
      org.opencontainers.image.version="${APP_VERSION}" \
      org.opencontainers.image.revision="${GIT_SHA}" \
      org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.source="https://github.com/nithingowdahm87/devops_agent"

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD ["python3", "-c", "import sys; sys.exit(0)"]

USER appuser

# The agent requires a project path as argument
ENTRYPOINT ["python3", "main.py"]
CMD ["--help"]