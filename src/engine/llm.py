"""
LLM Router — llama.cpp local provider.

Uses a single OpenAI-compatible endpoint exposed by llama-server at
http://127.0.0.1:8080/v1/chat/completions.

To use:
  1. Build llama.cpp and run:
       llama-server -m ~/models/qwen-coder-1.5b.gguf \
         --host 127.0.0.1 --port 8080 -c 4096 -t 4
  2. Set LLAMACPP_MODEL in .env to the model id (check GET /v1/models)
"""

from __future__ import annotations
import os
import time
import logging
import socket
import random

log = logging.getLogger(__name__)

# ── Single base URL for local llama.cpp ──────────────────────────────────────
_BASES = {
    "llamacpp": "http://127.0.0.1:8080/v1",
}

def _e(k: str, d: str = "") -> str:
    return os.environ.get(k, d).strip()

# ── Minimal task routing (kept for API compatibility) ─────────────────────────
# All task types resolve to the same single provider: "llamacpp".
_TASK_ROUTES = {
    "docker":          ["llamacpp"],
    "k8s":             ["llamacpp"],
    "cicd":            ["llamacpp"],
    "github_actions":  ["llamacpp"],
    "gitops_manifests":["llamacpp"],
    "heal":            ["llamacpp"],
    "critique":        ["llamacpp"],
    "default":         ["llamacpp"],
}

def _cfg(task_type: str = "default") -> dict:
    """
    Configuration for the single llama.cpp provider.

    LLAMACPP_MODEL is passed directly to llama-server's /v1/chat/completions
    endpoint.  The model id must match what GET /v1/models returns (usually the
    GGUF filename stem, e.g. "qwen-coder-1.5b.gguf").
    Any non-empty LLAMACPP_API_KEY works; llama-server ignores it but the
    OpenAI client requires a value.
    """
    return {
        "llamacpp": {
            "api_key":  _e("LLAMACPP_API_KEY", "none"),
            "model":    _e("LLAMACPP_MODEL", "qwen-coder-1.5b.gguf"),
            "base_url": _BASES["llamacpp"],
        },
    }

# ── Health check ──────────────────────────────────────────────────────────────
def _is_healthy() -> bool:
    """
    llama.cpp health check.

    Returns True if a TCP connection to 127.0.0.1:8080 can be established,
    i.e. llama-server is running.
    """
    try:
        socket.create_connection(("127.0.0.1", 8080), timeout=1)
        return True
    except OSError:
        return False

# ── Caller implementation (OpenAI-compatible) ─────────────────────────────────
def _call_openai_compat(cfg, system, user, temperature, max_tokens, timeout):
    """
    Generic OpenAI-compatible caller used for llama.cpp.

    llama-server exposes a drop-in /v1/chat/completions endpoint.
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
    "llamacpp": _call_openai_compat,
}

# ── Public API ────────────────────────────────────────────────────────────────
def call_llm(
    system_prompt: str,
    user_prompt: str,
    task_type: str = "default",
    max_tokens_budget: int = 1024,
) -> str:
    """
    Call local llama.cpp with a task-aware interface.

    task_type is kept for backward compatibility with previous multi-provider
    routing, but all routes now resolve to the single "llamacpp" provider.
    """

    order = _TASK_ROUTES.get(task_type, _TASK_ROUTES["default"])
    temperature = float(_e("LLM_TEMPERATURE", "0.1"))

    # Respect user-configured token cap
    env_max = int(os.environ.get("LLM_MAX_TOKENS", "512"))
    max_tokens = min(max_tokens_budget, env_max)

    timeout = int(_e("LLM_TIMEOUT_SECONDS", "90"))
    max_retries = int(_e("LLM_MAX_RETRIES", "2"))

    cfg_map = _cfg(task_type)
    errors: list[str] = []

    if not _is_healthy():
        raise RuntimeError(
            "llama-server is not reachable on 127.0.0.1:8080.\n"
            "Start it with:\n"
            "  llama-server -m ~/models/qwen-coder-1.5b.gguf \\\n"
            "    --host 127.0.0.1 --port 8080 -c 4096 -t 4"
        )

    provider = "llamacpp"
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
            wait = (2 ** attempt) + random.uniform(0, 5)  # jitter
            msg = f"{provider} attempt {attempt}/{max_retries}: {exc}"
            errors.append(msg)
            log.warning("%s — retry in %.1fs", msg, wait)
            if attempt < max_retries:
                time.sleep(wait)

    raise RuntimeError("llama.cpp failed:\n" + "\n".join(f"  • {e}" for e in errors))
