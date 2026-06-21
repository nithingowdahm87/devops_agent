#!/usr/bin/env python3
"""One-shot DB initialization script for production deployments.

Usage:
    python scripts/init_db.py

Runs SQLAlchemy create_all and Alembic migrations. Intended to be
executed as a K8s init container or one-shot job before app startup.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from src.db.database import engine, Base


def init_db():
    """Create tables and run Alembic migrations."""
    print("Creating database tables if missing...")
    Base.metadata.create_all(bind=engine)

    print("Running Alembic migrations...")
    import alembic.config
    import alembic.command
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cfg = alembic.config.Config(os.path.join(base_dir, "alembic.ini"))
    alembic.command.upgrade(cfg, "head")
    print("Database initialized successfully.")


if __name__ == "__main__":
    init_db()
