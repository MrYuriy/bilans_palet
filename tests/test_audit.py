# ruff: noqa: DTZ001 - audit times are naive local wall-clock times by design
"""The audit log: who changed what in users and dictionaries."""

import json
from datetime import datetime
from uuid import uuid4

import pytest

from app.models.area import Area
from app.models.audit_log import AuditLog
from app.models.pallet_type import PalletType
from app.models.quality import Quality
from tests.conftest import PASSWORD, login, make_user


async def log(client, headers, **filters):
    response = await client.get("/audit", headers=headers, params=filters)
    assert response.status_code == 200, response.text
    return response.json()


async def test_creating_an_area_is_logged(client, admin_headers):
    area = (
        await client.post("/areas", headers=admin_headers, json={"name": "Wysyłka 445"})
    ).json()

    [entry] = await log(client, admin_headers)

    assert entry["username"] == "admin"
    assert (entry["action"], entry["action_label"]) == ("create", "Utworzenie")
    assert (entry["entity"], entry["entity_label"]) == ("area", "Obszar")
    assert entry["entity_uuid"] == area["uuid"]
    assert entry["entity_name"] == "Wysyłka 445"
    assert entry["old_data"] is None
    assert entry["new_data"] == {
        "name": "Wysyłka 445",
        "description": None,
        "is_active": True,
    }


async def test_an_update_keeps_only_what_changed(client, admin_headers):
    area = (
        await client.post("/areas", headers=admin_headers, json={"name": "A"})
    ).json()

    await client.put(
        f"/areas/{area['uuid']}",
        headers=admin_headers,
        json={"name": "B", "is_active": False, "description": None},
    )

    update, _create = await log(client, admin_headers)
    assert (update["action"], update["action_label"]) == ("update", "Zmiana")
    assert update["entity_name"] == "B"
    assert update["old_data"] == {"name": "A", "is_active": True}
    assert update["new_data"] == {"name": "B", "is_active": False}


async def test_an_update_that_changes_nothing_is_not_logged(client, admin_headers):
    area = (
        await client.post("/areas", headers=admin_headers, json={"name": "A"})
    ).json()

    await client.put(
        f"/areas/{area['uuid']}", headers=admin_headers, json={"name": "A"}
    )

    assert [e["action"] for e in await log(client, admin_headers)] == ["create"]


async def test_deleting_is_logged_with_the_last_values(client, admin_headers):
    area = (
        await client.post("/areas", headers=admin_headers, json={"name": "A"})
    ).json()

    await client.delete(f"/areas/{area['uuid']}", headers=admin_headers)

    delete, _create = await log(client, admin_headers)
    assert (delete["action"], delete["action_label"]) == ("delete", "Usunięcie")
    assert delete["old_data"] == {"name": "A", "description": None, "is_active": True}
    assert delete["new_data"] is None


@pytest.mark.parametrize(
    ("url", "payload", "entity", "label", "new_data"),
    [
        (
            "/pallet-types",
            {"name": "EUR"},
            "pallet_type",
            "Typ palety",
            {"name": "EUR", "description": None, "is_active": True},
        ),
        (
            "/qualities",
            {"name": "I", "sort_order": 1},
            "quality",
            "Jakość",
            {"name": "I", "sort_order": 1, "description": None, "is_active": True},
        ),
    ],
)
async def test_other_dictionaries_are_logged(
    client, admin_headers, url, payload, entity, label, new_data
):
    await client.post(url, headers=admin_headers, json=payload)

    [entry] = await log(client, admin_headers)

    assert (entry["entity"], entry["entity_label"]) == (entity, label)
    assert entry["new_data"] == new_data


async def test_a_refused_change_leaves_no_entry(client, admin_headers):
    await client.post("/areas", headers=admin_headers, json={"name": "A"})

    duplicate = await client.post("/areas", headers=admin_headers, json={"name": "A"})

    assert duplicate.status_code == 409
    assert len(await log(client, admin_headers)) == 1


