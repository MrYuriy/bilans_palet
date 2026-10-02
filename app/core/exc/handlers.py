from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.core.exc.base import (
    BadRequestException,
    ForbiddenException,
    ObjectAlreadyExistsException,
    ObjectNotFoundException,
    UnauthorizedException,
)


def _json(e: Exception, code: int) -> JSONResponse:
    return JSONResponse(content={"message": str(e)}, status_code=code)


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(
        BadRequestException,
        lambda _r, e: _json(e, status.HTTP_400_BAD_REQUEST),
    )
    app.add_exception_handler(
        UnauthorizedException,
        lambda _r, e: _json(e, status.HTTP_401_UNAUTHORIZED),
    )
    app.add_exception_handler(
        ForbiddenException,
        lambda _r, e: _json(e, status.HTTP_403_FORBIDDEN),
    )
    app.add_exception_handler(
        ObjectNotFoundException,
        lambda _r, e: _json(e, status.HTTP_404_NOT_FOUND),
    )
    app.add_exception_handler(
        ObjectAlreadyExistsException,
        lambda _r, e: _json(e, status.HTTP_409_CONFLICT),
    )
