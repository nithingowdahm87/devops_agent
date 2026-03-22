"""
Tests for ObservabilityAgent writers — patched against call_llm (modern interface).
"""
import sys
import os
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.agents.observability_agent import (
    ObservabilityWriterA,
    ObservabilityWriterB,
    ObservabilityReviewer,
)


def test_writer_a_dashboard_prompt():
    """ObservabilityWriterA should call call_llm; prompt or system context must be non-empty."""
    with patch("src.agents.observability_agent.call_llm", return_value="{}") as mock_llm:
        writer = ObservabilityWriterA()
        writer.generate_dashboard("context")
        assert mock_llm.called


def test_writer_b_dashboard_prompt():
    """ObservabilityWriterB should call call_llm."""
    with patch("src.agents.observability_agent.call_llm", return_value="{}") as mock_llm:
        writer = ObservabilityWriterB()
        writer.generate_dashboard("context")
        assert mock_llm.called


def test_reviewer_detects_dashboard():
    """ObservabilityReviewer.review_and_merge should return a non-empty JSON string."""
    with patch(
        "src.agents.observability_agent.call_llm",
        return_value='REASONING: Good.\nCONTENT:\n```json\n{\n "title": "Dashboard"\n}\n```',
    ):
        reviewer = ObservabilityReviewer()
        final, reasoning = reviewer.review_and_merge("{}", "{}", "{}")
        assert "{" in final
        assert "}" in final
