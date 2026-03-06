"""
LLM Router — 6-provider fallback chain with exponential backoff.
Provider order: Groq → Gemini → Cerebras → NVIDIA → OpenRouter → HuggingFace
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
}

# ── Task-based model routing ──────────────────────────────────────────────────
# Each task type gets the best provider first, then falls back automatically.
# Gemini is intentionally demoted behind Groq and OpenRouter until fully migrated to google.genai
_TASK_ROUTES = {
    "docker":      ["groq",       "openrouter", "gemini",  "cerebras", "nvidia", "huggingface", "openai"],
    "k8s":         ["groq",       "openrouter", "gemini",  "cerebras", "nvidia", "huggingface", "openai"],
    "ci":          ["openrouter", "groq",       "gemini",  "nvidia", "cerebras",   "huggingface", "openai"],
    "heal":        ["groq",       "openrouter", "gemini",  "cerebras", "nvidia", "huggingface", "openai"],
    "critique":    ["openrouter", "groq",       "gemini",  "nvidia", "cerebras",   "huggingface", "openai"],
    "default":     ["groq",       "openrouter", "gemini",  "cerebras", "nvidia", "huggingface", "openai"],
}

def _e(k, d=""): return os.environ.get(k, d).strip()

def _cfg(task_type="default"):
    # Task-specific model overrides
    groq_model = "mixtral-8x7b-32768" if task_type == "heal" else "llama-3.3-70b-versatile"
    
    return {
        "groq":        {"api_key": _e("GROQ_API_KEY"),        "model": _e("GROQ_MODEL",        groq_model),                          "base_url": _BASES["groq"]},
        "gemini":      {"api_key": _e("GOOGLE_API_KEY"),      "model": _e("GEMINI_MODEL",      "gemini-2.0-flash")},
        "nvidia":      {"api_key": _e("NVIDIA_API_KEY"),      "model": _e("NVIDIA_MODEL",      "meta/llama-3.1-70b-instruct"),       "base_url": _BASES["nvidia"]},
        "cerebras":    {"api_key": _e("CEREBRAS_API_KEY"),    "model": _e("CEREBRAS_MODEL",    "llama-3.1-70b-versatile"),           "base_url": _BASES["cerebras"]},
        "openrouter":  {"api_key": _e("OPENROUTER_API_KEY"),  "model": _e("OPENROUTER_MODEL",  "anthropic/claude-3.5-sonnet"),       "base_url": _BASES["openrouter"]},
        "huggingface": {"api_key": _e("HUGGINGFACE_TOKEN"),   "model": _e("HUGGINGFACE_MODEL", "mistralai/Mistral-7B-Instruct-v0.3"),"base_url": _BASES["huggingface"]},
        "openai":      {"api_key": _e("OPENAI_API_KEY"),       "model": _e("OPENAI_MODEL",      "gpt-4o-mini"),                       "base_url": _BASES["openai"]},
    }

# ── Provider health tracker (skips recently-failed providers) ─────────────────
_health: dict[str, float] = {}   # provider → unix timestamp of last failure
_COOLDOWN = 120                   # seconds to skip a provider after failure

def _is_healthy(provider: str) -> bool:
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
    import google.generativeai as genai
    genai.configure(api_key=cfg["api_key"])
    model = genai.GenerativeModel(
        model_name=cfg["model"],
        system_instruction=system,
        generation_config=genai.GenerationConfig(temperature=temperature, max_output_tokens=max_tokens),
    )
    return model.generate_content(user, request_options={"timeout": timeout}).text.strip()

_CALLERS = {
    "groq": _call_openai_compat, "nvidia": _call_openai_compat,
    "cerebras": _call_openai_compat, "openrouter": _call_openai_compat,
    "huggingface": _call_openai_compat, "gemini": _call_gemini,
}

# ── Public API ────────────────────────────────────────────────────────────────
def call_llm(system_prompt: str, user_prompt: str, task_type: str = "default", max_tokens_budget: int = 2048) -> str:
    """
    Call LLM with task-aware routing and full fallback chain.
    task_type controls which provider is tried first.
    Automatically skips providers that failed recently (cooldown window).
    """
    order       = _TASK_ROUTES.get(task_type, _TASK_ROUTES["default"])
    temperature = float(_e("LLM_TEMPERATURE", "0.1"))
    
    # Safely compute token limits, respecting the specific task budget overrides
    env_max = int(os.environ.get("LLM_MAX_TOKENS", "2048"))
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
