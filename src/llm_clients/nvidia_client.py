"""
NVIDIA LLM Client — Wrapper for DevOps Agent.

Configure via env vars:
  NVIDIA_API_KEY=your_key_here
  NVIDIA_MODEL=meta/llama-3.1-405b-instruct (optional)
"""

from __future__ import annotations
import os
from src.engine.llm import call_llm


class NvidiaClient:
    """Thin wrapper around call_llm for compatibility with LLMGenerator."""

    def __init__(self, model: str = "meta/llama-3.1-405b-instruct", temperature: float = 0.1):
        self.model = model
        self.temperature = temperature
        # Validate API key exists
        api_key = os.environ.get("NVIDIA_API_KEY")
        if not api_key:
            raise RuntimeError("NVIDIA_API_KEY not set. Configure NVIDIA API key to use the agent.")

    def call(self, prompt: str) -> str:
        """Call NVIDIA LLM via the unified call_llm function."""
        # The prompt here is the full prompt (system + user combined)
        # call_llm expects system_prompt and user_prompt separately
        # For compatibility, we treat the whole prompt as user_prompt
        # and use a minimal system prompt
        return call_llm(
            system_prompt="You are an elite DevOps Engineering Assistant.",
            user_prompt=prompt,
            task_type="default",
            max_tokens_budget=8192,
        )