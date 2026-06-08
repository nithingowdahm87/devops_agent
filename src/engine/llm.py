"""
LLM Router — supports API key providers + local llama.cpp.

Providers: groq, gemini, cerebras, nvidia, openrouter, llamacpp
Configure via env vars (see .env.example):
  LLM_PRIMARY=groq
  LLM_FALLBACK_ORDER=gemini,cerebras

Local llama.cpp remains available as a fallback:
  llama-server -m ~/models/qwen-coder-1.5b.gguf \
    --host 127.0.0.1 --port 8080 -c 4096 -t 4
"""

from __future__ import annotations
import os
import time
import logging
import socket
import random

log = logging.getLogger(__name__)

# ── Base URLs ────────────────────────────────────────────────────────────────
_BASES = {
    "llamacpp": "http://127.0.0.1:8080/v1",
}

def _e(k: str, d: str = "") -> str:
    return os.environ.get(k, d).strip()

# ── Provider defaults ─────────────────────────────────────────────────────────
_PROVIDER_MODELS = {
    "groq":       "llama-3.3-70b-versatile",
    "gemini":     "gemini-2.0-flash-exp",
    "cerebras":   "llama3.1-8b",
    "nvidia":     "meta/llama-3.1-405b-instruct",
    "openrouter": "deepseek/deepseek-r1-0528:free",
    "llamacpp":   _e("LLAMACPP_MODEL", "qwen-coder-1.5b.gguf"),
    "kimchi":     _e("KIMCHI_MODEL", "kimi-k2.6"),
}

# ── Task routing defaults ─────────────────────────────────────────────────────
_TASK_ROUTES = {
    "docker":           ["groq", "gemini", "cerebras"],
    "k8s":              ["groq", "gemini", "cerebras"],
    "cicd":             ["groq", "gemini", "cerebras"],
    "github_actions":   ["groq", "gemini", "cerebras"],
    "gitops_manifests": ["groq", "gemini", "cerebras"],
    "heal":             ["groq", "gemini", "cerebras"],
    "critique":         ["groq", "gemini", "cerebras"],
    "default":          ["groq", "gemini", "cerebras"],
}

# ── llamacpp config ───────────────────────────────────────────────────────────
def _get_llamacpp_cfg() -> dict:
    return {
        "api_key":  _e("LLAMACPP_API_KEY", "none"),
        "model":    _e("LLAMACPP_MODEL", _PROVIDER_MODELS["llamacpp"]),
        "base_url": _BASES["llamacpp"],
    }

# ── Provider order resolution ─────────────────────────────────────────────────
def _provider_name_from_env(task_type: str = "default") -> list[str]:
    """Return ordered provider list for this task."""
    primary = _e("LLM_PRIMARY", "").lower()
    fallback = [p.strip() for p in _e("LLM_FALLBACK_ORDER", "").split(",") if p.strip()]
    task_defaults = _TASK_ROUTES.get(task_type, _TASK_ROUTES["default"])
    order: list[str] = []
    if primary and primary in _PROVIDER_MODELS:
        order.append(primary)
    order.extend(fallback)
    for p in task_defaults:
        if p not in order:
            order.append(p)
    return order

# ── Health check (llama.cpp only) ─────────────────────────────────────────────
def _is_llamacpp_healthy() -> bool:
    try:
        socket.create_connection(("127.0.0.1", 8080), timeout=1)
        return True
    except OSError:
        return False

# ── OpenAI-compatible caller for llamacpp ─────────────────────────────────────
def _call_openai_compat(cfg, system, user, temperature, max_tokens, timeout):
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

