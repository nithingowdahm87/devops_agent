"""Pydantic Settings for SaaS mode."""
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    APP_NAME: str = "DevOps Agent"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = Field(default="development")

    SERVER_HOST: str = Field(default="0.0.0.0")
    SERVER_PORT: int = Field(default=8000)

    DATABASE_URL: str = Field(default="sqlite:///./devops_agent.db")

    JWT_SECRET_KEY: str = Field(default="dev-secret-change-in-production")
    JWT_ALGORITHM: str = Field(default="HS256")
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=60)

    MAX_REQUEST_BODY_SIZE_MB: int = Field(default=10)

    KIMCHI_API_KEY: str | None = Field(default=None)
    KIMCHI_API_URL: str = Field(default="https://llm.kimchi.dev/openai/v1")

    RATE_LIMIT_DEFAULT: str = Field(default="100/minute")
    RATE_LIMIT_WRITE: str = Field(default="20/minute")
    MAX_REQUEST_BODY_SIZE_MB: int = Field(default=10)
    REDIS_URL: str | None = Field(default=None)
    SENTRY_DSN: str | None = Field(default=None)

    model_config = SettingsConfigDict(env_file=".env", extra="allow")


settings = Settings()