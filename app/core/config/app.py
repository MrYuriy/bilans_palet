from pydantic import Field

from app.core.config.base import BaseConfig


class AppConfig(BaseConfig):
    PROJECT_NAME: str = "MONOLIT"
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
    # Saldo Palet (deliveries of the day before, read every morning). Empty URL
    # = off. The account needs the "reports" permission there (a viewer).
    SALDO_PALET_URL: str = ""
    SALDO_PALET_USERNAME: str = ""
    SALDO_PALET_PASSWORD: str = ""
    # Local time after which yesterday is imported.
    SALDO_PALET_IMPORT_AT: str = "05:00"
    # Days missed while the app was down that are still caught up.
    SALDO_PALET_CATCH_UP_DAYS: int = 7
    # Reminder mails (SMTP). Empty host = no mail is sent.
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = ""
    SMTP_STARTTLS: bool = True
    # The app's address, put into the mails.
    APP_URL: str = ""
