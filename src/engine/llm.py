"""
LLM Router — 8-provider fallback chain with exponential backoff.
Provider order: Groq → NVIDIA → Cerebras → OpenRouter → HuggingFace → OpenAI → Gemini → Ollama
"""
from __future__ import annotations
import os, time, logging
log = logging.getLogger(__name__)

_BASES = {
    "groq":        "https://api.groq.com/openai/v1",
    "nvidia":      "https://integrate.api.nvidia.com/v1",
    "cerebras":    "https://api.cerebras.ai/v1",
    "openrouter":  "https://openrouter.ai/api/v1",
    "huggingface": "https://router.huggingface.co/hf-inference/v1",
    "openai":      "https://api.openai.com/v1",
    "ollama":      "http://localhost:11434/v1",  # Local Ollama server
}

# ── Task-based model routing ──────────────────────────────────────────────────
# Each task type gets the best provider first, then falls back automatically.
# Ollama is always last — local safety net when all clouds fail.
_TASK_ROUTES = {
    "docker":          ["groq", "nvidia", "cerebras", "openrouter", "huggingface", "openai", "gemini", "ollama"],
    "k8s":             ["groq", "nvidia", "cerebras", "openrouter", "huggingface", "openai", "gemini", "ollama"],
    "ci":              ["groq", "nvidia", "cerebras", "openrouter", "huggingface", "openai", "gemini", "ollama"],
    "cicd":            ["groq", "nvidia", "cerebras", "openrouter", "huggingface", "openai", "gemini", "ollama"],
    "github_actions":  ["groq", "nvidia", "cerebras", "openrouter", "huggingface", "openai", "gemini", "ollama"],
    "gitops_manifests":["groq", "nvidia", "cerebras", "openrouter", "huggingface", "openai", "gemini", "ollama"],
    "heal":            ["groq", "nvidia", "cerebras", "openrouter", "huggingface", "openai", "gemini", "ollama"],
    "critique":        ["groq", "nvidia", "cerebras", "openrouter", "huggingface", "openai", "gemini", "ollama"],
    "default":         ["groq", "nvidia", "cerebras", "openrouter", "huggingface", "openai", "gemini", "ollama"],
}

def _e(k, d=""): return os.environ.get(k, d).strip()

def _cfg(task_type="default"):
    # Task-specific model overrides
    groq_model = "llama-3.3-70b-versatile"  # mixtral-8x7b-32768 was decommissioned

    return {
        "groq":        {"api_key": _e("GROQ_API_KEY"),        "model": _e("GROQ_MODEL",        groq_model),                          "base_url": _BASES["groq"]},
        "gemini":      {"api_key": _e("GOOGLE_API_KEY"),      "model": _e("GEMINI_MODEL",      "gemini-2.0-flash")},
        "nvidia":      {"api_key": _e("NVIDIA_API_KEY"),      "model": _e("NVIDIA_MODEL",      "meta/llama-3.1-70b-instruct"),       "base_url": _BASES["nvidia"]},
        "cerebras":    {"api_key": _e("CEREBRAS_API_KEY"),    "model": _e("CEREBRAS_MODEL",    "llama3.1-8b"),           "base_url": _BASES["cerebras"]},
        "openrouter":  {"api_key": _e("OPENROUTER_API_KEY"),  "model": _e("OPENROUTER_MODEL",  "anthropic/claude-3.5-sonnet"),       "base_url": _BASES["openrouter"]},
        "huggingface": {"api_key": _e("HUGGINGFACE_TOKEN"),   "model": _e("HUGGINGFACE_MODEL", "mistralai/Mistral-7B-Instruct-v0.3"),"base_url": _BASES["huggingface"]},
        "openai":      {"api_key": _e("OPENAI_API_KEY"),       "model": _e("OPENAI_MODEL",      "gpt-4o-mini"),                       "base_url": _BASES["openai"]},
        "ollama":      {
            "api_key":  _e("OLLAMA_API_KEY", "ollama"),            # stub; Ollama ignores it
            "model":    _e("OLLAMA_MODEL", "llama3.2:3b"),         # good default for 8 GB
            "base_url": _BASES["ollama"],
        },
    }

