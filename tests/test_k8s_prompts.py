"""
Tests for K8s agent writers — patched against call_llm (modern interface).
"""
import sys
import os
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.agents.k8s_agents import K8sWriterA, K8sWriterB, K8sWriterC


def test_k8s_writer_a_context_includes_istio():
    """K8sWriterA.generate should call call_llm; its prompt file references Istio."""
    with patch("src.agents.k8s_agents.call_llm", return_value="yaml") as mock_llm:
        writer = K8sWriterA()
        writer.generate("context")
        assert mock_llm.called
        # The user prompt (2nd positional arg) should include Istio keywords
        user_prompt = mock_llm.call_args[0][1]
        assert "Istio" in user_prompt or "VirtualService" in user_prompt


def test_k8s_writer_b_context_includes_network_policy():
    """K8sWriterB.generate should call call_llm; its prompt references NetworkPolicy."""
    with patch("src.agents.k8s_agents.call_llm", return_value="yaml") as mock_llm:
        writer = K8sWriterB()
        writer.generate("context")
        assert mock_llm.called
        user_prompt = mock_llm.call_args[0][1]
        assert "NetworkPolicy" in user_prompt or "Deny-All" in user_prompt


def test_k8s_writer_c_context_includes_ha():
    """K8sWriterC.generate should call call_llm; its prompt references HA/Topology."""
    with patch("src.agents.k8s_agents.call_llm", return_value="yaml") as mock_llm:
        writer = K8sWriterC()
        writer.generate("context")
        assert mock_llm.called
        user_prompt = mock_llm.call_args[0][1]
        assert "Topology Spread" in user_prompt or "highly-available" in user_prompt
