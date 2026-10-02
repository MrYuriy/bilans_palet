import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel

from app.core.exc import (
    BadRequestException,
    ForbiddenException,
    ObjectAlreadyExistsException,
    ObjectNotFoundException,
    UnauthorizedException,
    register_exception_handlers,
)


class Payload(BaseModel):
    name: str
    quantity: int


def make_app() -> FastAPI:
    """A tiny app with the project's exception handlers."""
    app = FastAPI()
    register_exception_handlers(app)

    errors = {
        "bad-request": BadRequestException,
        "unauthorized": UnauthorizedException,
        "forbidden": ForbiddenException,
        "not-found": ObjectNotFoundException,
        "conflict": ObjectAlreadyExistsException,
    }

    @app.get("/raise/{kind}")
    async def raise_error(kind: str):
        raise errors[kind]("Komunikat")

    @app.post("/payload")
    async def accept(payload: Payload):
        return payload

    return app


@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=make_app()), base_url="http://test"
    ) as ac:
        yield ac


@pytest.mark.parametrize(
    ("kind", "status"),
    [
        ("bad-request", 400),
        ("unauthorized", 401),
        ("forbidden", 403),
        ("not-found", 404),
        ("conflict", 409),
    ],
)
async def test_domain_errors_map_to_status_and_message(client, kind, status):
    response = await client.get(f"/raise/{kind}")

    assert response.status_code == status
    assert response.json() == {"message": "Komunikat"}


async def test_validation_errors_are_in_polish_and_name_the_fields(client):
    response = await client.post("/payload", json={"quantity": "dużo"})

    assert response.status_code == 422
    body = response.json()
    assert body["message"] == "Nieprawidłowe dane: name, quantity"
    assert len(body["errors"]) == 2


async def test_validation_error_for_a_malformed_body(client):
    response = await client.post(
        "/payload", content="nie-json", headers={"Content-Type": "application/json"}
    )

    assert response.status_code == 422
    assert response.json()["message"].startswith("Nieprawidłowe dane")
