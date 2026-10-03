"""Stock counts (inwentaryzacja): today, one step, partial, with the sheet kept."""

from uuid import UUID, uuid4

import pytest
from sqlalchemy import insert

from app.models.area import Area
from app.models.pallet_type import PalletType
from app.models.quality import Quality
from app.models.user_area import user_areas
from tests.conftest import login, make_user, warehouse_today


@pytest.fixture
async def ids(session) -> dict[str, str]:
    rows = {
        "a": Area(name="Przyjęcia 445"),
        "b": Area(name="Wysyłka 445"),
        "eur": PalletType(name="EUR"),
        "chep": PalletType(name="CHEP", is_active=False),
        "I": Quality(name="I", sort_order=1),
        "II": Quality(name="II", sort_order=2),
        "old": Quality(name="Stara", sort_order=9, is_active=False),
    }
    session.add_all(rows.values())
    await session.commit()
    return {key: str(row.uuid) for key, row in rows.items()}


async def receive(client, headers, ids, quantity, quality="I", area="a"):
    response = await client.post(
        "/movements",
        headers=headers,
        json={
            "type": "RECEIPT",
            "area_uuid": ids[area],
            "lines": [
                {
                    "pallet_type_uuid": ids["eur"],
                    "quality_uuid": ids[quality],
                    "quantity": quantity,
                }
            ],
        },
    )
    assert response.status_code == 200, response.text


def counted(ids, quantity, quality="I", pallet_type="eur"):
    return {
        "pallet_type_uuid": ids.get(pallet_type, pallet_type),
        "quality_uuid": ids.get(quality, quality),
        "counted_quantity": quantity,
    }


async def count(client, headers, ids, *lines, area="a", **extra):
    return await client.post(
        "/inventories",
        headers=headers,
        json={"area_uuid": ids[area], "lines": list(lines), **extra},
    )


def sheet_of(response):
    return [
        (
            row["quality"]["name"],
            row["system_quantity"],
            row["counted_quantity"],
            row["difference"],
        )
        for row in response.json()["inventory_lines"]
    ]


def lines_of(response):
    return [(ln["quality"]["name"], ln["quantity"]) for ln in response.json()["lines"]]


# ---------- the count ----------


async def test_a_shortage_is_written_as_a_minus(client, admin_headers, ids):
    await receive(client, admin_headers, ids, 100)

    response = await count(
        client, admin_headers, ids, counted(ids, 90), comment="spis kwartalny"
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["type"], body["type_label"]) == ("INVENTORY", "Inwentaryzacja")
    assert body["operation_date"] == warehouse_today().isoformat()
    assert body["comment"] == "spis kwartalny"
    assert sheet_of(response) == [("I", 100, 90, -10)]
    assert lines_of(response) == [("I", -10)]


async def test_a_surplus_is_written_as_a_plus(client, admin_headers, ids):
    await receive(client, admin_headers, ids, 100)

    response = await count(client, admin_headers, ids, counted(ids, 110))

    assert sheet_of(response) == [("I", 100, 110, 10)]
    assert lines_of(response) == [("I", 10)]


async def test_a_matching_count_is_kept_without_lines(client, admin_headers, ids):
    await receive(client, admin_headers, ids, 100)

    response = await count(client, admin_headers, ids, counted(ids, 100))

    assert response.status_code == 200
    assert sheet_of(response) == [("I", 100, 100, 0)]
    assert lines_of(response) == []


async def test_pallets_never_entered_before(client, admin_headers, ids):
    response = await count(client, admin_headers, ids, counted(ids, 5, quality="II"))

    assert sheet_of(response) == [("II", 0, 5, 5)]


async def test_after_the_count_the_balance_is_what_was_counted(
    client, admin_headers, ids
):
    await receive(client, admin_headers, ids, 100)
    await count(client, admin_headers, ids, counted(ids, 90))

    sheet = await client.get(
        "/inventories/sheet", headers=admin_headers, params={"area_uuid": ids["a"]}
    )

    rows = {(r["pallet_type"]["name"], r["quality"]["name"]): r for r in sheet.json()}
    assert rows["EUR", "I"]["system_quantity"] == 90


async def test_only_counted_rows_change(client, admin_headers, ids):
    await receive(client, admin_headers, ids, 100, quality="I")
    await receive(client, admin_headers, ids, 30, quality="II")

    await count(client, admin_headers, ids, counted(ids, 80, quality="I"))
    sheet = await client.get(
        "/inventories/sheet", headers=admin_headers, params={"area_uuid": ids["a"]}
    )

    assert [(r["quality"]["name"], r["system_quantity"]) for r in sheet.json()] == [
        ("I", 80),
        ("II", 30),
    ]


async def test_a_count_belongs_to_one_area(client, admin_headers, ids):
    await receive(client, admin_headers, ids, 100, area="a")
    await receive(client, admin_headers, ids, 40, area="b")

    await count(client, admin_headers, ids, counted(ids, 0), area="b")
    sheet_a = await client.get(
        "/inventories/sheet", headers=admin_headers, params={"area_uuid": ids["a"]}
    )

    assert sheet_a.json()[0]["system_quantity"] == 100


