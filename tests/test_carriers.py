"""Carrier groups and types: what goes beyond the shared dictionary behaviour."""

import pytest

from tests.conftest import login, make_user


async def group(client, headers, name="EUR", **fields):
    response = await client.post(
        "/carrier-groups", headers=headers, json={"name": name, **fields}
    )
    assert response.status_code == 200, response.text
    return response.json()


async def carrier_type(client, headers, group_uuid, name="EURO", **fields):
    return await client.post(
        "/carrier-types",
        headers=headers,
        json={"group_uuid": group_uuid, "name": name, **fields},
    )


async def test_a_type_shows_its_group_and_report_flag(client, admin_headers):
    eur = await group(client, admin_headers)

    response = await carrier_type(
        client, admin_headers, eur["uuid"], "EURO uszkodzone", count_in_reports=False
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["group"] == {"uuid": eur["uuid"], "name": "EUR"}
    assert (body["count_in_reports"], body["sort_order"]) == (False, 0)


async def test_counted_in_reports_by_default(client, admin_headers):
    eur = await group(client, admin_headers)

    body = (await carrier_type(client, admin_headers, eur["uuid"])).json()

    assert body["count_in_reports"] is True


async def test_types_are_listed_by_group_then_order(client, admin_headers):
    single = await group(client, admin_headers, "Jednorazowe")
    eur = await group(client, admin_headers, "EUR")
    await carrier_type(client, admin_headers, single["uuid"], "Jednorazowe")
    await carrier_type(
        client, admin_headers, eur["uuid"], "EURO utylizacja", sort_order=3
    )
    await carrier_type(client, admin_headers, eur["uuid"], "EURO", sort_order=1)
    await carrier_type(
        client, admin_headers, eur["uuid"], "EURO uszkodzone", sort_order=2
    )

    listed = (await client.get("/carrier-types", headers=admin_headers)).json()

    assert [t["name"] for t in listed] == [
        "EURO",
        "EURO uszkodzone",
        "EURO utylizacja",
        "Jednorazowe",
    ]


async def test_a_type_needs_a_known_group(client, admin_headers):
    missing = await client.post(
        "/carrier-types", headers=admin_headers, json={"name": "EURO"}
    )
    unknown = await carrier_type(
        client, admin_headers, "0f5e8a52-9a34-4c1b-b8d2-7a3c1e2d4f6a"
    )

    assert missing.status_code == 422
    assert unknown.status_code == 400
    assert unknown.json() == {"message": "Nieznana grupa nośników"}


async def test_no_new_type_in_an_inactive_group(client, admin_headers):
    eur = await group(client, admin_headers)
    await client.put(
        f"/carrier-groups/{eur['uuid']}",
        headers=admin_headers,
        json={"is_active": False},
    )

    response = await carrier_type(client, admin_headers, eur["uuid"])

    assert response.status_code == 400
    assert response.json() == {"message": "Grupa „EUR” jest nieaktywna"}


async def test_a_type_moves_to_another_group(client, admin_headers):
    eur = await group(client, admin_headers)
    single = await group(client, admin_headers, "Jednorazowe")
    created = (await carrier_type(client, admin_headers, eur["uuid"], "Mix")).json()

    response = await client.put(
        f"/carrier-types/{created['uuid']}",
        headers=admin_headers,
        json={"group_uuid": single["uuid"], "count_in_reports": False},
    )

    assert response.status_code == 200, response.text
    assert response.json()["group"]["name"] == "Jednorazowe"
    assert response.json()["count_in_reports"] is False


async def test_a_group_with_types_is_not_deleted(client, admin_headers):
    eur = await group(client, admin_headers)
    await carrier_type(client, admin_headers, eur["uuid"])

    response = await client.delete(
        f"/carrier-groups/{eur['uuid']}", headers=admin_headers
    )

    assert response.status_code == 409
    assert response.json() == {
        "message": "Grupa ma typy nośników. Możesz ją dezaktywować."
    }


async def test_the_audit_names_the_group(client, admin_headers):
    eur = await group(client, admin_headers)
    created = (await carrier_type(client, admin_headers, eur["uuid"])).json()
    await client.put(
        f"/carrier-types/{created['uuid']}",
        headers=admin_headers,
        json={"count_in_reports": False},
    )

    entries = (
        await client.get(
            "/audit", headers=admin_headers, params={"entity": "carrier_type"}
        )
    ).json()

    update, create = entries
    assert create["entity_label"] == "Typ nośnika"
    assert create["new_data"]["group"] == "EUR"
    assert (update["old_data"], update["new_data"]) == (
        {"count_in_reports": True},
        {"count_in_reports": False},
    )


@pytest.mark.parametrize("role", ["operator", "viewer"])
async def test_only_the_admin_adds_types(client, session, admin_headers, role):
    eur = await group(client, admin_headers)
    await make_user(session, "jan", role=role)
    headers = await login(client, "jan")

    response = await carrier_type(client, headers, eur["uuid"])

    assert response.status_code == 403
