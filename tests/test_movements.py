"""Movement documents: receipts, LM purchases, shipments and corrections."""

from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import insert

from app.models.area import Area
from app.models.pallet_type import PalletType
from app.models.quality import Quality
from app.models.user_area import user_areas
from tests.conftest import login, make_user, warehouse_today


@dataclass
class World:
    area_a: str
    area_b: str
    inactive_area: str
    eur: str
    inactive_type: str
    q1: str
    q2: str
    inactive_quality: str


@pytest.fixture
async def world(session) -> World:
    rows = {
        "area_a": Area(name="Przyjęcia 445"),
        "area_b": Area(name="Wysyłka 445"),
        "inactive_area": Area(name="Stary", is_active=False),
        "eur": PalletType(name="EUR"),
        "inactive_type": PalletType(name="CHEP", is_active=False),
        "q1": Quality(name="I", sort_order=1),
        "q2": Quality(name="II", sort_order=2),
        "inactive_quality": Quality(name="X", sort_order=9, is_active=False),
    }
    session.add_all(rows.values())
    await session.commit()
    return World(**{key: str(row.uuid) for key, row in rows.items()})


async def operator(client, session, world, *areas, role="operator"):
    """Create a user with the given area keys assigned and log them in."""
    user = await make_user(session, "jan", role=role)
    if areas:
        await session.execute(
            insert(user_areas),
            [
                {"user_uuid": user.uuid, "area_uuid": UUID(getattr(world, key))}
                for key in areas
            ],
        )
        await session.commit()
    return await login(client, "jan")


def line(world, quantity, pallet_type=None, quality=None):
    return {
        "pallet_type_uuid": pallet_type or world.eur,
        "quality_uuid": quality or world.q1,
        "quantity": quantity,
    }


async def post(client, headers, **payload):
    return await client.post("/movements", headers=headers, json=payload)


async def receive(client, headers, world, area_key, quantity):
    """Put EUR / I pallets into an area, so they can be shipped or corrected."""
    response = await post(
        client,
        headers,
        type="RECEIPT",
        area_uuid=getattr(world, area_key),
        lines=[line(world, quantity)],
    )
    assert response.status_code == 200, response.text


# ---------- the movement kinds ----------


async def test_receipt_adds_pallets(client, admin_headers, world):
    response = await post(
        client,
        admin_headers,
        type="RECEIPT",
        area_uuid=world.area_a,
        document_number=" PZ/12 ",
        comment="dostawa",
        lines=[line(world, 320)],
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["type"] == "RECEIPT"
    assert body["type_label"] == "Przyjęcie na magazyn"
    assert body["area"]["name"] == "Przyjęcia 445"
    assert body["user"]["username"] == "admin"
    assert body["operation_date"] == warehouse_today().isoformat()
    assert body["document_number"] == "PZ/12"
    assert body["comment"] == "dostawa"
    assert [
        (ln["pallet_type"]["name"], ln["quality"]["name"], ln["quantity"])
        for ln in body["lines"]
    ] == [("EUR", "I", 320)]


async def test_lm_purchase_adds_pallets(client, admin_headers, world):
    response = await post(
        client,
        admin_headers,
        type="LM_PURCHASE",
        area_uuid=world.area_a,
        lines=[line(world, 50)],
    )

    assert response.json()["type_label"] == "Zakup LM"
    assert response.json()["lines"][0]["quantity"] == 50


async def test_shipment_is_stored_as_a_minus(client, admin_headers, world):
    await receive(client, admin_headers, world, "area_b", 40)

    response = await post(
        client,
        admin_headers,
        type="SHIPMENT",
        area_uuid=world.area_b,
        lines=[line(world, 40)],
    )

    assert response.json()["type_label"] == "Wysyłka z magazynu"
    assert response.json()["lines"][0]["quantity"] == -40


@pytest.mark.parametrize("quantity", [15, -15])
async def test_correction_keeps_its_sign(client, admin_headers, world, quantity):
    await receive(client, admin_headers, world, "area_a", 15)

    response = await post(
        client,
        admin_headers,
        type="CORRECTION",
        area_uuid=world.area_a,
        comment="spis ręczny",
        lines=[line(world, quantity)],
    )

    assert response.status_code == 200, response.text
    assert response.json()["lines"][0]["quantity"] == quantity


async def test_a_document_keeps_several_lines_in_order(client, admin_headers, world):
    response = await post(
        client,
        admin_headers,
        type="RECEIPT",
        area_uuid=world.area_a,
        lines=[line(world, 320), line(world, 30, quality=world.q2)],
    )

    assert [
        (ln["quality"]["name"], ln["quantity"]) for ln in response.json()["lines"]
    ] == [("I", 320), ("II", 30)]


# ---------- validation ----------


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({"type": "RECEIPT", "lines": []}, "Dodaj co najmniej jedną pozycję"),
        (
            {"type": "RECEIPT", "lines": [{"quantity": 0}]},
            "Ilość musi być większa od zera",
        ),
        (
            {"type": "SHIPMENT", "lines": [{"quantity": -5}]},
            "Ilość musi być większa od zera",
        ),
        (
            {"type": "CORRECTION", "comment": "x", "lines": [{"quantity": 0}]},
            "Ilość korekty nie może być zerowa",
        ),
        (
            {"type": "CORRECTION", "comment": "  ", "lines": [{"quantity": 3}]},
            "Podaj powód korekty w komentarzu",
        ),
        (
            {"type": "RECEIPT", "lines": [{"quantity": 1, "pallet_type": "unknown"}]},
            "Nieznany typ palety",
        ),
        (
            {"type": "RECEIPT", "lines": [{"quantity": 1, "pallet_type": "inactive"}]},
            "Typ palety „CHEP” jest nieaktywny",
        ),
        (
            {"type": "RECEIPT", "lines": [{"quantity": 1, "quality": "unknown"}]},
            "Nieznana jakość",
        ),
        (
            {"type": "RECEIPT", "lines": [{"quantity": 1, "quality": "inactive"}]},
            "Jakość „X” jest nieaktywna",
        ),
    ],
)
async def test_invalid_documents(client, admin_headers, world, payload, message):
    pallet_types = {"unknown": str(uuid4()), "inactive": world.inactive_type}
    qualities = {"unknown": str(uuid4()), "inactive": world.inactive_quality}
    lines = [
        line(
            world,
            raw["quantity"],
            pallet_type=pallet_types.get(raw.get("pallet_type")),
            quality=qualities.get(raw.get("quality")),
        )
        for raw in payload["lines"]
    ]

    response = await post(
        client,
        admin_headers,
        **{**payload, "lines": lines},
        area_uuid=world.area_a,
    )

    assert response.status_code == 400
    assert response.json() == {"message": message}


