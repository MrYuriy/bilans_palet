from pydantic import Field

from app.core.config.base import BaseConfig


class AuthConfig(BaseConfig):
    SECRET_KEY: str = Field(..., alias="SECRET_KEY")
    ALGORITHM: str = Field("HS256", alias="ALGORITHM")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(30, alias="ACCESS_TOKEN_EXPIRE_MINUTES")
