"""
Central config loader. Reads from .env (via python-dotenv) and environment.
All other modules import from here — never call os.environ directly.
"""

from __future__ import annotations

import os
from pathlib import Path

# Load .env file if present (dev workflow)
try:
    from dotenv import load_dotenv
    _env_file = Path(__file__).parents[2] / ".env"
    if _env_file.exists():
        load_dotenv(_env_file)
except ImportError:
    pass  # python-dotenv optional in CI — env vars injected directly


def _e(key: str, default: str = "") -> str:
    return os.environ.get(key, default).strip()


# ── API Keys ──────────────────────────────────────────────────────────────────
GOOGLE_API_KEY     = _e("GOOGLE_API_KEY")
GROQ_API_KEY       = _e("GROQ_API_KEY")
NVIDIA_API_KEY     = _e("NVIDIA_API_KEY")
CEREBRAS_API_KEY   = _e("CEREBRAS_API_KEY")
OPENROUTER_API_KEY = _e("OPENROUTER_API_KEY")
# HUGGINGFACE_TOKEN  = _e("HUGGINGFACE_TOKEN")  # HuggingFace client not used
KIMCHI_API_KEY     = _e("KIMCHI_API_KEY")

# ── LLM Routing ───────────────────────────────────────────────────────────────
LLM_STRATEGY       = _e("LLM_STRATEGY",       "fallback")
LLM_PRIMARY        = _e("LLM_PRIMARY",         "groq")
LLM_FALLBACK_ORDER = _e("LLM_FALLBACK_ORDER",  "gemini,cerebras,nvidia,openrouter,huggingface")
LLM_TEMPERATURE    = float(_e("LLM_TEMPERATURE", "0.1"))
LLM_MAX_TOKENS     = int(_e("LLM_MAX_TOKENS",    "8192"))
LLM_TIMEOUT        = int(_e("LLM_TIMEOUT_SECONDS", "45"))
LLM_MAX_RETRIES    = int(_e("LLM_MAX_RETRIES",   "3"))
MAX_HEAL_RETRIES   = int(_e("MAX_HEAL_RETRIES", "3"))

# ── Per-provider model pins ───────────────────────────────────────────────────
GROQ_MODEL         = _e("GROQ_MODEL",        "llama-3.3-70b-versatile")
GEMINI_MODEL       = _e("GEMINI_MODEL",       "gemini-2.0-flash-exp")
NVIDIA_MODEL       = _e("NVIDIA_MODEL",       "meta/llama-3.1-70b-instruct")
CEREBRAS_MODEL     = _e("CEREBRAS_MODEL",     "llama3.1-70b")
OPENROUTER_MODEL   = _e("OPENROUTER_MODEL",   "anthropic/claude-3.5-sonnet")
# HUGGINGFACE_MODEL  = _e("HUGGINGFACE_MODEL",  "mistralai/Mistral-7B-Instruct-v0.3")  # HuggingFace client not used
KIMCHI_MODEL       = _e("KIMCHI_MODEL",       "kimi-k2.6")

# ── Pipeline mode ─────────────────────────────────────────────────────────────
PIPELINE_ENV       = _e("PIPELINE_ENV", "prod")
DEBUG              = _e("DEBUG", "false").lower() == "true"

# ── Default environment ───────────────────────────────────────────────────────
DEFAULT_ENVIRONMENT = _e("PIPELINE_ENV", "dev")
