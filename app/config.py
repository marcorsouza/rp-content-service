from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: Literal["development", "demo", "staging", "production"] = "development"
    database_url: str = ""
    api_key: str = "dev-content-api-key"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    log_level: str = "INFO"

    @property
    def docs_enabled(self) -> bool:
        return self.app_env in {"development", "demo", "staging"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
