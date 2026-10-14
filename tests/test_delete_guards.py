"""What movements already use is deactivated, never deleted."""

from tests.conftest import line, login, make_user, move

IN_USE = "Typ nośnika występuje w ruchach. Możesz go dezaktywować."


async def receive(client, headers, carrier_type):
    response = await move(client, headers, "OTHER_RECEIPT", line(carrier_type, 10))
    assert response.status_code == 200, response.text


async def test_a_used_carrier_type_is_not_deleted(client, admin_headers, carriers):
    await receive(client, admin_headers, carriers.euro)
    url = f"/carrier-types/{carriers.euro}"

    deleted = await client.delete(url, headers=admin_headers)
    still_there = await client.get(url, headers=admin_headers)
    deactivated = await client.put(
        url, headers=admin_headers, json={"is_active": False}
    )

    assert deleted.status_code == 409
    assert deleted.json() == {"message": IN_USE}
    assert still_there.status_code == 200
    assert deactivated.json()["is_active"] is False


async def test_an_unused_type_next_to_used_ones_can_be_deleted(
    client, admin_headers, carriers
):
    await receive(client, admin_headers, carriers.euro)

    response = await client.delete(
        f"/carrier-types/{carriers.scrap}", headers=admin_headers
    )

    assert response.status_code == 200


async def test_a_type_used_only_as_a_reclassification_target(
    client, admin_headers, carriers
):
    await move(
        client,
        admin_headers,
        "RECLASSIFICATION",
        line(carriers.euro, 3, to=carriers.damaged),
    )

    response = await client.delete(
        f"/carrier-types/{carriers.damaged}", headers=admin_headers
    )

    assert response.status_code == 409


async def test_a_type_used_only_in_a_matching_count(client, admin_headers, carriers):
    # The count matched, so no movement line: only the count sheet uses the type.
    await client.post(
        "/inventories",
        headers=admin_headers,
        json={"lines": [{"carrier_type_uuid": carriers.scrap, "counted_quantity": 0}]},
    )

    response = await client.delete(
        f"/carrier-types/{carriers.scrap}", headers=admin_headers
    )

    assert response.status_code == 409


async def test_a_user_with_movements_is_not_deleted(
    client, session, admin_headers, carriers
):
    user = await make_user(session, "jan", role="admin")
    await receive(client, await login(client, "jan"), carriers.euro)

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
    client, session, admin_headers, carriers
):
    user = await make_user(session, "jan", role="admin")
    await receive(client, await login(client, "jan"), carriers.euro)
    await client.put(
        f"/users/{user.uuid}", headers=admin_headers, json={"is_active": False}
    )

    listed = await client.get("/movements", headers=admin_headers)

    assert [m["user"]["username"] for m in listed.json()] == ["jan"]
