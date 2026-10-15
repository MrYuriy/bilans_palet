"""Closing warehouse days: the stored balance, the chain of days, closed means closed."""

import asyncio
from datetime import datetime, time, timedelta

import pytest
from sqlalchemy import func, select

from app.models.day_closure import DailyBalance, DayClosure
from app.services.day_close_service import DayCloseService, day_close_loop
from tests.conftest import TestSessionLocal, line, move, warehouse_today

TODAY = warehouse_today()
D1, D2, D3 = (TODAY - timedelta(days=n) for n in (3, 2, 1))


def after_cutoff(day):
    """A moment early in the warehouse day after ``day``."""
    return datetime.combine(day + timedelta(days=1), time(7, 0))


async def snapshot(session, day, carriers):
    names = {
        carriers.euro: "euro",
        carriers.damaged: "damaged",
        carriers.single: "single",
    }
    rows = (
        await session.execute(
            select(DailyBalance).where(DailyBalance.business_date == day)
        )
    ).scalars()
    return {
        names[str(r.carrier_type_uuid)]: (
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
async def history(client, admin_headers, carriers):
    """D1: a busy day of EURO; D2: nothing; D3: single-use pallets in."""
    for kind, ln in [
        ("PRODUCER_RECEIPT", line(carriers.euro, 100)),
        ("ECOM_TRANSFER", line(carriers.euro, 30)),
        ("CORRECTION", line(carriers.euro, 5)),
        ("RECLASSIFICATION", line(carriers.euro, 10, to=carriers.damaged)),
        ("OTHER_RECEIPT", line(carriers.euro, 20)),
    ]:
        response = await move(client, admin_headers, kind, ln, day=D1)
        assert response.status_code == 200, response.text
    response = await move(
        client, admin_headers, "OTHER_RECEIPT", line(carriers.single, 7), day=D3
    )
    assert response.status_code == 200, response.text


async def test_closing_stores_the_days_balance(session, carriers, history):
    closed = await DayCloseService(session).close_due_days()

    assert closed == [D1, D2, D3]
    # (opening, receipts, shipments, corrections, reclassifications, closing)
    assert await snapshot(session, D1, carriers) == {
        "euro": (0, 120, 30, 5, -10, 85),
        "damaged": (0, 0, 0, 0, 10, 10),
    }


async def test_each_day_opens_with_the_previous_closing(session, carriers, history):
    await DayCloseService(session).close_due_days()

    assert await snapshot(session, D2, carriers) == {
        "euro": (85, 0, 0, 0, 0, 85),
        "damaged": (10, 0, 0, 0, 0, 10),
    }
    assert await snapshot(session, D3, carriers) == {
        "euro": (85, 0, 0, 0, 0, 85),
        "damaged": (10, 0, 0, 0, 0, 10),
        "single": (0, 7, 0, 0, 0, 7),
    }


async def test_closing_again_changes_nothing(session, history):
    service = DayCloseService(session)
    await service.close_due_days()

    again = await service.close_due_days()

    rows = (
        await session.execute(select(func.count()).select_from(DayClosure))
    ).scalar()
    assert again == []
    assert rows == 3


async def test_a_closed_day_refuses_movements(
    client, session, admin_headers, carriers, history
):
    await DayCloseService(session).close_due_days()

    late = await move(
        client, admin_headers, "OTHER_RECEIPT", line(carriers.euro, 1), day=D3
    )
    today = await move(
        client, admin_headers, "OTHER_RECEIPT", line(carriers.euro, 1), day=TODAY
    )

    assert late.status_code == 400
    assert late.json() == {
        "message": f"Doba {D3.strftime('%d.%m.%Y')} jest już zamknięta"
    }
    assert today.status_code == 200


async def test_closed_days_keep_their_numbers(
    client, session, admin_headers, carriers, history
):
    await DayCloseService(session).close_due_days()
    before = await snapshot(session, D1, carriers)

    await move(client, admin_headers, "ECOM_TRANSFER", line(carriers.euro, 50))

    assert await snapshot(session, D1, carriers) == before


async def test_a_count_lands_on_the_open_day(
    client, session, admin_headers, carriers, history
):
    await DayCloseService(session).close_due_days()

    response = await client.post(
        "/inventories",
        headers=admin_headers,
        json={"lines": [{"carrier_type_uuid": carriers.euro, "counted_quantity": 80}]},
    )
    await DayCloseService(session).close_due_days(now=after_cutoff(TODAY))

    assert response.json()["operation_date"] == TODAY.isoformat()
    assert (await snapshot(session, TODAY, carriers))["euro"] == (85, 0, 0, -5, 0, 80)


async def test_without_any_movement_only_yesterday_closes(session):
    closed = await DayCloseService(session).close_due_days()

    assert closed == [TODAY - timedelta(days=1)]


async def test_catching_up_after_downtime(session, history):
    service = DayCloseService(session)
    await service.close_due_days()

    later = await service.close_due_days(now=after_cutoff(TODAY + timedelta(days=2)))

    assert later == [TODAY, TODAY + timedelta(days=1), TODAY + timedelta(days=2)]


async def test_the_current_day_is_never_a_closed_one(
    client, session, admin_headers, carriers, history
):
    # Close today early, as if the cut-off had been moved.
    await DayCloseService(session).close_due_days(now=after_cutoff(TODAY))

    settings = await client.get("/settings", headers=admin_headers)
    response = await move(
        client, admin_headers, "OTHER_RECEIPT", line(carriers.euro, 1)
    )

    tomorrow = (TODAY + timedelta(days=1)).isoformat()
    assert settings.json()["current_day"] == tomorrow
    assert response.json()["operation_date"] == tomorrow


async def test_the_background_task_closes_days(history):
    task = asyncio.create_task(day_close_loop(TestSessionLocal, interval_seconds=60))
    try:
        for _ in range(400):  # up to 20 s: a busy machine may be slow
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
