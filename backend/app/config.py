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

    analytics_reader_password: str = "reader_password"

    openai_api_key: str = ""

    backend_host: str = "0.0.0.0"
    backend_port: int = 8000

    @property
    def database_url(self) -> str:
        """Sync SQLAlchemy connection URL (psycopg3)."""
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
