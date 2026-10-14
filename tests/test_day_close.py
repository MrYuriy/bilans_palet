"""Closing warehouse days: the stored balance, the chain of days, closed means closed."""

import asyncio
from datetime import datetime, time, timedelta

import pytest
from sqlalchemy import func, select

from app.models.area import Area
from app.models.day_closure import DailyBalance, DayClosure
from app.models.pallet_type import PalletType
from app.models.quality import Quality
from app.services.day_close_service import DayCloseService, day_close_loop
from tests.conftest import TestSessionLocal, warehouse_today

TODAY = warehouse_today()
D1, D2, D3 = (TODAY - timedelta(days=n) for n in (3, 2, 1))


def after_cutoff(day):
    """A moment early in the warehouse day after ``day``."""
    return datetime.combine(day + timedelta(days=1), time(7, 0))


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
    return response


async def snapshot(session, day, ids):
    rows = (
        await session.execute(
            select(DailyBalance).where(DailyBalance.business_date == day)
        )
    ).scalars()
    names = {v: k for k, v in ids.items()}
    return {
        (names[str(r.area_uuid)], names[str(r.quality_uuid)]): (
            r.opening,
            r.receipts,
            r.shipments,
            r.corrections,
            r.reclassifications,
            r.closing,
        )
        for r in rows
    }


@pytest.fixture
async def history(client, admin_headers, ids):
    """D1: busy day in area a; D2: nothing; D3: a receipt in area b."""
    for kind, quantity, extra in [
        ("RECEIPT", 100, {}),
        ("SHIPMENT", 30, {}),
        ("CORRECTION", 5, {}),
        ("RECLASSIFICATION", 10, {"to": "II"}),
        ("LM_PURCHASE", 20, {}),
    ]:
        response = await move(client, admin_headers, ids, kind, quantity, D1, **extra)
        assert response.status_code == 200, response.text
    response = await move(client, admin_headers, ids, "RECEIPT", 7, D3, area="b")
    assert response.status_code == 200, response.text


async def test_closing_stores_the_days_balance(session, ids, history):
    closed = await DayCloseService(session).close_due_days()

    assert closed == [D1, D2, D3]
    # (opening, receipts, shipments, corrections, reclassifications, closing)
    assert await snapshot(session, D1, ids) == {
        ("a", "I"): (0, 120, 30, 5, -10, 85),
        ("a", "II"): (0, 0, 0, 0, 10, 10),
    }


async def test_each_day_opens_with_the_previous_closing(session, ids, history):
    await DayCloseService(session).close_due_days()

    assert await snapshot(session, D2, ids) == {
        ("a", "I"): (85, 0, 0, 0, 0, 85),
        ("a", "II"): (10, 0, 0, 0, 0, 10),
    }
    assert await snapshot(session, D3, ids) == {
        ("a", "I"): (85, 0, 0, 0, 0, 85),
        ("a", "II"): (10, 0, 0, 0, 0, 10),
        ("b", "I"): (0, 7, 0, 0, 0, 7),
    }


async def test_closing_again_changes_nothing(session, ids, history):
    service = DayCloseService(session)
    await service.close_due_days()

    again = await service.close_due_days()

    rows = (
        await session.execute(select(func.count()).select_from(DayClosure))
    ).scalar()
    assert again == []
    assert rows == 3


async def test_a_closed_day_refuses_movements(
    client, session, admin_headers, ids, history
):
    await DayCloseService(session).close_due_days()

    late = await move(client, admin_headers, ids, "RECEIPT", 1, D3)
    today = await move(client, admin_headers, ids, "RECEIPT", 1, TODAY)

    assert late.status_code == 400
    assert late.json() == {
        "message": f"Doba {D3.strftime('%d.%m.%Y')} jest już zamknięta"
    }
    assert today.status_code == 200


async def test_closed_days_keep_their_numbers(
    client, session, admin_headers, ids, history
):
    await DayCloseService(session).close_due_days()
    before = await snapshot(session, D1, ids)

    await move(client, admin_headers, ids, "SHIPMENT", 50, TODAY)

    assert await snapshot(session, D1, ids) == before


async def test_a_count_lands_on_the_open_day(
    client, session, admin_headers, ids, history
):
    await DayCloseService(session).close_due_days()

    response = await client.post(
        "/inventories",
        headers=admin_headers,
        json={
            "area_uuid": ids["a"],
            "lines": [
                {
                    "pallet_type_uuid": ids["eur"],
                    "quality_uuid": ids["I"],
                    "counted_quantity": 80,
                }
            ],
        },
    )
    await DayCloseService(session).close_due_days(now=after_cutoff(TODAY))

    assert response.json()["operation_date"] == TODAY.isoformat()
    assert (await snapshot(session, TODAY, ids))["a", "I"] == (85, 0, 0, -5, 0, 80)


async def test_without_any_movement_only_yesterday_closes(session):
    closed = await DayCloseService(session).close_due_days()

    assert closed == [TODAY - timedelta(days=1)]


async def test_catching_up_after_downtime(session, ids, history):
    service = DayCloseService(session)
    await service.close_due_days()

    later = await service.close_due_days(now=after_cutoff(TODAY + timedelta(days=2)))

    assert later == [TODAY, TODAY + timedelta(days=1), TODAY + timedelta(days=2)]


async def test_the_current_day_is_never_a_closed_one(
    client, session, admin_headers, ids, history
):
    # Close today early, as if the cut-off had been moved.
    await DayCloseService(session).close_due_days(now=after_cutoff(TODAY))

    settings = await client.get("/settings", headers=admin_headers)
    response = await client.post(
        "/movements",
        headers=admin_headers,
        json={
            "type": "RECEIPT",
            "area_uuid": ids["a"],
            "lines": [
                {
                    "pallet_type_uuid": ids["eur"],
                    "quality_uuid": ids["I"],
                    "quantity": 1,
                }
            ],
        },
    )

    tomorrow = (TODAY + timedelta(days=1)).isoformat()
    assert settings.json()["current_day"] == tomorrow
    assert response.json()["operation_date"] == tomorrow


async def test_the_background_task_closes_days(ids, history):
    task = asyncio.create_task(day_close_loop(TestSessionLocal, interval_seconds=60))
    try:
        for _ in range(100):
            async with TestSessionLocal() as session:
                count = (
                    await session.execute(select(func.count()).select_from(DayClosure))
                ).scalar()
            if count == 3:
                break
            await asyncio.sleep(0.05)
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    assert count == 3
