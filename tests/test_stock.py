"""No balance may go below zero: per area, pallet type and quality."""

import pytest

from app.models.area import Area
from app.models.pallet_type import PalletType
from app.models.quality import Quality


@pytest.fixture
async def ids(session) -> dict[str, str]:
    rows = {
        "a": Area(name="Przyjęcia 445"),
        "b": Area(name="Wysyłka 445"),
        "eur": PalletType(name="EUR"),
        "I": Quality(name="I", sort_order=1),
        "II": Quality(name="II", sort_order=2),
    }
    session.add_all(rows.values())
    await session.commit()
    return {key: str(row.uuid) for key, row in rows.items()}


def ln(ids, quantity, quality="I", to=None):
    line = {
        "pallet_type_uuid": ids["eur"],
        "quality_uuid": ids[quality],
        "quantity": quantity,
    }
    if to:
        line["to_quality_uuid"] = ids[to]
    return line


async def post(client, headers, ids, kind, area, *lines, comment=None):
    return await client.post(
        "/movements",
        headers=headers,
        json={
            "type": kind,
            "area_uuid": ids[area],
            "comment": comment,
            "lines": list(lines),
        },
    )


async def count(client, headers):
    response = await client.get("/movements", headers=headers)
    return int(response.headers["X-Total-Count"])


async def test_shipment_beyond_stock_is_refused_and_not_saved(
    client, admin_headers, ids
):
    await post(client, admin_headers, ids, "RECEIPT", "a", ln(ids, 100))

    response = await post(client, admin_headers, ids, "SHIPMENT", "a", ln(ids, 150))

    assert response.status_code == 400
    assert response.json() == {
        "message": "Niewystarczająca ilość EUR / I w obszarze „Przyjęcia 445”:"
        " dostępne 100, potrzeba 150"
    }
    assert await count(client, admin_headers) == 1


async def test_shipping_everything_leaves_zero(client, admin_headers, ids):
    await post(client, admin_headers, ids, "RECEIPT", "a", ln(ids, 100))

    first = await post(client, admin_headers, ids, "SHIPMENT", "a", ln(ids, 100))
    second = await post(client, admin_headers, ids, "SHIPMENT", "a", ln(ids, 1))

    assert first.status_code == 200
    assert second.status_code == 400
    assert "dostępne 0, potrzeba 1" in second.json()["message"]


async def test_stock_belongs_to_one_area(client, admin_headers, ids):
    await post(client, admin_headers, ids, "RECEIPT", "a", ln(ids, 100))

    response = await post(client, admin_headers, ids, "SHIPMENT", "b", ln(ids, 1))

    assert response.status_code == 400
    assert "w obszarze „Wysyłka 445”: dostępne 0" in response.json()["message"]


async def test_stock_belongs_to_one_quality(client, admin_headers, ids):
    await post(client, admin_headers, ids, "RECEIPT", "a", ln(ids, 100))

    response = await post(
        client, admin_headers, ids, "SHIPMENT", "a", ln(ids, 1, quality="II")
    )

    assert response.status_code == 400
    assert "EUR / II" in response.json()["message"]


async def test_lines_of_one_document_add_up(client, admin_headers, ids):
    await post(client, admin_headers, ids, "RECEIPT", "a", ln(ids, 100))

    response = await post(
        client, admin_headers, ids, "SHIPMENT", "a", ln(ids, 60), ln(ids, 60)
    )

    assert response.status_code == 400
    assert "dostępne 100, potrzeba 120" in response.json()["message"]


async def test_reclassification_beyond_stock_is_refused(client, admin_headers, ids):
    await post(client, admin_headers, ids, "RECEIPT", "a", ln(ids, 10))

    response = await post(
        client, admin_headers, ids, "RECLASSIFICATION", "a", ln(ids, 11, to="II")
    )

    assert response.status_code == 400
    assert "EUR / I" in response.json()["message"]
    assert "dostępne 10, potrzeba 11" in response.json()["message"]


async def test_reclassified_pallets_can_then_be_shipped(client, admin_headers, ids):
    await post(client, admin_headers, ids, "RECEIPT", "a", ln(ids, 10))
    await post(client, admin_headers, ids, "RECLASSIFICATION", "a", ln(ids, 4, to="II"))

    ship_ii = await post(
        client, admin_headers, ids, "SHIPMENT", "a", ln(ids, 4, quality="II")
    )
    ship_i_too_many = await post(
        client, admin_headers, ids, "SHIPMENT", "a", ln(ids, 7)
    )

    assert ship_ii.status_code == 200
    assert ship_i_too_many.status_code == 400
    assert "dostępne 6, potrzeba 7" in ship_i_too_many.json()["message"]


async def test_a_minus_correction_beyond_stock_is_refused(client, admin_headers, ids):
    await post(client, admin_headers, ids, "RECEIPT", "a", ln(ids, 5))

    within = await post(
        client, admin_headers, ids, "CORRECTION", "a", ln(ids, -5), comment="spis"
    )
    beyond = await post(
        client, admin_headers, ids, "CORRECTION", "a", ln(ids, -1), comment="spis"
    )

    assert within.status_code == 200
    assert beyond.status_code == 400


async def test_receipts_and_plus_corrections_are_never_blocked(
    client, admin_headers, ids
):
    receipt = await post(client, admin_headers, ids, "RECEIPT", "b", ln(ids, 1))
    correction = await post(
        client, admin_headers, ids, "CORRECTION", "b", ln(ids, 3), comment="spis"
    )

    assert receipt.status_code == correction.status_code == 200
