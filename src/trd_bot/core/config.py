from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="TRD_BOT_",
        extra="ignore",
    )

    app_name: str = "TRD BOT v2"
    app_version: str = "0.1.0"
    environment: Literal["development", "test", "production"] = "development"
    debug: bool = False


@lru_cache
def get_settings() -> Settings:
    """Return a cached settings instance."""

    return Settings()
