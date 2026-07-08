"""Pydantic Settings for CLI-only DevOps Agent."""
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    APP_NAME: str = "DevOps Agent"
    APP_VERSION: str = "1.0.0"
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


def validate_cli_settings():
    """Validate settings for CLI mode."""
    if settings.ENVIRONMENT == "production":
        if not settings.NVIDIA_API_KEY:
            raise RuntimeError(
                "NVIDIA_API_KEY is required for production use. "
                "Set it in your environment or .env file."
            )