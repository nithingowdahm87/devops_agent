# -*- coding: utf-8 -*-
import os
import pytest
from src.engine.fallbacks import write_fallbacks, FALLBACK_DIR

def test_fallback_generation(tmp_path):
    """Verify that fallback templates are correctly written and valid."""
    # We use the real fallbacks.py logic
    write_fallbacks()
    
    assert os.path.exists(os.path.join(FALLBACK_DIR, "Dockerfile"))
    assert os.path.exists(os.path.join(FALLBACK_DIR, "docker-compose.yml"))
    assert os.path.exists(os.path.join(FALLBACK_DIR, "k8s-deployment.yaml"))
    
    with open(os.path.join(FALLBACK_DIR, "Dockerfile"), "r", encoding="utf-8") as f:
        content = f.read()
        assert "FROM node:20-alpine" in content
        assert "USER node" in content # Best practice preserved in fallback
