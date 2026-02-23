"""Shared pytest fixtures for devops-agent tests."""

import os
import json
import tempfile
import pytest


@pytest.fixture
def mock_env(monkeypatch):
    """Set mock API keys so secrets module doesn't raise."""
    monkeypatch.setenv("GOOGLE_API_KEY", "test-google-key")
    monkeypatch.setenv("GROQ_API_KEY", "test-groq-key")
    monkeypatch.setenv("NVIDIA_API_KEY", "test-nvidia-key")


@pytest.fixture
def clean_env(monkeypatch):
    """Remove all API keys to test missing-key paths."""
                 "GITHUB_TOKEN", "GITHUB_REPO"]:
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
