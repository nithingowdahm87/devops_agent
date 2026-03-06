"""
LLM Router — Ollama-only local provider.

Uses a single OpenAI-compatible endpoint exposed by Ollama at
http://localhost:11434/v1/chat/completions.

To use:
  1. Install Ollama:  curl -fsSL https://ollama.com/install.sh | sh
  2. Pull a small model (good for 8 GB RAM):
       ollama pull llama3.2:3b
  3. Set OLLAMA_MODEL in .env (e.g. llama3.2:3b)
"""

from __future__ import annotations
import os
import time
import logging
import socket

log = logging.getLogger(__name__)

# ── Single base URL for local Ollama ───────────────────────────────────────────
_BASES = {
    "ollama": "http://localhost:11434/v1",
}

def _e(k: str, d: str = "") -> str:
    return os.environ.get(k, d).strip()

# ── Minimal task routing (kept for API compatibility) ─────────────────────────
# All task types resolve to the same single provider: "ollama".
_TASK_ROUTES = {
    "docker":          ["ollama"],
    "k8s":             ["ollama"],
    "cicd":            ["ollama"],
    "github_actions":  ["ollama"],
    "gitops_manifests":["ollama"],
    "heal":            ["ollama"],
    "critique":        ["ollama"],
    "default":         ["ollama"],
}

def _cfg(task_type: str = "default") -> dict:
    """
    Configuration for the single Ollama provider.

    OLLAMA_MODEL is passed directly to Ollama's /v1/chat/completions endpoint.
    Any non-empty OLLAMA_API_KEY works; Ollama ignores it but the OpenAI client
    requires a value.
    """
    return {
        "ollama": {
            "api_key":  _e("OLLAMA_API_KEY", "ollama"),
            "model":    _e("OLLAMA_MODEL", "llama3.2:3b"),
            "base_url": _BASES["ollama"],
        },
    }

# ── Health check ───────────────────────────────────────────────────────────────
def _is_healthy() -> bool:
    """
    Ollama-specific health check.

    Returns True if a TCP connection to localhost:11434 can be established.
    """
    try:
        socket.create_connection(("127.0.0.1", 11434), timeout=1)
        return True
    except OSError:
        return False

# ── Caller implementation (OpenAI-compatible) ─────────────────────────────────
def _call_openai_compat(cfg, system, user, temperature, max_tokens, timeout):
    """
    Generic OpenAI-compatible caller used for Ollama.

    Ollama exposes a drop-in /v1/chat/completions endpoint.
    """
    from openai import OpenAI

    client = OpenAI(api_key=cfg["api_key"], base_url=cfg["base_url"])
    resp = client.chat.completions.create(
        model=cfg["model"],
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout,
    )
    return resp.choices[0].message.content.strip()

_CALLERS = {
    "ollama": _call_openai_compat,
}

# ── Public API ────────────────────────────────────────────────────────────────
def call_llm(
    system_prompt: str,
    user_prompt: str,
    task_type: str = "default",
    max_tokens_budget: int = 1024,
) -> str:
    """
    Call local Ollama with a task-aware interface.

    task_type is kept for backward compatibility with previous multi-provider
    routing, but all routes now resolve to the single "ollama" provider.
    """

    order = _TASK_ROUTES.get(task_type, _TASK_ROUTES["default"])
    temperature = float(_e("LLM_TEMPERATURE", "0.1"))

    # Respect user-configured token cap
    env_max = int(os.environ.get("LLM_MAX_TOKENS", "1024"))
    max_tokens = min(max_tokens_budget, env_max)

    timeout = int(_e("LLM_TIMEOUT_SECONDS", "45"))
    max_retries = int(_e("LLM_MAX_RETRIES", "3"))

    cfg_map = _cfg(task_type)
    errors: list[str] = []

    if not _is_healthy():
        raise RuntimeError(
            "Ollama server is not reachable on localhost:11434.\n"
            "Start it with:  ollama serve  (or run any model once, e.g. "
            "`ollama run llama3.2:3b`)."
        )

    provider = "ollama"
    cfg = cfg_map[provider]
    caller = _CALLERS[provider]

    for attempt in range(1, max_retries + 1):
        try:
            log.info(
                "LLM → %s [task=%s] attempt %d/%d",
                provider,
                task_type,
                attempt,
                max_retries,
            )
            result = caller(cfg, system_prompt, user_prompt, temperature, max_tokens, timeout)
            log.info("LLM ✓ %s", provider)
            return result
        except Exception as exc:
            wait = 2 ** attempt
            msg = f"{provider} attempt {attempt}/{max_retries}: {exc}"
            errors.append(msg)
            log.warning("%s — retry in %ds", msg, wait)
            if attempt < max_retries:
                time.sleep(wait)

    raise RuntimeError("Ollama failed:\n" + "\n".join(f"  • {e}" for e in errors))
