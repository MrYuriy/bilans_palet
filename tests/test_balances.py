"""Balances: what is in stock now, and per warehouse day (closed or live)."""

from datetime import timedelta

import pytest

from app.services.day_close_service import DayCloseService
from tests.conftest import line, login, make_user, move, warehouse_today

TODAY = warehouse_today()
YESTERDAY = TODAY - timedelta(days=1)


@pytest.fixture
async def history(client, admin_headers, carriers):
    """Yesterday: 100 EURO in, 30 out to ECOM, 10 EURO -> uszkodzone, 8 single in,
    a correction of -2 EURO. Today: 5 more EURO in."""
    for kind, ln in [
        ("PRODUCER_RECEIPT", line(carriers.euro, 100)),
        ("ECOM_TRANSFER", line(carriers.euro, 30)),
        ("RECLASSIFICATION", line(carriers.euro, 10, to=carriers.damaged)),
        ("OTHER_RECEIPT", line(carriers.single, 8)),
        ("CORRECTION", line(carriers.euro, -2)),
    ]:
        response = await move(client, admin_headers, kind, ln, day=YESTERDAY)
        assert response.status_code == 200, response.text
    response = await move(
        client, admin_headers, "PRODUCER_RECEIPT", line(carriers.euro, 5), day=TODAY
    )
    assert response.status_code == 200, response.text


def stock(group):
    return [(r["carrier_type"]["name"], r["quantity"]) for r in group["rows"]]


def day_rows(group):
    return [
        (
            r["carrier_type"]["name"],
            r["opening"],
            r["receipts"],
            r["shipments"],
            r["corrections"],
            r["reclassifications"],
            r["closing"],
        )
        for r in group["rows"]
    ]


def totals(group):
    t = group["total"]
    return (
        t["opening"],
        t["receipts"],
        t["shipments"],
        t["corrections"],
        t["reclassifications"],
        t["closing"],
    )


# ---------- now ----------


async def test_current_stock_per_group_and_type(client, admin_headers, history):
    response = await client.get("/balances/current", headers=admin_headers)

    eur, single = response.json()["groups"]
    assert eur["group"]["name"] == "EUR"
    assert stock(eur) == [
        ("EURO", 63),
        ("EURO uszkodzone", 10),
        ("EURO utylizacja", 0),
    ]
    # Only the types counted in reports make the group's total.
    assert eur["total"] == 63
    assert (stock(single), single["total"]) == ([("Jednorazowe", 8)], 8)


async def test_the_report_flag_comes_with_each_type(client, admin_headers, history):
    response = await client.get("/balances/current", headers=admin_headers)

    eur = response.json()["groups"][0]
    assert [r["carrier_type"]["count_in_reports"] for r in eur["rows"]] == [
        True,
        False,
        False,
    ]


async def test_an_empty_stock_shows_zeros(client, admin_headers, carriers):
    response = await client.get("/balances/current", headers=admin_headers)

    assert [(stock(g), g["total"]) for g in response.json()["groups"]] == [
        ([("EURO", 0), ("EURO uszkodzone", 0), ("EURO utylizacja", 0)], 0),
        ([("Jednorazowe", 0)], 0),
    ]


async def test_an_inactive_type_shows_only_while_it_holds_stock(
    client, admin_headers, carriers, history
):
    for type_uuid in (carriers.damaged, carriers.scrap):
        await client.put(
            f"/carrier-types/{type_uuid}",
            headers=admin_headers,
            json={"is_active": False},
        )

    response = await client.get("/balances/current", headers=admin_headers)

    # uszkodzone still holds 10, utylizacja holds nothing.
    assert stock(response.json()["groups"][0]) == [
        ("EURO", 63),
        ("EURO uszkodzone", 10),
    ]


async def test_a_viewer_sees_the_stock(client, session, history):
    await make_user(session, "jan", role="viewer")
    headers = await login(client, "jan")

    response = await client.get("/balances/current", headers=headers)

    assert response.json()["groups"][0]["total"] == 63


# ---------- per day ----------


async def test_a_closed_day_shows_its_stored_balance(
    client, session, admin_headers, history
):
    await DayCloseService(session).close_due_days()

    response = await client.get(
        "/balances/daily", headers=admin_headers, params={"day": YESTERDAY.isoformat()}
    )

    body = response.json()
    assert (body["day"], body["closed"]) == (YESTERDAY.isoformat(), True)
    assert body["closed_at"] is not None
    eur, single = body["groups"]
    # (type, opening, receipts, shipments, corrections, reclassifications, closing)
    assert day_rows(eur) == [
        ("EURO", 0, 100, 30, -2, -10, 58),
        ("EURO uszkodzone", 0, 0, 0, 0, 10, 10),
        ("EURO utylizacja", 0, 0, 0, 0, 0, 0),
    ]
    assert totals(eur) == (0, 100, 30, -2, -10, 58)
    assert day_rows(single) == [("Jednorazowe", 0, 8, 0, 0, 0, 8)]


async def test_without_a_day_the_last_closed_one_is_shown(
    client, session, admin_headers, history
):
    await DayCloseService(session).close_due_days()

    response = await client.get("/balances/daily", headers=admin_headers)

    assert (response.json()["day"], response.json()["closed"]) == (
        YESTERDAY.isoformat(),
        True,
    )


async def test_the_open_day_is_a_live_preview(client, session, admin_headers, history):
    await DayCloseService(session).close_due_days()

    response = await client.get(
        "/balances/daily", headers=admin_headers, params={"day": TODAY.isoformat()}
    )

    body = response.json()
    assert (body["closed"], body["closed_at"]) == (False, None)
    assert day_rows(body["groups"][0])[:2] == [
        ("EURO", 58, 5, 0, 0, 0, 63),
        ("EURO uszkodzone", 10, 0, 0, 0, 0, 10),
    ]


async def test_closed_numbers_do_not_follow_later_movements(
    client, session, admin_headers, carriers, history
):
    await DayCloseService(session).close_due_days()
    await move(client, admin_headers, "ECOM_TRANSFER", line(carriers.euro, 20))

    response = await client.get(
        "/balances/daily", headers=admin_headers, params={"day": YESTERDAY.isoformat()}
    )

    assert totals(response.json()["groups"][0]) == (0, 100, 30, -2, -10, 58)


async def test_without_any_closed_day_today_is_shown(client, admin_headers, history):
    response = await client.get("/balances/daily", headers=admin_headers)

    assert (response.json()["day"], response.json()["closed"]) == (
        TODAY.isoformat(),
        False,
    )


async def test_a_future_day_is_refused(client, admin_headers, carriers):
    response = await client.get(
        "/balances/daily",
        headers=admin_headers,
        params={"day": (TODAY + timedelta(days=1)).isoformat()},
    )

    assert response.status_code == 400
    assert response.json() == {"message": "Ta doba jeszcze się nie zaczęła"}
