from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")

    app_name: str = "DClaw Project"
    app_env: str = "dev"
    debug: bool = True

    # Default to local SQLite for fast dev onboarding. Override with PostgreSQL
    # URL in Docker / production (see docker-compose.yml and Helm values).
    database_url: str = "sqlite+aiosqlite:///./dclaw_project.db"

    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1"
    openrouter_api_key: str = ""
    openrouter_model: str = "meta-llama/llama-3.1-8b-instruct"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    secret_key: str = "change-me-in-production"
    access_token_expire_minutes: int = 60

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
