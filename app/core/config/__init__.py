from app.core.config.app import AppConfig
from app.core.config.auth import AuthConfig
from app.core.config.base import BaseConfig
from app.core.config.db import DbConfig


class Settings(BaseConfig):
    app: AppConfig = AppConfig()
    db: DbConfig = DbConfig()
    auth: AuthConfig = AuthConfig()


settings = Settings()

__all__ = ["AppConfig", "AuthConfig", "BaseConfig", "DbConfig", "Settings", "settings"]