async def test_unknown_type_is_rejected(client, admin_headers, world):
    response = await post(
        client, admin_headers, type="TELEPORT", area_uuid=world.area_a, lines=[]
    )

    assert response.status_code == 422
    assert response.json()["message"] == "Nieprawidłowe dane: type"


async def test_operation_date_in_the_past_is_fine(client, admin_headers, world):
    yesterday = (warehouse_today() - timedelta(days=1)).isoformat()

    response = await post(
        client,
        admin_headers,
        type="RECEIPT",
        area_uuid=world.area_a,
        operation_date=yesterday,
        lines=[line(world, 1)],
    )

    assert response.json()["operation_date"] == yesterday


async def test_operation_date_in_the_future_is_rejected(client, admin_headers, world):
    tomorrow = (warehouse_today() + timedelta(days=1)).isoformat()

    response = await post(
        client,
        admin_headers,
        type="RECEIPT",
        area_uuid=world.area_a,
        operation_date=tomorrow,
        lines=[line(world, 1)],
    )

    assert response.status_code == 400
    assert response.json() == {"message": "Data operacji nie może być z przyszłości"}


# ---------- areas ----------


async def test_the_only_area_is_used_automatically(client, session, world):
    headers = await operator(client, session, world, "area_b")

    response = await post(client, headers, type="RECEIPT", lines=[line(world, 5)])

    assert response.status_code == 200, response.text
    assert response.json()["area"]["name"] == "Wysyłka 445"


async def test_with_several_areas_one_must_be_chosen(client, session, world):
    headers = await operator(client, session, world, "area_a", "area_b")

    response = await post(client, headers, type="RECEIPT", lines=[line(world, 5)])

    assert response.status_code == 400
    assert response.json() == {"message": "Wybierz obszar"}


async def test_operator_cannot_use_an_area_not_assigned(client, session, world):
    headers = await operator(client, session, world, "area_a")

    response = await post(
        client, headers, type="RECEIPT", area_uuid=world.area_b, lines=[line(world, 5)]
    )

    assert response.status_code == 403
    assert response.json() == {"message": "Brak dostępu do obszaru"}


async def test_admin_may_use_any_area(client, admin_headers, world):
    response = await post(
        client,
        admin_headers,
        type="RECEIPT",
        area_uuid=world.area_b,
        lines=[line(world, 5)],
    )

    assert response.status_code == 200


async def test_an_inactive_area_is_rejected(client, admin_headers, world):
    response = await post(
        client,
        admin_headers,
        type="RECEIPT",
        area_uuid=world.inactive_area,
        lines=[line(world, 5)],
    )

    assert response.status_code == 400
    assert response.json() == {"message": "Obszar „Stary” jest nieaktywny"}


async def test_viewer_cannot_enter_movements(client, session, world):
    headers = await operator(client, session, world, "area_a", role="viewer")

    response = await post(
        client, headers, type="RECEIPT", area_uuid=world.area_a, lines=[line(world, 5)]
    )

    assert response.status_code == 403
    assert response.json() == {"message": "Brak uprawnień"}


