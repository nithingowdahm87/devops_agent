"""
Tests for CostEstimator — patched against call_llm (modern interface).
"""
import sys
import os
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.agents.cost_agent import CostEstimator


def test_cost_estimator_uses_prompt_file():
    """CostEstimator should call call_llm with KUBERNETES MANIFESTS in user prompt."""
    with patch("src.agents.cost_agent.call_llm", return_value="| Resource | Cost |") as mock_llm:
        estimator = CostEstimator()
        estimator.estimate("kind: Pod\nmetadata:\n  name: test")

        assert mock_llm.called
        # call_llm(system, user, task_type=...)
        _, user_prompt = mock_llm.call_args[0]
        assert "KUBERNETES MANIFESTS" in user_prompt


def test_cost_estimator_fallback():
    """CostEstimator should fall back to a hard-coded task string when file is missing."""
    with patch("src.agents.cost_agent.call_llm", return_value="Report") as mock_llm:
        with patch("src.agents.cost_agent.read_file", side_effect=Exception("File not found")):
            estimator = CostEstimator()
            estimator.estimate("yaml")

            assert mock_llm.called
            _, user_prompt = mock_llm.call_args[0]
            assert "Analyze these K8s manifests" in user_prompt
