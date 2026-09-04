"""Application settings loaded from environment variables."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the TraceIQ backend."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    postgres_user: str = "postgres"
    postgres_password: str = "postgres"
    postgres_db: str = "traceiq"
    postgres_host: str = "postgres"
    postgres_port: int = 5432

    analytics_admin_password: str = "admin_password"
    analytics_reader_password: str = "reader_password"

    # LLM via OpenRouter (OpenAI-compatible API)
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    model: str = "minimax/minimax-m3:free"
    # Kept for backward compatibility; prefer openrouter_* / model
    openai_api_key: str = ""
    openai_model: str = ""

    # When True, request JSON object mode (not all OpenRouter models support it)
    llm_json_mode: bool = False

    # LangSmith — optional; tracing is enabled only when langchain_api_key is set
    langchain_tracing_v2: bool = True
    langchain_endpoint: str = "https://api.smith.langchain.com"
    langchain_api_key: str = ""
    langchain_project: str = "TraceIQ"

    backend_host: str = "0.0.0.0"
    backend_port: int = 8000

    sql_statement_timeout_ms: int = 15000
    sql_max_rows: int = 5000
    sql_max_repair_attempts: int = 2

    config_dir: str = "/config"

    @property
    def llm_api_key(self) -> str:
        """Prefer OpenRouter key; fall back to OPENAI_API_KEY."""
        return self.openrouter_api_key or self.openai_api_key

    @property
    def llm_model(self) -> str:
        """Prefer MODEL / openrouter model; fall back to openai_model."""
        return self.model or self.openai_model or "minimax/minimax-m3:free"

    @property
    def langsmith_enabled(self) -> bool:
        """Tracing is on only when an API key is present."""
        return bool(self.langchain_api_key.strip())

    @property
    def database_url(self) -> str:
        """Sync SQLAlchemy connection URL for the app/admin user (psycopg3)."""
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def reader_database_url(self) -> str:
        """Read-only SQLAlchemy URL for LLM-generated analytics queries."""
        return (
            f"postgresql+psycopg://analytics_reader:{self.analytics_reader_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
