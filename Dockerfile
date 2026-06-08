# syntax=docker/dockerfile:1
# ============================================================
# Production Dockerfile — DevOps Agent v2.0.0
# ============================================================
ARG PYTHON_VERSION=3.12
ARG GIT_SHA=""
ARG APP_VERSION="2.0.0"
ARG BUILD_DATE=""

# ── Stage 1: Builder ─────────────────────────────────────────
FROM python:${PYTHON_VERSION}-slim AS builder

WORKDIR /build

# Install build deps
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc git \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip and install build tools
RUN pip install --no-cache-dir --upgrade pip setuptools wheel uv

# Copy source + config
COPY pyproject.toml requirements.txt ./
COPY src/ ./src/
COPY configs/ ./configs/
COPY main.py run_agent.sh ./

# Create venv and install deps
RUN uv venv /opt/venv \
    && VIRTUAL_ENV=/opt/venv uv pip install -r requirements.txt \
    && VIRTUAL_ENV=/opt/venv uv pip install -e . 2>/dev/null || true

# ── Stage 2: Runtime ─────────────────────────────────────────
FROM python:${PYTHON_VERSION}-slim AS runtime

ARG GIT_SHA
ARG APP_VERSION
ARG BUILD_DATE

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    PATH="/opt/venv/bin:$PATH" \
    APP_VERSION=${APP_VERSION}

# Non-root user
RUN groupadd -r -g 10001 appgroup \
    && useradd -r -u 10001 -g appgroup --no-log-init appuser

WORKDIR /app

# Copy venv from builder
COPY --from=builder /opt/venv /opt/venv

# Copy application files
COPY --chown=appuser:appgroup main.py ./
COPY --chown=appuser:appgroup run_agent.sh ./
COPY --chown=appuser:appgroup src/ ./src/
COPY --chown=appuser:appgroup configs/ ./configs/
COPY --chown=appuser:appgroup policies/ ./policies/
COPY --chown=appuser:appgroup README.md ./
COPY --chown=appuser:appgroup LICENSE ./

# OCI Labels
LABEL org.opencontainers.image.title="devops-agent" \
      org.opencontainers.image.description="AI-powered multi-agent DevOps pipeline" \
      org.opencontainers.image.version="${APP_VERSION}" \
      org.opencontainers.image.revision="${GIT_SHA}" \
      org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.source="https://github.com/nithingowdahm87/devops_agent"

USER appuser

# The agent requires a project path as argument
ENTRYPOINT ["python3", "main.py"]
CMD ["--help"]
