"""Behaviour shared by every admin-managed dictionary (areas, pallet types, ...)."""

from collections.abc import Callable
from dataclasses import dataclass, field, replace
from uuid import uuid4

import pytest

from app.models.carrier_group import CarrierGroup
from tests.conftest import login, make_user


@dataclass
class Dictionary:
    url: str
    not_found: str
    duplicate: str
    # Extra fields a new row needs; gets the row's position (1, 2, ...).
    extra: Callable[[int], dict] = field(default=lambda n: {})
    # Rows belong to a carrier group (created by the fixture).
    needs_group: bool = False


DICTIONARIES = [
    pytest.param(
        Dictionary(
            url="/areas",
            not_found="Nie znaleziono obszaru",
            duplicate="Obszar o tej nazwie już istnieje",
        ),
        id="areas",
    ),
    pytest.param(
        Dictionary(
            url="/pallet-types",
            not_found="Nie znaleziono typu palety",
            duplicate="Typ palety o tej nazwie już istnieje",
        ),
        id="pallet-types",
    ),
    pytest.param(
        Dictionary(
            url="/qualities",
            not_found="Nie znaleziono jakości",
            duplicate="Jakość o tej nazwie już istnieje",
            extra=lambda n: {"sort_order": n},
        ),
        id="qualities",
    ),
    pytest.param(
        Dictionary(
            url="/carrier-groups",
            not_found="Nie znaleziono grupy nośników",
            duplicate="Grupa o tej nazwie już istnieje",
        ),
        id="carrier-groups",
    ),
    pytest.param(
        Dictionary(
            url="/carrier-types",
            not_found="Nie znaleziono typu nośnika",
            duplicate="Typ nośnika o tej nazwie już istnieje",
            needs_group=True,
        ),
        id="carrier-types",
    ),
]


@pytest.fixture(params=DICTIONARIES)
async def d(request, session) -> Dictionary:
    dictionary = request.param
    if not dictionary.needs_group:
        return dictionary
    group = CarrierGroup(name="EUR")
    session.add(group)
    await session.commit()
    group_uuid = str(group.uuid)
    return replace(dictionary, extra=lambda n: {"group_uuid": group_uuid})


async def create(client, headers, d: Dictionary, name: str, n: int = 1, **fields):
    return await client.post(
        d.url, headers=headers, json={"name": name, **d.extra(n), **fields}
    )


async def test_admin_creates_reads_and_lists(client, admin_headers, d):
    first = await create(client, admin_headers, d, "  Alfa ", 1, description="opis")
    await create(client, admin_headers, d, "Beta", 2)

    assert first.status_code == 200, first.text
    body = first.json()
    assert body["name"] == "Alfa"
    assert body["description"] == "opis"
    assert body["is_active"] is True

    one = await client.get(f"{d.url}/{body['uuid']}", headers=admin_headers)
    assert one.json()["name"] == "Alfa"

    listed = await client.get(d.url, headers=admin_headers)
    assert [row["name"] for row in listed.json()] == ["Alfa", "Beta"]


async def test_name_is_required(client, admin_headers, d):
    response = await create(client, admin_headers, d, "   ")

    assert response.status_code == 400
    assert response.json() == {"message": "Nazwa jest wymagana"}


async def test_name_must_be_unique(client, admin_headers, d):
    await create(client, admin_headers, d, "Alfa", 1)

    response = await create(client, admin_headers, d, "Alfa", 2)

    assert response.status_code == 409
    assert response.json() == {"message": d.duplicate}


async def test_get_a_missing_row(client, admin_headers, d):
    response = await client.get(f"{d.url}/{uuid4()}", headers=admin_headers)

    assert response.status_code == 404
    assert response.json() == {"message": d.not_found}


async def test_admin_updates_a_row(client, admin_headers, d):
    created = (await create(client, admin_headers, d, "Alfa")).json()

    response = await client.put(
        f"{d.url}/{created['uuid']}",
        headers=admin_headers,
        json={"name": "Gamma", "description": "nowy", "is_active": False},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["name"], body["description"], body["is_active"]) == (
        "Gamma",
        "nowy",
        False,
    )


async def test_update_keeping_the_same_name(client, admin_headers, d):
    created = (await create(client, admin_headers, d, "Alfa")).json()

    response = await client.put(
        f"{d.url}/{created['uuid']}", headers=admin_headers, json={"name": "Alfa"}
    )

    assert response.status_code == 200


async def test_update_to_a_taken_name(client, admin_headers, d):
    await create(client, admin_headers, d, "Alfa", 1)
    beta = (await create(client, admin_headers, d, "Beta", 2)).json()

    response = await client.put(
        f"{d.url}/{beta['uuid']}", headers=admin_headers, json={"name": "Alfa"}
    )

    assert response.status_code == 409
    assert response.json() == {"message": d.duplicate}


async def test_update_a_missing_row(client, admin_headers, d):
    response = await client.put(
        f"{d.url}/{uuid4()}", headers=admin_headers, json={"name": "x"}
    )

    assert response.status_code == 404
    assert response.json() == {"message": d.not_found}


async def test_admin_deletes_a_row(client, admin_headers, d):
    created = (await create(client, admin_headers, d, "Alfa")).json()

    deleted = await client.delete(f"{d.url}/{created['uuid']}", headers=admin_headers)
    again = await client.get(f"{d.url}/{created['uuid']}", headers=admin_headers)

    assert deleted.status_code == 200
    assert again.status_code == 404


async def test_delete_a_missing_row(client, admin_headers, d):
    response = await client.delete(f"{d.url}/{uuid4()}", headers=admin_headers)

    assert response.status_code == 404
    assert response.json() == {"message": d.not_found}


async def test_list_filters_by_active(client, admin_headers, d):
    await create(client, admin_headers, d, "Alfa", 1)
    beta = (await create(client, admin_headers, d, "Beta", 2)).json()
    await client.put(
        f"{d.url}/{beta['uuid']}", headers=admin_headers, json={"is_active": False}
    )

    active = await client.get(f"{d.url}?active=true", headers=admin_headers)
    inactive = await client.get(f"{d.url}?active=false", headers=admin_headers)

    assert [row["name"] for row in active.json()] == ["Alfa"]
    assert [row["name"] for row in inactive.json()] == ["Beta"]


@pytest.mark.parametrize("role", ["operator", "viewer"])
async def test_others_read_but_do_not_change(client, session, admin_headers, d, role):
    row = (await create(client, admin_headers, d, "Alfa")).json()
    await make_user(session, "jan", role=role)
    headers = await login(client, "jan")

    listed = await client.get(d.url, headers=headers)
    one = await client.get(f"{d.url}/{row['uuid']}", headers=headers)
    assert listed.status_code == one.status_code == 200

    changes = [
        create(client, headers, d, "Beta", 2),
        client.put(f"{d.url}/{row['uuid']}", headers=headers, json={"name": "x"}),
        client.delete(f"{d.url}/{row['uuid']}", headers=headers),
    ]
    for change in changes:
        response = await change
        assert response.status_code == 403
        assert response.json() == {"message": "Brak uprawnień"}


async def test_reading_needs_a_login(client, d):
    response = await client.get(d.url)

    assert response.status_code == 401
