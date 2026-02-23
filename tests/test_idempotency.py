# -*- coding: utf-8 -*-
import pytest
from src.engine.idempotency import IdempotencyEngine

def test_yaml_idempotency():
    """Verify YAML keys are sorted and formatting is stable."""
    unsorted_yaml = "services:\n  web:\n    image: nginx\n  db:\n    image: postgres"
    # db is before web in alpha order
    
    stabilized = IdempotencyEngine.stabilize_yaml(unsorted_yaml)
    assert "db:" in stabilized.splitlines()[1] # First service after root
    
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
