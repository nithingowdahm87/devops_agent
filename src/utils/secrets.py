"""
Unified Secrets Provider — Strategy pattern with 3 backends.

Priority order:
  1. AWS Secrets Manager  (if boto3 available + AWS credentials set)
  2. HashiCorp Vault      (if hvac available + VAULT_ADDR set)
  3. Environment variable  (fallback for local development)

Usage:
    from src.utils.secrets import get_secret
    api_key = get_secret("GOOGLE_API_KEY")
"""

import os
import json
import logging

logger = logging.getLogger("devops-agent.secrets")

# ─── Key name mapping ───────────────────────────────────────────────
# Maps friendly names to env var names and secret store paths
_KEY_MAP = {
    "GROQ_API_KEY":      {"env": "GROQ_API_KEY",      "aws_field": "groq_api_key"},
    "NVIDIA_API_KEY":    {"env": "NVIDIA_API_KEY",     "aws_field": "nvidia_api_key"},
    "CEREBRAS_API_KEY":  {"env": "CEREBRAS_API_KEY",   "aws_field": "cerebras_api_key"},
    "OPENROUTER_API_KEY":{"env": "OPENROUTER_API_KEY", "aws_field": "openrouter_api_key"},
    "HUGGINGFACE_TOKEN": {"env": "HUGGINGFACE_TOKEN",  "aws_field": "huggingface_token"},
}

# AWS Secrets Manager secret name (single secret holding all keys)
_AWS_SECRET_NAME = os.environ.get("DEVOPS_AGENT_SECRET_NAME", "devops-agent/llm-keys")
_AWS_REGION = os.environ.get("AWS_REGION", "ap-south-1")

# Vault path
_VAULT_PATH = os.environ.get("VAULT_SECRET_PATH", "secret/data/devops-agent/llm-keys")


# ─── Backend: AWS Secrets Manager ────────────────────────────────────

def _try_aws(field: str) -> str | None:
    """Attempt to fetch from AWS Secrets Manager."""
    try:
        import boto3
        client = boto3.client("secretsmanager", region_name=_AWS_REGION)
        raw = client.get_secret_value(SecretId=_AWS_SECRET_NAME)["SecretString"]
        secrets = json.loads(raw)
        value = secrets.get(field)
        if value:
            logger.info("Secret '%s' loaded from AWS Secrets Manager", field)
        return value
    except ImportError:
        return None  # boto3 not installed
    except Exception as e:
        logger.debug("AWS Secrets Manager unavailable: %s", e)
        return None


# ─── Backend: HashiCorp Vault ────────────────────────────────────────

def _try_vault(field: str) -> str | None:
    """Attempt to fetch from HashiCorp Vault."""
    try:
        import hvac
        vault_addr = os.environ.get("VAULT_ADDR")
        vault_token = os.environ.get("VAULT_TOKEN")
        if not vault_addr or not vault_token:
            return None
        client = hvac.Client(url=vault_addr, token=vault_token)
        resp = client.secrets.kv.v2.read_secret_version(path="devops-agent/llm-keys")
        value = resp["data"]["data"].get(field)
        if value:
            logger.info("Secret '%s' loaded from Vault", field)
        return value
    except ImportError:
        return None  # hvac not installed
    except Exception as e:
        logger.debug("Vault unavailable: %s", e)
        return None


# ─── Backend: Environment Variable ──────────────────────────────────

def _try_env(env_name: str) -> str | None:
    """Fallback to environment variable."""
    value = os.environ.get(env_name)
    if value:
        logger.info("Secret '%s' loaded from environment variable", env_name)
    return value


# ─── Public API ─────────────────────────────────────────────────────

def get_secret(name: str) -> str:
    """
    Retrieve a secret by name. Tries backends in priority order:
    AWS Secrets Manager → Vault → Environment Variable.

    Args:
        name: Key name (e.g., "GOOGLE_API_KEY", "GROQ_API_KEY")

    Returns:
        The secret string.

    Raises:
        RuntimeError: If the secret is not found in any backend.
    """
    mapping = _KEY_MAP.get(name, {"env": name, "aws_field": name.lower()})
    env_name = mapping["env"]
    aws_field = mapping["aws_field"]

    # Try each backend in priority order
    value = _try_aws(aws_field)
    if value:
        return value

    value = _try_vault(aws_field)
    if value:
        return value

    value = _try_env(env_name)
    if value:
        return value

    raise RuntimeError(
        f"Secret '{name}' not found. Set the {env_name} environment variable, "
        f"or configure AWS Secrets Manager / Vault. "
        f"See .env.example for required keys."
    )
