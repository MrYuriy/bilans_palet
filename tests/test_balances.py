"""Balances: what is in stock now, and per warehouse day (closed or live)."""

from datetime import timedelta
from uuid import UUID

import pytest
from sqlalchemy import insert

from app.models.area import Area
from app.models.pallet_type import PalletType
from app.models.quality import Quality
from app.models.user_area import user_areas
from app.services.day_close_service import DayCloseService
from tests.conftest import login, make_user, warehouse_today

TODAY = warehouse_today()
YESTERDAY = TODAY - timedelta(days=1)


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


async def move(client, headers, ids, kind, quantity, day, area="a", q="I", to=None):
    line = {
        "pallet_type_uuid": ids["eur"],
        "quality_uuid": ids[q],
        "quantity": quantity,
    }
    if to:
        line["to_quality_uuid"] = ids[to]
    response = await client.post(
        "/movements",
        headers=headers,
        json={
            "type": kind,
            "area_uuid": ids[area],
            "operation_date": day.isoformat(),
            "comment": "test",
            "lines": [line],
        },
    )
    assert response.status_code == 200, response.text


@pytest.fixture
async def history(client, admin_headers, ids):
    """Yesterday: 100 I in, 30 out, 10 I->II in area a; 7 I in area b.
    Today: 5 more I into area a."""
    await move(client, admin_headers, ids, "RECEIPT", 100, YESTERDAY)
    await move(client, admin_headers, ids, "SHIPMENT", 30, YESTERDAY)
    await move(client, admin_headers, ids, "RECLASSIFICATION", 10, YESTERDAY, to="II")
    await move(client, admin_headers, ids, "RECEIPT", 7, YESTERDAY, area="b")
    await move(client, admin_headers, ids, "RECEIPT", 5, TODAY)


def stock(rows):
    return [(r["quality"]["name"], r["quantity"]) for r in rows]


def day_rows(rows):
    return [
        (
            r["quality"]["name"],
            r["opening"],
            r["receipts"],
            r["shipments"],
            r["corrections"],
            r["reclassifications"],
            r["closing"],
        )
        for r in rows
    ]


async def operator(client, session, *area_uuids, role="operator"):
    user = await make_user(session, "jan", role=role)
    if area_uuids:
        await session.execute(
            insert(user_areas),
            [{"user_uuid": user.uuid, "area_uuid": UUID(a)} for a in area_uuids],
        )
        await session.commit()
    return await login(client, "jan")


# ---------- now ----------


async def test_current_stock_per_area_and_in_total(client, admin_headers, history):
    response = await client.get("/balances/current", headers=admin_headers)

    body = response.json()
    assert [a["area"]["name"] for a in body["areas"]] == [
        "Przyjęcia 445",
        "Wysyłka 445",
    ]
    assert stock(body["areas"][0]["rows"]) == [("I", 65), ("II", 10)]
    assert stock(body["areas"][1]["rows"]) == [("I", 7), ("II", 0)]
    assert stock(body["total"]) == [("I", 72), ("II", 10)]


async def test_current_stock_shows_empty_areas_with_zeros(client, admin_headers, ids):
    response = await client.get("/balances/current", headers=admin_headers)

    body = response.json()
    assert [stock(a["rows"]) for a in body["areas"]] == [[("I", 0), ("II", 0)]] * 2
    assert stock(body["total"]) == [("I", 0), ("II", 0)]


async def test_an_inactive_quality_with_stock_is_still_shown(
    client, admin_headers, ids, history
):
    await client.put(
        f"/qualities/{ids['II']}", headers=admin_headers, json={"is_active": False}
    )

    response = await client.get(
        "/balances/current", headers=admin_headers, params={"area_uuid": ids["b"]}
    )

    # Area b has no II, so the inactive II disappears there; area a keeps it.
    assert stock(response.json()["areas"][0]["rows"]) == [("I", 7)]
    whole = await client.get("/balances/current", headers=admin_headers)
    assert stock(whole.json()["areas"][0]["rows"]) == [("I", 65), ("II", 10)]


async def test_operator_sees_only_their_areas(client, session, ids, history):
    headers = await operator(client, session, ids["b"])

    mine = await client.get("/balances/current", headers=headers)
    foreign = await client.get(
        "/balances/current", headers=headers, params={"area_uuid": ids["a"]}
    )

    assert [a["area"]["name"] for a in mine.json()["areas"]] == ["Wysyłka 445"]
    assert stock(mine.json()["total"]) == [("I", 7), ("II", 0)]
    assert foreign.status_code == 403


async def test_viewer_sees_everything(client, session, ids, history):
    headers = await operator(client, session, role="viewer")

    response = await client.get("/balances/current", headers=headers)

    assert stock(response.json()["total"]) == [("I", 72), ("II", 10)]


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
    # (quality, opening, receipts, shipments, corrections, reclassifications, closing)
    assert day_rows(body["areas"][0]["rows"]) == [
        ("I", 0, 100, 30, 0, -10, 60),
        ("II", 0, 0, 0, 0, 10, 10),
    ]
    assert day_rows(body["areas"][1]["rows"]) == [("I", 0, 7, 0, 0, 0, 7)]
    assert day_rows(body["total"]) == [
        ("I", 0, 107, 30, 0, -10, 67),
        ("II", 0, 0, 0, 0, 10, 10),
    ]


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
    assert day_rows(body["areas"][0]["rows"]) == [
        ("I", 60, 5, 0, 0, 0, 65),
        ("II", 10, 0, 0, 0, 0, 10),
    ]


async def test_closed_numbers_do_not_follow_later_movements(
    client, session, admin_headers, ids, history
):
    await DayCloseService(session).close_due_days()
    await move(client, admin_headers, ids, "SHIPMENT", 20, TODAY)

    response = await client.get(
        "/balances/daily", headers=admin_headers, params={"day": YESTERDAY.isoformat()}
    )

    assert day_rows(response.json()["total"])[0] == ("I", 0, 107, 30, 0, -10, 67)


async def test_without_any_closed_day_today_is_shown(client, admin_headers, history):
    response = await client.get("/balances/daily", headers=admin_headers)

    assert (response.json()["day"], response.json()["closed"]) == (
        TODAY.isoformat(),
        False,
    )


async def test_a_future_day_is_refused(client, admin_headers, ids):
    response = await client.get(
        "/balances/daily",
        headers=admin_headers,
        params={"day": (TODAY + timedelta(days=1)).isoformat()},
    )

    assert response.status_code == 400
    assert response.json() == {"message": "Ta doba jeszcze się nie zaczęła"}


async def test_operator_daily_balance_is_limited_to_their_areas(
    client, session, ids, history
):
    headers = await operator(client, session, ids["b"])

    response = await client.get(
        "/balances/daily", headers=headers, params={"day": YESTERDAY.isoformat()}
    )

    body = response.json()
    assert [a["area"]["name"] for a in body["areas"]] == ["Wysyłka 445"]
    assert day_rows(body["total"]) == [("I", 0, 7, 0, 0, 0, 7)]