async def test_users_are_logged_without_passwords(client, session, admin_headers):
    area = Area(name="Wysyłka 445")
    session.add(area)
    await session.commit()

    created = (
        await client.post(
            "/users",
            headers=admin_headers,
            json={
                "username": "jan",
                "password": "Tajne123!",
                "role": "admin",
                "areas": [str(area.uuid)],
            },
        )
    ).json()
    await client.put(
        f"/users/{created['uuid']}",
        headers=admin_headers,
        json={"password": "Inne456!", "areas": [], "must_change_password": True},
    )

    update, create = await log(client, admin_headers, entity="user")

    assert create["entity_name"] == "jan"
    assert create["new_data"] == {
        "username": "jan",
        "role": "admin",
        "is_active": True,
        "must_change_password": False,
        "areas": ["Wysyłka 445"],
    }
    assert update["old_data"] == {
        "must_change_password": False,
        "areas": ["Wysyłka 445"],
        "password_changed": None,
    }
    assert update["new_data"] == {
        "must_change_password": True,
        "areas": [],
        "password_changed": True,
    }

    everything = json.dumps(await log(client, admin_headers))
    assert "Tajne123!" not in everything
    assert "Inne456!" not in everything
    assert "argon2" not in everything


async def test_changing_ones_own_password_is_logged(client, session, admin_headers):
    await make_user(session, "jan", must_change_password=True)
    headers = await login(client, "jan")

    await client.post(
        "/auth/change-password",
        headers=headers,
        json={"old_password": PASSWORD, "new_password": "Nowe456!"},
    )

    [entry] = await log(client, admin_headers, entity="user")
    assert (entry["username"], entry["entity_name"]) == ("jan", "jan")
    assert entry["new_data"] == {
        "must_change_password": False,
        "password_changed": True,
    }


async def test_entries_outlive_their_author(client, session, admin_headers):
    other = await make_user(session, "anna", role="admin")
    anna = await login(client, "anna")
    await client.post("/areas", headers=anna, json={"name": "A"})

    await client.delete(f"/users/{other.uuid}", headers=admin_headers)

    entries = await log(client, admin_headers, entity="area")
    assert [(e["username"], e["user_uuid"]) for e in entries] == [("anna", None)]


async def test_filters_and_total(client, session, admin_headers):
    a = (await client.post("/areas", headers=admin_headers, json={"name": "A"})).json()
    await client.post("/areas", headers=admin_headers, json={"name": "B"})
    await client.post("/pallet-types", headers=admin_headers, json={"name": "EUR"})

    response = await client.get("/audit", headers=admin_headers, params={"limit": 2})
    by_entity = await log(client, admin_headers, entity="area")
    by_row = await log(client, admin_headers, entity_uuid=a["uuid"])

    assert response.headers["X-Total-Count"] == "3"
    assert [e["entity_name"] for e in response.json()] == ["EUR", "B"]
    assert [e["entity_name"] for e in by_entity] == ["B", "A"]
    assert [e["entity_name"] for e in by_row] == ["A"]


async def test_entries_of_the_same_instant_keep_their_order(
    client, session, admin_headers
):
    # The clock can give two entries the same time; the order must still hold.
    moment = datetime(2026, 10, 1, 12, 0)
    for name in ("first", "second", "third"):
        session.add(
            AuditLog(
                username="admin",
                action="create",
                entity="area",
                entity_uuid=uuid4(),
                entity_name=name,
                created_at=moment,
            )
        )
        await session.flush()
    await session.commit()

    entries = await log(client, admin_headers, entity="area")

    assert [e["entity_name"] for e in entries] == ["third", "second", "first"]


async def test_movements_are_not_logged(client, session, admin_headers):
    rows = [Area(name="A"), PalletType(name="EUR"), Quality(name="I", sort_order=1)]
    session.add_all(rows)
    await session.commit()
    area, eur, q1 = rows

    response = await client.post(
        "/movements",
        headers=admin_headers,
        json={
            "type": "RECEIPT",
            "area_uuid": str(area.uuid),
            "lines": [
                {
                    "pallet_type_uuid": str(eur.uuid),
                    "quality_uuid": str(q1.uuid),
                    "quantity": 5,
                }
            ],
        },
    )

    assert response.status_code == 200
    assert await log(client, admin_headers) == []


@pytest.mark.parametrize("role", ["operator", "viewer"])
async def test_only_the_admin_reads_the_log(client, session, role):
    await make_user(session, "jan", role=role)
    headers = await login(client, "jan")

    response = await client.get("/audit", headers=headers)

    assert response.status_code == 403
    assert response.json() == {"message": "Brak uprawnień"}


async def test_the_log_cannot_be_written_through_the_api(client, admin_headers):
    response = await client.post("/audit", headers=admin_headers, json={})

    assert response.status_code == 405