# ── API client router ─────────────────────────────────────────────────────────
def _call_api_client(provider: str, system: str, user: str, temperature: float,
                     max_tokens: int, timeout: int) -> str:
    """Route to existing src.llm_clients client classes."""
    full_prompt = f"{system}\n\n{user}" if system else user

    if provider == "gemini":
        from src.llm_clients.gemini_client import GeminiClient
        client = GeminiClient(
            model=_e("GEMINI_MODEL", _PROVIDER_MODELS["gemini"]),
            temperature=temperature,
        )
    elif provider == "groq":
        from src.llm_clients.groq_client import GroqClient
        client = GroqClient(
            model=_e("GROQ_MODEL", _PROVIDER_MODELS["groq"]),
            temperature=temperature,
        )
    elif provider == "nvidia":
        from src.llm_clients.nvidia_client import NvidiaClient
        client = NvidiaClient(
            model=_e("NVIDIA_MODEL", _PROVIDER_MODELS["nvidia"]),
            temperature=temperature,
        )
    elif provider == "cerebras":
        from src.llm_clients.cerebras_client import CerebrasClient
        client = CerebrasClient(
            model=_e("CEREBRAS_MODEL", _PROVIDER_MODELS["cerebras"]),
            temperature=temperature,
        )
    elif provider == "openrouter":
        from src.llm_clients.openrouter_client import OpenRouterClient
        client = OpenRouterClient(
            model=_e("OPENROUTER_MODEL", _PROVIDER_MODELS["openrouter"]),
            temperature=temperature,
        )
    elif provider == "kimchi":
        from src.llm_clients.kimchi_client import KimchiClient
        client = KimchiClient(
            model=_e("KIMCHI_MODEL", _PROVIDER_MODELS["kimchi"]),
            temperature=temperature,
        )
    elif provider == "llamacpp":
        cfg = _get_llamacpp_cfg()
        return _call_openai_compat(cfg, system, user, temperature, max_tokens, timeout)
    else:
        raise RuntimeError(f"Unknown provider: {provider}")

    result = client.call(full_prompt)

    # Post-process: strip reasoning/explanation text before the first code block or FILENAME
    # Models sometimes output "I will generate a Dockerfile..." before the actual code.
    lines = result.splitlines()
    cut_idx = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("FILENAME:") or stripped.startswith("```"):
            cut_idx = i
            break
        # Kimchi/minimax sometimes outputs reasoning in sentences before code
        # Heuristic: if we see "The user wants" or similar meta-text, skip those lines
        lower = stripped.lower()
        if lower.startswith("the user wants") or lower.startswith("i need to") or lower.startswith("here is"):
            cut_idx = i + 1
    if cut_idx > 0:
        result = "\n".join(lines[cut_idx:])
    return result.strip()

# ── Caller map ────────────────────────────────────────────────────────────────
_CALLERS: dict[str, callable] = {}
for _pname in list(_PROVIDER_MODELS.keys()):
    _CALLERS[_pname] = lambda s, u, t, m, to, p=_pname: _call_api_client(p, s, u, t, m, to)

# ── Public API ────────────────────────────────────────────────────────────────
def call_llm(
    system_prompt: str,
    user_prompt: str,
    task_type: str = "default",
    max_tokens_budget: int = 1024,
) -> str:
    """Call LLM with provider routing and fallback."""
    providers = _provider_name_from_env(task_type)
    temperature = float(_e("LLM_TEMPERATURE", "0.1"))
    env_max = int(os.environ.get("LLM_MAX_TOKENS", "256"))
    max_tokens = min(max_tokens_budget, env_max)
    timeout = int(_e("LLM_TIMEOUT_SECONDS", "180"))
    max_retries = int(_e("LLM_MAX_RETRIES", "1"))
    errors: list[str] = []

    for provider in providers:
        caller = _CALLERS.get(provider)
        if not caller:
            continue
        if provider == "llamacpp" and not _is_llamacpp_healthy():
            errors.append("llamacpp: server not reachable on 127.0.0.1:8080")
            continue

        for attempt in range(1, max_retries + 1):
            try:
                log.info(
                    "LLM → %s [task=%s] attempt %d/%d",
                    provider, task_type, attempt, max_retries,
                )
                result = caller(system_prompt, user_prompt, temperature, max_tokens, timeout)
                log.info("LLM ✓ %s", provider)
                return result
            except Exception as exc:
                wait = (2 ** attempt) + random.uniform(0, 5)
                msg = f"{provider} attempt {attempt}/{max_retries}: {exc}"
                errors.append(msg)
                log.warning("%s — retry in %.1fs", msg, wait)
                if attempt < max_retries:
                    time.sleep(wait)

    raise RuntimeError("All LLM providers failed:\n" + "\n".join(f"  • {e}" for e in errors))
