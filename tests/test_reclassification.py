"""Re-classification (przeksięgowanie): a quantity moves from one carrier type
to another, in any direction."""

import pytest

from tests.conftest import line, login, make_user, move, stock_of


@pytest.mark.parametrize(
    ("source", "target"),
    [
        ("euro", "damaged"),  # damaged in the yard
        ("damaged", "euro"),  # back after repair
        ("euro", "single"),  # across groups
        ("single", "scrap"),
    ],
)
async def test_any_direction_moves_the_quantity(
    client, admin_headers, carriers, source, target
):
    response = await move(
        client,
        admin_headers,
        "RECLASSIFICATION",
        line(getattr(carriers, source), 10, to=getattr(carriers, target)),
    )

    assert response.status_code == 200, response.text
    assert [
        (ln["carrier_type"]["uuid"], ln["quantity"]) for ln in response.json()["lines"]
    ] == [(getattr(carriers, source), -10), (getattr(carriers, target), 10)]


async def test_the_total_stock_does_not_change(client, admin_headers, carriers):
    await move(client, admin_headers, "OTHER_RECEIPT", line(carriers.euro, 50))

    await move(
        client,
        admin_headers,
        "RECLASSIFICATION",
        line(carriers.euro, 20, to=carriers.damaged),
    )

    current = await stock_of(client, admin_headers, carriers.euro, carriers.damaged)
    assert (current["EURO"], current["EURO uszkodzone"]) == (30, 20)


async def test_not_onto_the_same_type(client, admin_headers, carriers):
    response = await move(
        client,
        admin_headers,
        "RECLASSIFICATION",
        line(carriers.euro, 10, to=carriers.euro),
    )

    assert response.status_code == 400
    assert response.json() == {
        "message": "Przeksięgowanie wymaga dwóch różnych typów nośników"
    }


async def test_a_target_is_required(client, admin_headers, carriers):
    response = await move(
        client, admin_headers, "RECLASSIFICATION", line(carriers.euro, 10)
    )

    assert response.status_code == 400
    assert response.json() == {"message": "Podaj typ docelowy przeksięgowania"}


async def test_an_inactive_target_is_refused(client, admin_headers, carriers):
    response = await move(
        client,
        admin_headers,
        "RECLASSIFICATION",
        line(carriers.euro, 10, to=carriers.inactive),
    )

    assert response.status_code == 400
    assert response.json() == {"message": "Typ nośnika „CHEP” jest nieaktywny"}


async def test_a_note_is_required(client, admin_headers, carriers):
    response = await move(
        client,
        admin_headers,
        "RECLASSIFICATION",
        line(carriers.euro, 10, to=carriers.damaged),
        comment=None,
    )

    assert response.status_code == 400
    assert response.json() == {"message": "„Przeksięgowanie” wymaga notatki"}


async def test_a_viewer_cannot_reclassify(client, session, carriers):
    await make_user(session, "jan", role="viewer")
    headers = await login(client, "jan")

    response = await move(
        client, headers, "RECLASSIFICATION", line(carriers.euro, 1, to=carriers.damaged)
    )

    assert response.status_code == 403