async def test_several_rows_in_one_count(client, admin_headers, ids):
    await receive(client, admin_headers, ids, 100, quality="I")
    await receive(client, admin_headers, ids, 30, quality="II")

    response = await count(
        client,
        admin_headers,
        ids,
        counted(ids, 100, quality="I"),
        counted(ids, 25, quality="II"),
    )

    assert sheet_of(response) == [("I", 100, 100, 0), ("II", 30, 25, -5)]
    assert lines_of(response) == [("II", -5)]


# ---------- validation ----------


@pytest.mark.parametrize(
    ("lines", "message"),
    [
        ([], "Dodaj co najmniej jedną pozycję"),
        ([("I", -1, "eur")], "Policzona ilość nie może być ujemna"),
        ([("I", 1, "unknown")], "Nieznany typ palety"),
        ([("I", 1, "chep")], "Typ palety „CHEP” jest nieaktywny"),
        ([("unknown", 1, "eur")], "Nieznana jakość"),
        ([("old", 1, "eur")], "Jakość „Stara” jest nieaktywna"),
        ([("I", 1, "eur"), ("I", 2, "eur")], "Pozycja EUR / I występuje dwa razy"),
    ],
)
async def test_invalid_counts(client, admin_headers, ids, lines, message):
    unknown = str(uuid4())
    payload = [
        counted(
            ids,
            quantity,
            quality=unknown if quality == "unknown" else quality,
            pallet_type=unknown if pallet_type == "unknown" else pallet_type,
        )
        for quality, quantity, pallet_type in lines
    ]

    response = await count(client, admin_headers, ids, *payload)

    assert response.status_code == 400
    assert response.json() == {"message": message}


async def test_a_count_cannot_be_dated(client, admin_headers, ids):
    response = await count(
        client, admin_headers, ids, counted(ids, 1), operation_date="2020-01-01"
    )

    assert response.json()["operation_date"] == warehouse_today().isoformat()


async def test_not_through_the_movements_endpoint(client, admin_headers, ids):
    response = await client.post(
        "/movements",
        headers=admin_headers,
        json={
            "type": "INVENTORY",
            "area_uuid": ids["a"],
            "lines": [counted(ids, 1) | {"quantity": 1}],
        },
    )

    assert response.status_code == 400
    assert response.json() == {"message": "Inwentaryzację wprowadza się arkuszem spisu"}


# ---------- the empty sheet ----------


async def test_the_sheet_lists_every_active_type_and_quality(
    client, admin_headers, ids
):
    await receive(client, admin_headers, ids, 7, quality="II")

    response = await client.get(
        "/inventories/sheet", headers=admin_headers, params={"area_uuid": ids["a"]}
    )

    assert [
        (r["pallet_type"]["name"], r["quality"]["name"], r["system_quantity"])
        for r in response.json()
    ] == [("EUR", "I", 0), ("EUR", "II", 7)]


# ---------- who ----------


async def operator(client, session, *area_uuids, role="operator"):
    user = await make_user(session, "jan", role=role)
    if area_uuids:
        await session.execute(
            insert(user_areas),
            [{"user_uuid": user.uuid, "area_uuid": UUID(a)} for a in area_uuids],
        )
        await session.commit()
    return await login(client, "jan")


async def test_the_only_area_is_used_automatically(client, session, ids):
    headers = await operator(client, session, ids["b"])

    sheet = await client.get("/inventories/sheet", headers=headers)
    response = await client.post(
        "/inventories", headers=headers, json={"lines": [counted(ids, 3)]}
    )

    assert sheet.status_code == 200
    assert response.json()["area"]["name"] == "Wysyłka 445"


async def test_operator_counts_only_their_areas(client, session, ids):
    headers = await operator(client, session, ids["a"])

    sheet = await client.get(
        "/inventories/sheet", headers=headers, params={"area_uuid": ids["b"]}
    )
    response = await count(client, headers, ids, counted(ids, 1), area="b")

    assert sheet.status_code == response.status_code == 403


async def test_viewer_cannot_count(client, session, ids):
    headers = await operator(client, session, ids["a"], role="viewer")

    sheet = await client.get(
        "/inventories/sheet", headers=headers, params={"area_uuid": ids["a"]}
    )
    response = await count(client, headers, ids, counted(ids, 1))

    assert sheet.status_code == response.status_code == 403


# ---------- history ----------


async def test_counts_are_in_the_movement_history(client, admin_headers, ids):
    await receive(client, admin_headers, ids, 100)
    created = await count(client, admin_headers, ids, counted(ids, 95))

    listed = await client.get(
        "/movements", headers=admin_headers, params={"type": "INVENTORY"}
    )
    one = await client.get(
        f"/movements/{created.json()['uuid']}", headers=admin_headers
    )
    receipt = (
        await client.get(
            "/movements", headers=admin_headers, params={"type": "RECEIPT"}
        )
    ).json()[0]

    assert [m["uuid"] for m in listed.json()] == [created.json()["uuid"]]
    assert one.json() == created.json()
    assert receipt["inventory_lines"] is None


async def test_a_quality_used_only_in_a_matching_count_is_not_deleted(
    client, admin_headers, ids
):
    await count(client, admin_headers, ids, counted(ids, 0, quality="II"))

    response = await client.delete(f"/qualities/{ids['II']}", headers=admin_headers)

    assert response.status_code == 409
