from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Core
    APP_NAME: str = "EstudioHC Central API"
    DEBUG: bool = False
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 5050

    # Database
    DATABASE_URL: str = f"sqlite+aiosqlite:///{Path.home() / 'Apps/EstudioHC-Memory-Suite/data/estudiohc.db'}"
    DB_ECHO: bool = False

    # CORS
    CORS_ORIGINS: list[str] = ["*"]

    # Paths
    DASHBOARD_PATH: str = str(Path(__file__).parent.parent.parent / "dashboard" / "static")
    HERMES_CLI: str = str(Path.home() / ".local/bin/hermes")

    # Hermes AI
    HERMES_TIMEOUT: int = 120


settings = Settings()