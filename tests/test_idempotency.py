# -*- coding: utf-8 -*-
import pytest
from src.engine.idempotency import IdempotencyEngine

def test_yaml_idempotency():
    """Verify YAML key order is preserved and formatting is stable."""
    unsorted_yaml = "services:\n  web:\n    image: nginx\n  db:\n    image: postgres"
    # Original order: web first, then db
    
    stabilized = IdempotencyEngine.stabilize_yaml(unsorted_yaml)
    assert "web:" in stabilized.splitlines()[1] # First service after root preserves original order
    
    # Run twice should be identical
    stabilized_2 = IdempotencyEngine.stabilize_yaml(stabilized)
    assert stabilized == stabilized_2

def test_dockerfile_normalization():
    """Verify Dockerfile instructions are normalized to uppercase."""
    raw = "from node:20\nworkdir /app\ncopy . ."
    stabilized = IdempotencyEngine.stabilize_dockerfile(raw)
    
    assert "FROM node:20" in stabilized
    assert "WORKDIR /app" in stabilized
    assert "COPY . ." in stabilized
