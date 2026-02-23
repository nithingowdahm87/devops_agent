import sys
import os
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.agents.observability_agent import ObservabilityWriterA, ObservabilityWriterB, ObservabilityWriterC, ObservabilityReviewer

def test_writer_a_dashboard_prompt():
    with patch("src.agents.observability_agent.GeminiClient") as MockClient:
        mock_llm = MockClient.return_value
        mock_llm.call.return_value = "{}"
        
        writer = ObservabilityWriterA()
        # Should now use the unified prompt from file
        writer.generate_dashboard("context")
        
        args, _ = mock_llm.call.call_args
        prompt = args[0]
        # Validates it loaded the file content
        assert "Monitoring Expert" in prompt
        assert "Grafana Dashboard" in prompt

def test_writer_b_dashboard_prompt():
    with patch("src.agents.observability_agent.GroqClient") as MockClient:
        mock_llm = MockClient.return_value
        mock_llm.call.return_value = "{}"
        
        writer = ObservabilityWriterB()
        writer.generate_dashboard("context")
        
        args, _ = mock_llm.call.call_args
        prompt = args[0]
        # Unified prompt uses "Monitoring Expert"
        assert "Monitoring Expert" in prompt
        assert "USE Method" in prompt

def test_reviewer_detects_dashboard():
    # Patch where it is defined since it is imported locally inside __init__
        mock_llm = MockClient.return_value
        mock_llm.call.return_value = "REASONING: Good.\nCONTENT:\n```json\n{\n \"title\": \"Dashboard\"\n}\n```"
        
        reviewer = ObservabilityReviewer()
        final, reasoning = reviewer.review_and_merge("{}", "{}", "{}")
        assert "{" in final
        assert "}" in final
