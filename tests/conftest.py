"""Shared pytest fixtures for devops-agent tests (CLI-only)."""

import os
import json
import tempfile
import pytest

# Test fixtures only - no FastAPI/SQLAlchemy dependencies needed for CLI tool


@pytest.fixture
def mock_env(monkeypatch):
    """Set mock API keys so NVIDIA client doesn't raise."""
    monkeypatch.setenv("NVIDIA_API_KEY", "test-nvidia-key")
    monkeypatch.setenv("NVIDIA_MODEL", "meta/llama-3.1-405b-instruct")
    monkeypatch.setenv("PIPELINE_ENV", "dev")
    monkeypatch.setenv("LOG_JSON", "false")


@pytest.fixture
def clean_env(monkeypatch):
    """Remove all API keys to test missing-key paths."""
    for key in ["NVIDIA_API_KEY", "NVIDIA_MODEL"]:
        monkeypatch.delenv(key, raising=False)


@pytest.fixture
def tmp_project(tmp_path):
    """Create a minimal Node.js project in a temp directory."""
    pkg = {
        "name": "test-app",
        "version": "1.0.0",
        "dependencies": {"express": "^4.18.0"},
        "scripts": {"start": "node server.js"},
    }
    (tmp_path / "package.json").write_text(json.dumps(pkg))
    (tmp_path / "server.js").write_text(
        "const express = require('express');\n"
        "const app = express();\n"
        "app.listen(3000);\n"
    )
    return tmp_path


@pytest.fixture
def mock_context():
    """Return a valid ProjectContext dict."""
    return {
        "project_name": "test-app",
        "language": "javascript/node",
        "frameworks": ["express"],
        "dependencies": ["express"],
        "ports": ["3000"],
        "env_vars": ["MONGO_URI"],
    }


@pytest.fixture
def sample_dockerfile():
    """Valid multi-stage Dockerfile for testing."""
    return '''FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci --ignore-scripts && npm cache clean --force

FROM node:20-alpine AS runtime
RUN addgroup -g 10001 -S appgroup && adduser -u 10001 -S appuser -G appgroup
WORKDIR /app
COPY --from=builder --chown=root:root /app/node_modules ./node_modules
COPY --from=builder --chown=root:root /app/dist ./dist
USER appuser
ENV NODE_ENV=production
EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 CMD node -e "require('http').get('http://localhost:3000/health',(r)=>{process.exit(r.statusCode===200?0:1)}).on('error',()=>process.exit(1))"
CMD ["node", "dist/index.js"]'''


@pytest.fixture
def sample_k8s_manifest():
    """Valid K8s deployment manifest for testing."""
    return '''apiVersion: apps/v1
kind: Deployment
metadata:
  name: test-app
  namespace: default
spec:
  replicas: 2
  selector:
    matchLabels:
      app: test-app
  template:
    metadata:
      labels:
        app: test-app
    spec:
      securityContext:
        runAsNonRoot: true
        runAsUser: 10001
        fsGroup: 10001
        seccompProfile:
          type: RuntimeDefault
      containers:
      - name: test-app
        image: test-app:latest
        ports:
        - containerPort: 3000
        resources:
          requests:
            cpu: "250m"
            memory: "256Mi"
          limits:
            cpu: "500m"
            memory: "512Mi"
        livenessProbe:
          httpGet:
            path: /health
            port: 3000
          periodSeconds: 10
          failureThreshold: 3
        readinessProbe:
          httpGet:
            path: /ready
            port: 3000
          periodSeconds: 5
          failureThreshold: 3
        securityContext:
          allowPrivilegeEscalation: false
          readOnlyRootFilesystem: true
          capabilities:
            drop: ["ALL"]
        volumeMounts:
        - name: tmp
          mountPath: /tmp
        - name: var-run
          mountPath: /var/run
      volumes:
      - name: tmp
        emptyDir: {}
      - name: var-run
        emptyDir: {}'''


@pytest.fixture
def sample_github_actions():
    """Valid GitHub Actions workflow for testing."""
    return '''name: CI/CD Pipeline

on:
  push:
    branches: [main, master]
  pull_request:
    branches: [main, master]

permissions:
  contents: read
  id-token: write
  security-events: write

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

jobs:
  compile:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: npm
      - run: npm ci && npm run build

  trivy-fs:
    runs-on: ubuntu-latest
    needs: [compile]
    steps:
      - uses: actions/checkout@v4
      - uses: aquasecurity/trivy-action@master
        with:
          scan-type: fs
          scan-ref: .
          format: sarif
          output: trivy-fs.sarif
      - uses: github/codeql-action/upload-sarif@v3
        if: always()
        with:
          sarif_file: trivy-fs.sarif'''