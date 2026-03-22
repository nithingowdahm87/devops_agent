# -*- coding: utf-8 -*-
"""
Tests for Healer — patched against call_llm (modern interface).
"""
import pytest
from unittest.mock import patch, MagicMock
from src.engine.heal import Healer
from src.engine.models import GeneratedFile


def test_healer_basic_repair():
    """Healer.heal should call call_llm and return modified content."""
    with patch("src.engine.heal.call_llm", return_value="FROM node:20-alpine\nRUN ls") as mock_llm:
        healer = Healer()
        broken_content = "FROM node:latest\nRUN echo 'stub'"
        errors = ["PROD_POLICY_VIOLATION: Avoid using :latest tags in production."]

        file = GeneratedFile(path="Dockerfile", content=broken_content)
        healed = healer.heal(file, errors)

        assert mock_llm.called
        assert healed.content != broken_content


def test_healer_k8s_repair():
    """Healer.heal should embed fixed content returned by call_llm."""
    with patch("src.engine.heal.call_llm", return_value="replicas: 2\nrunAsNonRoot: true"):
        healer = Healer()
        file = GeneratedFile(path="k8s/deployment.yaml", content="replicas: 1")
        healed = healer.heal(file, ["Deployment replicas < 2"])

        assert "replicas: 2" in healed.content


def test_healer_no_op_on_empty_errors():
    """Healer.heal returns a valid GeneratedFile even when errors list is empty."""
    with patch("src.engine.heal.call_llm", return_value="VALID CONTENT"):
        healer = Healer()
        file = GeneratedFile(path="test.txt", content="VALID CONTENT")
        healed = healer.heal(file, [])

        assert healed.path == "test.txt"
