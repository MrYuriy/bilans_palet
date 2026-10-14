"""Stock counts (inwentaryzacja), also the starting stock: the count sheet,
the difference, and what stays in the history."""

import pytest

from tests.conftest import line, login, make_user, move, stock_of, warehouse_today


def counted(carrier_type: str, quantity: int) -> dict:
    return {"carrier_type_uuid": carrier_type, "counted_quantity": quantity}


async def count(client, headers, *lines, **fields):
    return await client.post(
        "/inventories", headers=headers, json={"lines": list(lines), **fields}
    )


async def receive(client, headers, carrier_type: str, quantity: int):
    response = await move(
        client, headers, "OTHER_RECEIPT", line(carrier_type, quantity)
    )
    assert response.status_code == 200, response.text


async def test_a_shortage_is_written_as_a_minus(client, admin_headers, carriers):
    await receive(client, admin_headers, carriers.euro, 100)

    response = await count(
        client, admin_headers, counted(carriers.euro, 96), document_number=" SP/1 "
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["type"], body["type_label"]) == ("INVENTORY", "Inwentaryzacja")
    assert body["operation_date"] == warehouse_today().isoformat()
    assert body["document_number"] == "SP/1"
    assert [(ln["carrier_type"]["name"], ln["quantity"]) for ln in body["lines"]] == [
        ("EURO", -4)
    ]
    assert body["inventory_lines"] == [
        {
            "carrier_type": {"uuid": carriers.euro, "name": "EURO"},
            "system_quantity": 100,
            "counted_quantity": 96,
            "difference": -4,
        }
    ]


async def test_a_surplus_is_written_as_a_plus(client, admin_headers, carriers):
    await receive(client, admin_headers, carriers.euro, 100)

    response = await count(client, admin_headers, counted(carriers.euro, 103))

    assert response.json()["lines"][0]["quantity"] == 3


async def test_a_matching_count_is_kept_without_lines(client, admin_headers, carriers):
    await receive(client, admin_headers, carriers.euro, 100)

    response = await count(client, admin_headers, counted(carriers.euro, 100))

    body = response.json()
    assert body["lines"] == []
    assert [r["difference"] for r in body["inventory_lines"]] == [0]


async def test_the_starting_stock_is_a_first_count(client, admin_headers, carriers):
    response = await count(
        client,
        admin_headers,
        counted(carriers.euro, 1200),
        counted(carriers.damaged, 40),
        counted(carriers.single, 300),
        comment="Stan początkowy",
    )

    assert response.status_code == 200, response.text
    current = await stock_of(
        client, admin_headers, carriers.euro, carriers.damaged, carriers.single
    )
    assert (current["EURO"], current["EURO uszkodzone"], current["Jednorazowe"]) == (
        1200,
        40,
        300,
    )


async def test_a_count_brings_a_negative_stock_back(client, admin_headers, carriers):
    await move(client, admin_headers, "ECOM_TRANSFER", line(carriers.euro, 30))

    response = await count(client, admin_headers, counted(carriers.euro, 10))

    assert response.json()["lines"][0]["quantity"] == 40
    assert (await stock_of(client, admin_headers))["EURO"] == 10


async def test_only_counted_rows_change(client, admin_headers, carriers):
    await receive(client, admin_headers, carriers.euro, 100)
    await receive(client, admin_headers, carriers.single, 50)

    await count(client, admin_headers, counted(carriers.euro, 90))

    current = await stock_of(client, admin_headers)
    assert (current["EURO"], current["Jednorazowe"]) == (90, 50)


@pytest.mark.parametrize(
    ("lines", "message"),
    [
        ([], "Dodaj co najmniej jedną pozycję"),
        ([("euro", -1)], "Policzona ilość nie może być ujemna"),
        ([("euro", 1), ("euro", 2)], "Pozycja EURO występuje dwa razy"),
        ([("inactive", 1)], "Typ nośnika „CHEP” jest nieaktywny"),
    ],
)
async def test_invalid_counts(client, admin_headers, carriers, lines, message):
    response = await count(
        client,
        admin_headers,
        *(counted(getattr(carriers, t), q) for t, q in lines),
    )

    assert response.status_code == 400
    assert response.json() == {"message": message}


async def test_the_sheet_lists_every_active_type(client, admin_headers, carriers):
    await receive(client, admin_headers, carriers.euro, 70)

    response = await client.get("/inventories/sheet", headers=admin_headers)

    assert response.status_code == 200, response.text
    assert [
        (r["group"]["name"], r["carrier_type"]["name"], r["system_quantity"])
        for r in response.json()
    ] == [
        ("EUR", "EURO", 70),
        ("EUR", "EURO uszkodzone", 0),
        ("EUR", "EURO utylizacja", 0),
        ("Jednorazowe", "Jednorazowe", 0),
    ]


async def test_a_viewer_cannot_count(client, session, carriers):
    await make_user(session, "jan", role="viewer")
    headers = await login(client, "jan")

    sheet = await client.get("/inventories/sheet", headers=headers)
    approve = await count(client, headers, counted(carriers.euro, 1))

    assert sheet.status_code == approve.status_code == 403


async def test_counts_are_in_the_movement_history(client, admin_headers, carriers):
    await count(client, admin_headers, counted(carriers.euro, 5))

    listed = await client.get("/movements?type=INVENTORY", headers=admin_headers)

    assert [m["type_label"] for m in listed.json()] == ["Inwentaryzacja"]
    assert listed.json()[0]["inventory_lines"][0]["counted_quantity"] == 5
