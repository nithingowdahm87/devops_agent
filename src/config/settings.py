"""Pydantic Settings for CLI-only DevOps Agent (NVIDIA-only)."""
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
import yaml


class Settings(BaseSettings):
    APP_NAME: str = "DevOps Agent"
    APP_VERSION: str = "2.0.0"
    ENVIRONMENT: str = Field(default="production")

    # NVIDIA LLM
    NVIDIA_API_KEY: str | None = Field(default=None)
    NVIDIA_MODEL: str = Field(default="meta/llama-3.1-405b-instruct")

    # Generation params
    LLM_TEMPERATURE: float = Field(default=0.1)
    LLM_MAX_TOKENS: int = Field(default=8192)
    LLM_TIMEOUT_SECONDS: int = Field(default=180)
    LLM_MAX_RETRIES: int = Field(default=3)

    # Pipeline
    PIPELINE_ENV: str = Field(default="prod")

    # Logging
    LOG_JSON: bool = Field(default=False)

    model_config = SettingsConfigDict(env_file=".env", extra="allow")


settings = Settings()


_PROFILES_PATH = Path(__file__).parent.parent.parent / "configs" / "resource_profiles.yaml"


def load_resource_profiles() -> dict:
    """Load per-environment resource profiles from configs/resource_profiles.yaml."""
    if not _PROFILES_PATH.exists():
        return {}
    return yaml.safe_load(_PROFILES_PATH.read_text()) or {}


RESOURCE_PROFILES: dict = load_resource_profiles()