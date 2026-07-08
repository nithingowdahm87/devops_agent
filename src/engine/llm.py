"""
NVIDIA LLM Client — Single provider for DevOps Agent.

Configure via env vars:
  NVIDIA_API_KEY=your_key_here
  NVIDIA_MODEL=meta/llama-3.1-405b-instruct (optional)
"""

from __future__ import annotations
import os
import time
import logging
import random
from typing import Optional

log = logging.getLogger(__name__)

# NVIDIA NIM endpoint
_NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1/chat/completions"


def _e(k: str, d: str = "") -> str:
    return os.environ.get(k, d).strip()


def _get_nvidia_model() -> str:
    return _e("NVIDIA_MODEL", "meta/llama-3.1-405b-instruct")


def call_llm(
    system_prompt: str,
    user_prompt: str,
    task_type: str = "default",
    max_tokens_budget: int = 8192,
) -> str:
    """Call NVIDIA LLM with retry logic."""
    api_key = _e("NVIDIA_API_KEY")
    if not api_key:
        raise RuntimeError(
            "NVIDIA_API_KEY not set. Configure NVIDIA API key to use the agent."
        )

    model = _get_nvidia_model()
    temperature = float(_e("LLM_TEMPERATURE", "0.1"))
    env_max = int(os.environ.get("LLM_MAX_TOKENS", "8192"))
    max_tokens = min(max_tokens_budget, env_max)
    timeout = int(_e("LLM_TIMEOUT_SECONDS", "180"))
    max_retries = int(_e("LLM_MAX_RETRIES", "3"))
    errors: list[str] = []

    import requests

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    full_prompt = f"{system_prompt}\n\n{user_prompt}" if system_prompt else user_prompt

    for attempt in range(1, max_retries + 1):
        try:
            log.info("LLM → NVIDIA [task=%s] attempt %d/%d", task_type, attempt, max_retries)
            data = {
                "model": model,
                "messages": [
                    {"role": "system", "content": "You are an elite DevOps Engineering Assistant."},
                    {"role": "user", "user", "content": full_prompt},
                ],
                "temperature": temperature,
                "max_tokens": max_tokens,
                "top_p": 0.7,
            }
            resp = requests.post(_NVIDIA_BASE_URL, headers=headers, json=data, timeout=timeout)

            if resp.status_code != 200:
                log.warning("NVIDIA API Error: %s - %s", resp.status_code, resp.text)
                resp.raise_for_status()

            result = resp.json()["choices"][0]["message"]["content"]
            log.info("LLM ✓ NVIDIA")
            return result.strip()

        except Exception as exc:
            wait = (2 ** attempt) + random.uniform(0, 5)
            msg = f"NVIDIA attempt {attempt}/{max_retries}: {exc}"
            errors.append(msg)
            log.warning("%s — retry in %.1fs", msg, wait)
            if attempt < max_retries:
                time.sleep(wait)

    raise RuntimeError("NVIDIA LLM failed after all retries:\n" + "\n".join(f"  • {e}" for e in errors))