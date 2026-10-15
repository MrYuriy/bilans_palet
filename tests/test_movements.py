"""Movement documents: the operations, their signs and rules, and the register."""

from datetime import timedelta
from uuid import uuid4

import pytest

from tests.conftest import line, login, make_user, move, warehouse_today

# ---------- the operations ----------


@pytest.mark.parametrize(
    ("kind", "label", "stored"),
    [
        ("PRODUCER_RECEIPT", "Przyjęcie od producentów EURO", 40),
        ("PRODUCER_SHIPMENT", "Wysyłka do producentów EURO", -40),
        ("ECOM_TRANSFER", "Przesunięcie na ECOM", -40),
        ("OTHER_RECEIPT", "Inne — przyjęcie", 40),
        ("OTHER_SHIPMENT", "Inne — wydanie", -40),
    ],
)
async def test_each_operation_adds_or_takes(
    client, admin_headers, carriers, kind, label, stored
):
    response = await move(client, admin_headers, kind, line(carriers.euro, 40))

    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["type"], body["type_label"]) == (kind, label)
    assert [(ln["carrier_type"]["name"], ln["quantity"]) for ln in body["lines"]] == [
        ("EURO", stored)
    ]


async def test_a_movement_keeps_its_details(client, admin_headers, carriers):
    response = await move(
        client,
        admin_headers,
        "PRODUCER_SHIPMENT",
        line(carriers.damaged, 12),
        line(carriers.scrap, 3),
        document_number=" WZ/12 ",
        comment="  do naprawy ",
    )

    body = response.json()
    assert body["user"]["username"] == "admin"
    assert body["operation_date"] == warehouse_today().isoformat()
    assert (body["document_number"], body["comment"]) == ("WZ/12", "do naprawy")
    assert [(ln["carrier_type"]["name"], ln["quantity"]) for ln in body["lines"]] == [
        ("EURO uszkodzone", -12),
        ("EURO utylizacja", -3),
    ]


@pytest.mark.parametrize("quantity", [15, -15])
async def test_a_correction_keeps_its_sign(client, admin_headers, carriers, quantity):
    response = await move(
        client, admin_headers, "CORRECTION", line(carriers.euro, quantity)
    )

    assert response.status_code == 200, response.text
    assert response.json()["lines"][0]["quantity"] == quantity


async def test_the_stock_may_go_below_zero(client, admin_headers, carriers):
    response = await move(
        client, admin_headers, "ECOM_TRANSFER", line(carriers.euro, 500)
    )

    assert response.status_code == 200, response.text
    current = (await client.get("/balances/current", headers=admin_headers)).json()
    assert current["groups"][0]["rows"][0]["quantity"] == -500


async def test_a_producer_receipt_is_only_for_counted_types(
    client, admin_headers, carriers
):
    single = await move(
        client, admin_headers, "PRODUCER_RECEIPT", line(carriers.single, 5)
    )
    damaged = await move(
        client, admin_headers, "PRODUCER_RECEIPT", line(carriers.damaged, 5)
    )

    assert single.status_code == 200, single.text
    assert damaged.status_code == 400
    assert damaged.json() == {
        "message": "„Przyjęcie od producentów EURO” dotyczy tylko typów liczonych"
        " w raportach, nie „EURO uszkodzone”"
    }


@pytest.mark.parametrize(
    ("kind", "label"),
    [
        ("OTHER_RECEIPT", "Inne — przyjęcie"),
        ("OTHER_SHIPMENT", "Inne — wydanie"),
        ("CORRECTION", "Korekta stanu"),
    ],
)
async def test_some_operations_need_a_note(
    client, admin_headers, carriers, kind, label
):
    response = await move(
        client, admin_headers, kind, line(carriers.euro, 3), comment="   "
    )

    assert response.status_code == 400
    assert response.json() == {"message": f"„{label}” wymaga notatki"}


@pytest.mark.parametrize("kind", ["PRODUCER_RECEIPT", "ECOM_TRANSFER"])
async def test_others_take_a_note_but_do_not_need_it(
    client, admin_headers, carriers, kind
):
    response = await move(
        client, admin_headers, kind, line(carriers.euro, 3), comment=None
    )

    assert response.status_code == 200, response.text
    assert response.json()["comment"] is None


