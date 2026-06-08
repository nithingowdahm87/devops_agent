"""
Kimchi CLI API Client — OpenAI-compatible endpoint.

Uses the Kimchi dev LLM API at https://llm.kimchi.dev/openai/v1
Auth token is read from $KIMCHI_API_KEY or ~/.config/kimchi/harness/auth.json
"""
from __future__ import annotations
import json
import os
from pathlib import Path


def _get_kimchi_api_key() -> str:
    """Resolve Kimchi API key from env or auth.json."""
    env_key = os.environ.get("KIMCHI_API_KEY", "").strip()
    if env_key:
        return env_key

    auth_paths = [
        Path.home() / ".config" / "kimchi" / "harness" / "auth.json",
        Path.home() / ".local" / "share" / "kimchi" / "auth.json",
    ]
    for path in auth_paths:
        if path.exists():
            try:
                data = json.loads(path.read_text())
                token = data.get("kimchi-dev", {}).get("access", "")
                if token:
                    return token
            except Exception:
                continue
    raise RuntimeError(
        "KIMCHI_API_KEY not set and auth.json not found. "
        "Log in with `kimchi login` or set KIMCHI_API_KEY."
    )


class KimchiClient:
    """LLM Client for Kimchi CLI API (OpenAI-compatible)."""

    def __init__(self, model: str = "kimi-k2.6", temperature: float = 0.1):
        self.api_key = _get_kimchi_api_key()
        self.model = model
        self.temperature = temperature
        self.base_url = "https://llm.kimchi.dev/openai/v1"

    def call(self, prompt: str) -> str:
        from openai import OpenAI

        client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        # Stream to keep Cloudflare proxy connection alive (>120s generation)
        stream = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are an elite DevOps Engineering Assistant."},
                {"role": "user", "content": prompt},
            ],
            temperature=self.temperature,
            max_tokens=4096,
            timeout=300,
            stream=True,
        )
        parts: list[str] = []
        for chunk in stream:
            delta = chunk.choices[0].delta
            text = delta.content
            if text:
                parts.append(text)
        content = "".join(parts)
        if not content:
            return ""
        return content.strip()
