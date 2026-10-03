"""What movements already use is deactivated, never deleted."""

import pytest

from app.models.area import Area
from app.models.pallet_type import PalletType
from app.models.quality import Quality
from tests.conftest import login, make_user


@pytest.fixture
async def ids(session) -> dict[str, str]:
    rows = {
        "area": Area(name="Przyjęcia 445"),
        "eur": PalletType(name="EUR"),
        "I": Quality(name="I", sort_order=1),
        "II": Quality(name="II", sort_order=2),
    }
    session.add_all(rows.values())
    await session.commit()
    return {key: str(row.uuid) for key, row in rows.items()}


async def receive(client, headers, ids, quality="I"):
    response = await client.post(
        "/movements",
        headers=headers,
        json={
            "type": "RECEIPT",
            "area_uuid": ids["area"],
            "lines": [
                {
                    "pallet_type_uuid": ids["eur"],
                    "quality_uuid": ids[quality],
                    "quantity": 10,
                }
            ],
        },
    )
    assert response.status_code == 200, response.text


@pytest.mark.parametrize(
    ("url", "key", "message"),
    [
        ("/areas", "area", "Obszar ma zarejestrowane ruchy. Możesz go dezaktywować."),
        (
            "/pallet-types",
            "eur",
            "Typ palety występuje w ruchach. Możesz go dezaktywować.",
        ),
        ("/qualities", "I", "Jakość występuje w ruchach. Możesz ją dezaktywować."),
    ],
)
async def test_a_used_dictionary_row_is_not_deleted(
    client, admin_headers, ids, url, key, message
):
    await receive(client, admin_headers, ids)

    deleted = await client.delete(f"{url}/{ids[key]}", headers=admin_headers)
    still_there = await client.get(f"{url}/{ids[key]}", headers=admin_headers)
    deactivated = await client.put(
        f"{url}/{ids[key]}", headers=admin_headers, json={"is_active": False}
    )

    assert deleted.status_code == 409
    assert deleted.json() == {"message": message}
    assert still_there.status_code == 200
    assert deactivated.json()["is_active"] is False


async def test_an_unused_row_next_to_used_ones_can_be_deleted(
    client, admin_headers, ids
):
    await receive(client, admin_headers, ids, quality="I")

    response = await client.delete(f"/qualities/{ids['II']}", headers=admin_headers)

    assert response.status_code == 200


async def test_a_quality_used_only_as_a_reclassification_target(
    client, admin_headers, ids
):
    await receive(client, admin_headers, ids, quality="I")
    await client.post(
        "/movements",
        headers=admin_headers,
        json={
            "type": "RECLASSIFICATION",
            "area_uuid": ids["area"],
            "lines": [
                {
                    "pallet_type_uuid": ids["eur"],
                    "quality_uuid": ids["I"],
                    "to_quality_uuid": ids["II"],
                    "quantity": 3,
                }
            ],
        },
    )

    response = await client.delete(f"/qualities/{ids['II']}", headers=admin_headers)

    assert response.status_code == 409


async def test_a_user_with_movements_is_not_deleted(
    client, session, admin_headers, ids
):
    user = await make_user(session, "jan", role="admin")
    await receive(client, await login(client, "jan"), ids)

    deleted = await client.delete(f"/users/{user.uuid}", headers=admin_headers)
    deactivated = await client.put(
        f"/users/{user.uuid}", headers=admin_headers, json={"is_active": False}
    )

    assert deleted.status_code == 409
    assert deleted.json() == {
        "message": "Użytkownik ma zarejestrowane ruchy. Możesz go dezaktywować."
    }
    assert deactivated.json()["is_active"] is False


async def test_a_deactivated_user_keeps_their_movements_readable(
    client, session, admin_headers, ids
):
    user = await make_user(session, "jan", role="admin")
    await receive(client, await login(client, "jan"), ids)
    await client.put(
        f"/users/{user.uuid}", headers=admin_headers, json={"is_active": False}
    )

    listed = await client.get("/movements", headers=admin_headers)

    assert [m["user"]["username"] for m in listed.json()] == ["jan"]