# ---------- validation ----------


@pytest.mark.parametrize(
    ("kind", "lines", "message"),
    [
        ("ECOM_TRANSFER", [], "Dodaj co najmniej jedną pozycję"),
        ("ECOM_TRANSFER", [("euro", 0)], "Ilość musi być większa od zera"),
        ("OTHER_RECEIPT", [("euro", -5)], "Ilość musi być większa od zera"),
        ("CORRECTION", [("euro", 0)], "Ilość korekty nie może być zerowa"),
        ("ECOM_TRANSFER", [("unknown", 1)], "Nieznany typ nośnika"),
        ("ECOM_TRANSFER", [("inactive", 1)], "Typ nośnika „CHEP” jest nieaktywny"),
    ],
)
async def test_invalid_documents(client, admin_headers, carriers, kind, lines, message):
    types = {
        "euro": carriers.euro,
        "inactive": carriers.inactive,
        "unknown": str(uuid4()),
    }

    response = await move(
        client, admin_headers, kind, *(line(types[t], q) for t, q in lines)
    )

    assert response.status_code == 400
    assert response.json() == {"message": message}


async def test_a_target_type_belongs_to_a_reclassification_only(
    client, admin_headers, carriers
):
    response = await move(
        client,
        admin_headers,
        "ECOM_TRANSFER",
        line(carriers.euro, 1, to=carriers.damaged),
    )

    assert response.status_code == 400
    assert response.json() == {"message": "Typ docelowy dotyczy tylko przeksięgowania"}


async def test_a_file_operation_is_not_entered_by_hand(client, admin_headers, carriers):
    response = await move(
        client, admin_headers, "STORE_SHIPMENT", line(carriers.euro, 1)
    )

    assert response.status_code == 400
    assert response.json() == {"message": "„Wysyłka do sklepów” księguje się z pliku"}


async def test_an_inventory_is_not_entered_as_a_movement(
    client, admin_headers, carriers
):
    response = await move(client, admin_headers, "INVENTORY", line(carriers.euro, 1))

    assert response.status_code == 400
    assert response.json() == {"message": "Inwentaryzację wprowadza się arkuszem spisu"}


async def test_an_unknown_operation_is_rejected(client, admin_headers, carriers):
    response = await move(client, admin_headers, "RECEIPT", line(carriers.euro, 1))

    assert response.status_code == 422
    assert response.json()["message"] == "Nieprawidłowe dane: type"


async def test_an_operation_date_in_the_past_is_fine(client, admin_headers, carriers):
    yesterday = warehouse_today() - timedelta(days=1)

    response = await move(
        client, admin_headers, "ECOM_TRANSFER", line(carriers.euro, 1), day=yesterday
    )

    assert response.json()["operation_date"] == yesterday.isoformat()


async def test_an_operation_date_in_the_future_is_rejected(
    client, admin_headers, carriers
):
    tomorrow = warehouse_today() + timedelta(days=1)

    response = await move(
        client, admin_headers, "ECOM_TRANSFER", line(carriers.euro, 1), day=tomorrow
    )

    assert response.status_code == 400
    assert response.json() == {"message": "Data operacji nie może być z przyszłości"}


# ---------- who may enter ----------


async def test_an_operator_enters_operations(client, session, carriers):
    await make_user(session, "jan", role="operator")
    headers = await login(client, "jan")

    response = await move(client, headers, "ECOM_TRANSFER", line(carriers.euro, 5))

    assert response.status_code == 200, response.text


async def test_a_viewer_cannot_enter_operations(client, session, carriers):
    await make_user(session, "jan", role="viewer")
    headers = await login(client, "jan")

    response = await move(client, headers, "ECOM_TRANSFER", line(carriers.euro, 5))

    assert response.status_code == 403
    assert response.json() == {"message": "Brak uprawnień"}


