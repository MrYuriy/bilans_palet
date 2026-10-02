from datetime import UTC, datetime, timedelta
from typing import Any

from jose import jwt

from app.core.config import settings


def create_access_token(
    data: dict[str, Any], expires_delta: timedelta | None = None
) -> str:
    to_encode = data.copy()
    expire = datetime.now(UTC) + (
        expires_delta or timedelta(minutes=settings.auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(
        to_encode, settings.auth.SECRET_KEY, algorithm=settings.auth.ALGORITHM
    )


def decode_access_token(token: str) -> dict[str, Any]:
    return jwt.decode(
        token, settings.auth.SECRET_KEY, algorithms=[settings.auth.ALGORITHM]
    )
