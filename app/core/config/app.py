from pydantic import Field

from app.core.config.base import BaseConfig


class AppConfig(BaseConfig):
    PROJECT_NAME: str = "Bilans Palet EUR"
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = False
    # Same-origin by default (frontend is served by this app).
    CORS_ORIGINS: list[str] = Field(
        default_factory=lambda: ["http://localhost:8000", "http://127.0.0.1:8000"]
    )
    # DB session timezone so now() defaults are stored in local wall-clock time.
    TIMEZONE: str = "Europe/Warsaw"
    # Background task that closes ended warehouse days (keep one app process).
    DAY_CLOSE_ENABLED: bool = True
    DAY_CLOSE_INTERVAL_SECONDS: int = 60
    LOG_LEVEL: str = "INFO"