async def test_the_operations_say_who_may_enter_them(client, session, admin_headers):
    await make_user(session, "jan", role="viewer")
    viewer = await login(client, "jan")

    admin_view = (await client.get("/movements/types", headers=admin_headers)).json()
    viewer_view = (await client.get("/movements/types", headers=viewer)).json()

    assert [(t["code"], t["label"], t["sign"]) for t in admin_view] == [
        ("PRODUCER_RECEIPT", "Przyjęcie od producentów EURO", 1),
        ("PRODUCER_SHIPMENT", "Wysyłka do producentów EURO", -1),
        ("ECOM_TRANSFER", "Przesunięcie na ECOM", -1),
        ("OTHER_RECEIPT", "Inne — przyjęcie", 1),
        ("OTHER_SHIPMENT", "Inne — wydanie", -1),
        ("STORE_SHIPMENT", "Wysyłka do sklepów", -1),
        ("STORE_RETURN", "Zwroty ze sklepów", 1),
        ("UKR_SHIPMENT", "Wysyłka UKR", -1),
        ("UKR_RETURN", "Zwroty z UKR", 1),
        ("CORRECTION", "Korekta stanu", 0),
        ("RECLASSIFICATION", "Przeksięgowanie", 0),
        ("INVENTORY", "Inwentaryzacja", 0),
    ]
    # The inventory has its own screen; the file operations come from the file.
    assert [t["code"] for t in admin_view if not t["can_enter"]] == [
        "STORE_SHIPMENT",
        "STORE_RETURN",
        "UKR_SHIPMENT",
        "UKR_RETURN",
        "INVENTORY",
    ]
    assert not any(t["can_enter"] for t in viewer_view)
    receipt = admin_view[0]
    assert (receipt["counted_types_only"], receipt["note_required"]) == (True, False)


# ---------- reading ----------


async def test_the_list_is_newest_first_with_a_total(client, admin_headers, carriers):
    old = warehouse_today() - timedelta(days=3)
    for day, quantity in [(old, 1), (None, 2), (None, 3)]:
        await move(
            client,
            admin_headers,
            "OTHER_RECEIPT",
            line(carriers.euro, quantity),
            day=day,
        )

    response = await client.get("/movements?limit=2", headers=admin_headers)

    assert response.headers["X-Total-Count"] == "3"
    assert [m["lines"][0]["quantity"] for m in response.json()] == [3, 2]
    rest = await client.get("/movements?limit=2&offset=2", headers=admin_headers)
    assert [m["lines"][0]["quantity"] for m in rest.json()] == [1]


async def test_the_list_filters(client, admin_headers, carriers):
    old = warehouse_today() - timedelta(days=3)
    await move(client, admin_headers, "OTHER_RECEIPT", line(carriers.euro, 1), day=old)
    await move(client, admin_headers, "ECOM_TRANSFER", line(carriers.single, 2))

    by_type = await client.get("/movements?type=ECOM_TRANSFER", headers=admin_headers)
    by_carrier = await client.get(
        f"/movements?carrier_type_uuid={carriers.single}", headers=admin_headers
    )
    by_date = await client.get(
        f"/movements?date_to={old.isoformat()}", headers=admin_headers
    )

    assert [m["type"] for m in by_type.json()] == ["ECOM_TRANSFER"]
    assert [m["type"] for m in by_carrier.json()] == ["ECOM_TRANSFER"]
    assert [m["operation_date"] for m in by_date.json()] == [old.isoformat()]


async def test_everyone_signed_in_reads_the_register(
    client, session, admin_headers, carriers
):
    created = await move(client, admin_headers, "ECOM_TRANSFER", line(carriers.euro, 1))
    await make_user(session, "jan", role="viewer")
    headers = await login(client, "jan")

    listed = await client.get("/movements", headers=headers)
    one = await client.get(f"/movements/{created.json()['uuid']}", headers=headers)

    assert listed.headers["X-Total-Count"] == "1"
    assert one.json() == created.json()


async def test_a_missing_movement(client, admin_headers):
    response = await client.get(f"/movements/{uuid4()}", headers=admin_headers)

    assert response.status_code == 404
    assert response.json() == {"message": "Nie znaleziono ruchu"}


async def test_a_saved_movement_cannot_be_edited_or_deleted(
    client, admin_headers, carriers
):
    created = await move(client, admin_headers, "ECOM_TRANSFER", line(carriers.euro, 7))
    url = f"/movements/{created.json()['uuid']}"

    assert (await client.put(url, headers=admin_headers, json={})).status_code == 405
    assert (await client.delete(url, headers=admin_headers)).status_code == 405
