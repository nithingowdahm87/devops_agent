"""Shared pytest fixtures for devops-agent tests."""

import os
import json
import tempfile
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.api.main import app
from src.db.database import Base, get_db

# Ensure all models are registered with Base.metadata before create_all
from src.db import models  # noqa: F401


# FastAPI test DB setup (shared across all API test modules)
_SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
_engine = create_engine(_SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
_TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)


def _override_get_db():
    db = _TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = _override_get_db

# Monkeypatch production SessionLocal so background tasks use test DB too
from src.db import database as _db_module
_db_module.SessionLocal = _TestingSessionLocal


@pytest.fixture(autouse=True)
def _setup_db():
    Base.metadata.create_all(bind=_engine)
    yield
    Base.metadata.drop_all(bind=_engine)


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    return TestClient(app)


@pytest.fixture
def mock_env(monkeypatch):
    """Set mock API keys so secrets module doesn't raise."""
    monkeypatch.setenv("GOOGLE_API_KEY", "test-google-key")
    monkeypatch.setenv("GROQ_API_KEY", "test-groq-key")
    monkeypatch.setenv("NVIDIA_API_KEY", "test-nvidia-key")


@pytest.fixture
def clean_env(monkeypatch):
    """Remove all API keys to test missing-key paths."""
    for key in ["GOOGLE_API_KEY", "GROQ_API_KEY", "NVIDIA_API_KEY", "GITHUB_TOKEN", "GITHUB_REPO"]:
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
