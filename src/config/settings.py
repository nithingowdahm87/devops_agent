"""Pydantic Settings for SaaS mode."""
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    APP_NAME: str = "DevOps Agent"
    APP_VERSION: str = "3.0.0"
    ENVIRONMENT: str = Field(default="development")

    SERVER_HOST: str = Field(default="0.0.0.0")
    SERVER_PORT: int = Field(default=8000)

    DATABASE_URL: str = Field(default="sqlite:///./devops_agent.db")

    JWT_SECRET_KEY: str = Field(default="dev-secret-change-in-production")
    JWT_ALGORITHM: str = Field(default="HS256")
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=60)

    KIMCHI_API_KEY: str | None = Field(default=None)
    KIMCHI_API_URL: str = Field(default="https://llm.kimchi.dev/openai/v1")

    model_config = SettingsConfigDict(env_file=".env", extra="allow")


settings = Settings()