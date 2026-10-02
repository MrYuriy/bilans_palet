from fastapi import FastAPI, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
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


def _validation_error(_request, e: RequestValidationError) -> JSONResponse:
    # Same {message} shape as the domain errors, in Polish; the raw pydantic
    # details stay available under "errors" for debugging.
    fields = sorted({str(err["loc"][-1]) for err in e.errors() if err.get("loc")})
    message = "Nieprawidłowe dane"
    if fields:
        message += ": " + ", ".join(fields)
    return JSONResponse(
        content={"message": message, "errors": jsonable_encoder(e.errors())},
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(RequestValidationError, _validation_error)
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
