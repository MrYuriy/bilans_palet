"""Przeksięgowanie kategorii: pallets move to a worse quality only."""

from uuid import uuid4

import pytest

from app.models.area import Area
from app.models.pallet_type import PalletType
from app.models.quality import Quality


@pytest.fixture
async def ids(session) -> dict[str, str]:
    rows = {
        "area": Area(name="Przyjęcia 445"),
        "eur": PalletType(name="EUR"),
        "I": Quality(name="I", sort_order=1),
        "II": Quality(name="II", sort_order=2),
        "III": Quality(name="III", sort_order=3),
        "old": Quality(name="Stara", sort_order=9, is_active=False),
    }
    session.add_all(rows.values())
    await session.commit()
    return {key: str(row.uuid) for key, row in rows.items()}


@pytest.fixture
async def stocked(client, admin_headers, ids):
    """100 EUR pallets of each quality in the area, so there is something to move."""
    response = await client.post(
        "/movements",
        headers=admin_headers,
        json={
            "type": "RECEIPT",
            "area_uuid": ids["area"],
            "lines": [
                {
                    "pallet_type_uuid": ids["eur"],
                    "quality_uuid": ids[q],
                    "quantity": 100,
                }
                for q in ("I", "II", "III")
            ],
        },
    )
    assert response.status_code == 200, response.text


async def reclassify(client, headers, ids, lines):
    return await client.post(
        "/movements",
        headers=headers,
        json={"type": "RECLASSIFICATION", "area_uuid": ids["area"], "lines": lines},
    )


def move(ids, quantity, source, target):
    return {
        "pallet_type_uuid": ids["eur"],
        "quality_uuid": ids[source],
        "to_quality_uuid": ids.get(target, target),
        "quantity": quantity,
    }


def lines_of(response):
    return [(ln["quality"]["name"], ln["quantity"]) for ln in response.json()["lines"]]


@pytest.mark.parametrize(
    ("source", "target"), [("I", "II"), ("I", "III"), ("II", "III")]
)
async def test_moves_to_a_worse_quality(
    client, admin_headers, ids, stocked, source, target
):
    response = await reclassify(
        client, admin_headers, ids, [move(ids, 50, source, target)]
    )

    assert response.status_code == 200, response.text
    assert response.json()["type_label"] == "Przeksięgowanie kategorii"
    assert lines_of(response) == [(source, -50), (target, 50)]


async def test_several_moves_in_one_document(client, admin_headers, ids, stocked):
    response = await reclassify(
        client,
        admin_headers,
        ids,
        [move(ids, 50, "I", "II"), move(ids, 8, "II", "III")],
    )

    assert lines_of(response) == [("I", -50), ("II", 50), ("II", -8), ("III", 8)]


@pytest.mark.parametrize(("source", "target"), [("II", "I"), ("III", "II"), ("I", "I")])
async def test_never_to_a_better_or_the_same_quality(
    client, admin_headers, ids, source, target
):
    response = await reclassify(
        client, admin_headers, ids, [move(ids, 5, source, target)]
    )

    assert response.status_code == 400
    assert response.json() == {
        "message": "Przeksięgowanie możliwe tylko do gorszej jakości"
    }


@pytest.mark.parametrize(
    ("target", "message"),
    [
        (None, "Podaj jakość docelową przeksięgowania"),
        (str(uuid4()), "Nieznana jakość"),
        ("old", "Jakość „Stara” jest nieaktywna"),
    ],
)
async def test_target_quality_must_be_valid(
    client, admin_headers, ids, target, message
):
    response = await reclassify(client, admin_headers, ids, [move(ids, 5, "I", target)])

    assert response.status_code == 400
    assert response.json() == {"message": message}


@pytest.mark.parametrize("quantity", [0, -5])
async def test_quantity_must_be_positive(client, admin_headers, ids, quantity):
    response = await reclassify(
        client, admin_headers, ids, [move(ids, quantity, "I", "II")]
    )

    assert response.status_code == 400
    assert response.json() == {"message": "Ilość musi być większa od zera"}


async def test_target_quality_only_on_a_reclassification(client, admin_headers, ids):
    response = await client.post(
        "/movements",
        headers=admin_headers,
        json={
            "type": "RECEIPT",
            "area_uuid": ids["area"],
            "lines": [move(ids, 5, "I", "II")],
        },
    )

    assert response.status_code == 400
    assert response.json() == {
        "message": "Jakość docelowa dotyczy tylko przeksięgowania"
    }