# ---------- reading ----------


async def test_list_is_newest_first_with_a_total(client, admin_headers, world):
    old = (warehouse_today() - timedelta(days=3)).isoformat()
    for operation_date, quantity in [(old, 1), (None, 2), (None, 3)]:
        await post(
            client,
            admin_headers,
            type="RECEIPT",
            area_uuid=world.area_a,
            operation_date=operation_date,
            lines=[line(world, quantity)],
        )

    response = await client.get("/movements?limit=2", headers=admin_headers)

    assert response.headers["X-Total-Count"] == "3"
    assert [m["lines"][0]["quantity"] for m in response.json()] == [3, 2]

    rest = await client.get("/movements?limit=2&offset=2", headers=admin_headers)
    assert [m["lines"][0]["quantity"] for m in rest.json()] == [1]


async def test_list_filters(client, admin_headers, world):
    old = (warehouse_today() - timedelta(days=3)).isoformat()
    await post(
        client,
        admin_headers,
        type="RECEIPT",
        area_uuid=world.area_a,
        operation_date=old,
        lines=[line(world, 1)],
    )
    await receive(client, admin_headers, world, "area_b", 2)
    await post(
        client,
        admin_headers,
        type="SHIPMENT",
        area_uuid=world.area_b,
        lines=[line(world, 2)],
    )

    by_type = await client.get("/movements?type=SHIPMENT", headers=admin_headers)
    by_area = await client.get(
        f"/movements?area_uuid={world.area_a}", headers=admin_headers
    )
    by_date = await client.get(f"/movements?date_to={old}", headers=admin_headers)

    assert [m["type"] for m in by_type.json()] == ["SHIPMENT"]
    assert [m["area"]["name"] for m in by_area.json()] == ["Przyjęcia 445"]
    assert [m["operation_date"] for m in by_date.json()] == [old]


async def test_operator_sees_only_their_areas(client, session, admin_headers, world):
    await post(
        client,
        admin_headers,
        type="RECEIPT",
        area_uuid=world.area_a,
        lines=[line(world, 1)],
    )
    other = await post(
        client,
        admin_headers,
        type="RECEIPT",
        area_uuid=world.area_b,
        lines=[line(world, 2)],
    )
    headers = await operator(client, session, world, "area_a")

    listed = await client.get("/movements", headers=headers)
    foreign_list = await client.get(
        f"/movements?area_uuid={world.area_b}", headers=headers
    )
    foreign_one = await client.get(
        f"/movements/{other.json()['uuid']}", headers=headers
    )

    assert [m["area"]["name"] for m in listed.json()] == ["Przyjęcia 445"]
    assert listed.headers["X-Total-Count"] == "1"
    assert foreign_list.status_code == foreign_one.status_code == 403


async def test_viewer_sees_every_area(client, session, admin_headers, world):
    for area in (world.area_a, world.area_b):
        await post(
            client,
            admin_headers,
            type="RECEIPT",
            area_uuid=area,
            lines=[line(world, 1)],
        )
    headers = await operator(client, session, world, role="viewer")

    listed = await client.get("/movements", headers=headers)

    assert listed.headers["X-Total-Count"] == "2"


async def test_get_one_movement(client, admin_headers, world):
    created = await post(
        client,
        admin_headers,
        type="RECEIPT",
        area_uuid=world.area_a,
        lines=[line(world, 7)],
    )

    response = await client.get(
        f"/movements/{created.json()['uuid']}", headers=admin_headers
    )

    assert response.json() == created.json()


async def test_get_a_missing_movement(client, admin_headers):
    response = await client.get(f"/movements/{uuid4()}", headers=admin_headers)

    assert response.status_code == 404
    assert response.json() == {"message": "Nie znaleziono ruchu"}


async def test_a_saved_movement_cannot_be_edited_or_deleted(
    client, admin_headers, world
):
    created = await post(
        client,
        admin_headers,
        type="RECEIPT",
        area_uuid=world.area_a,
        lines=[line(world, 7)],
    )
    url = f"/movements/{created.json()['uuid']}"

    assert (await client.put(url, headers=admin_headers, json={})).status_code == 405
    assert (await client.delete(url, headers=admin_headers)).status_code == 405


async def test_movement_types_have_polish_labels(client, admin_headers):
    response = await client.get("/movements/types", headers=admin_headers)

    assert response.json() == [
        {"code": "RECEIPT", "label": "Przyjęcie na magazyn"},
        {"code": "LM_PURCHASE", "label": "Zakup LM"},
        {"code": "SHIPMENT", "label": "Wysyłka z magazynu"},
        {"code": "CORRECTION", "label": "Korekta"},
        {"code": "RECLASSIFICATION", "label": "Przeksięgowanie kategorii"},
        {"code": "INVENTORY", "label": "Inwentaryzacja"},
    ]