# ── Provider health tracker (skips recently-failed providers) ─────────────────
_health: dict[str, float] = {}   # provider → unix timestamp of last failure
_COOLDOWN = 120                   # seconds to skip a provider after failure

def _is_healthy(provider: str) -> bool:
    if provider == "ollama":
        import socket
        try:
            socket.create_connection(("127.0.0.1", 11434), timeout=1)
            return True
        except OSError:
            return False

    last_fail = _health.get(provider, 0)
    return (time.time() - last_fail) > _COOLDOWN

def _mark_failed(provider: str):
    _health[provider] = time.time()
    log.warning("Provider %s marked unhealthy for %ds", provider, _COOLDOWN)

# ── Callers ───────────────────────────────────────────────────────────────────
def _call_openai_compat(cfg, system, user, temperature, max_tokens, timeout):
    from openai import OpenAI
    client = OpenAI(api_key=cfg["api_key"], base_url=cfg["base_url"])
    resp = client.chat.completions.create(
        model=cfg["model"],
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=temperature, max_tokens=max_tokens, timeout=timeout,
    )
    return resp.choices[0].message.content.strip()

def _call_gemini(cfg, system, user, temperature, max_tokens, timeout):
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=cfg["api_key"])
    response = client.models.generate_content(
        model=cfg["model"],
        contents=user,
        config=types.GenerateContentConfig(
            system_instruction=system,
            temperature=temperature,
            max_output_tokens=max_tokens,
        )
    )
    return response.text.strip()

_CALLERS = {
    "groq": _call_openai_compat, "nvidia": _call_openai_compat,
    "cerebras": _call_openai_compat, "openrouter": _call_openai_compat,
    "huggingface": _call_openai_compat, "openai": _call_openai_compat,
    "ollama": _call_openai_compat, "gemini": _call_gemini,
}

# ── Public API ────────────────────────────────────────────────────────────────
def call_llm(system_prompt: str, user_prompt: str, task_type: str = "default", max_tokens_budget: int = 1024) -> str:
    """
    Call LLM with task-aware routing and full fallback chain.
    task_type controls which provider is tried first.
    Automatically skips providers that failed recently (cooldown window).
    """
    order       = _TASK_ROUTES.get(task_type, _TASK_ROUTES["default"])

    mode = _e("LLM_PROVIDER_MODE", "remote_first").lower()
    # Modes:
    #   remote_first  → use TASK_ROUTES as-is (Ollama last)
    #   ollama_first  → try Ollama, then others
    #   ollama_only   → force-only Ollama
    if mode == "ollama_only":
        order = ["ollama"]
    elif mode == "ollama_first":
        if "ollama" not in order:
            order = ["ollama"] + order
        else:
            order = ["ollama"] + [p for p in order if p != "ollama"]

    temperature = float(_e("LLM_TEMPERATURE", "0.1"))

    # Safely compute token limits, respecting the specific task budget overrides
    env_max = int(os.environ.get("LLM_MAX_TOKENS", "1024"))
    max_tokens  = min(max_tokens_budget, env_max)

    timeout     = int(_e("LLM_TIMEOUT_SECONDS","45"))
    max_retries = int(_e("LLM_MAX_RETRIES",   "3"))

    cfg_map     = _cfg(task_type)
    errors: list[str] = []

    for provider in order:
        cfg = cfg_map.get(provider, {})
        if not cfg.get("api_key"):
            log.debug("Skipping %s — no API key.", provider)
            continue
        if not _is_healthy(provider):
            log.info("Skipping %s — in cooldown after recent failure.", provider)
            continue

        caller = _CALLERS.get(provider)
        for attempt in range(1, max_retries + 1):
            try:
                log.info("LLM → %s [task=%s] attempt %d/%d", provider, task_type, attempt, max_retries)
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
        _mark_failed(provider)

    raise RuntimeError("All LLM providers failed:\n" + "\n".join(f"  • {e}" for e in errors))
