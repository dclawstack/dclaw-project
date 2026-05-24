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

    # Comma-separated list of origins that may call the API with credentials.
    # In dev we default to the local Next.js port so the browser can talk to us;
    # in prod operators MUST supply an explicit list (no wildcard, since CORS
    # spec forbids `*` together with credentials).
    cors_allow_origins: str = "http://localhost:3010,http://localhost:3000"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_allow_origins.split(",") if o.strip()]

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() in {"prod", "production"}

    def assert_production_ready(self) -> None:
        """Refuse to boot in production with the default JWT signing key.

        HS256 + a known constant lets anyone forge a token for any user in
        any workspace. We catch the misconfiguration at process startup
        instead of letting it become a silent security bug.
        """
        if self.is_production and self.secret_key == "change-me-in-production":
            raise RuntimeError(
                "SECRET_KEY must be set to a non-default value when APP_ENV=production. "
                "Generate one with `python -c \"import secrets; print(secrets.token_urlsafe(64))\"` "
                "and provide it via the SECRET_KEY environment variable."
            )


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
