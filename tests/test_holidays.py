"""Days off: the Polish public holidays and the ones the admin adds."""

from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.models.holiday import Holiday
from app.services.holiday_service import (
    HolidayService,
    easter_sunday,
    polish_public_holidays,
)
from scripts.seed_data import seed_holidays
from tests.conftest import login, make_user


@pytest.mark.parametrize(
    ("year", "easter"),
    [
        (2024, date(2024, 3, 31)),
        (2025, date(2025, 4, 20)),
        (2026, date(2026, 4, 5)),
        (2027, date(2027, 3, 28)),
    ],
)
def test_easter(year, easter):
    assert easter_sunday(year) == easter


def test_the_public_holidays_of_2026():
    days = dict(polish_public_holidays(2026))

    assert len(days) == 14
    assert days[date(2026, 4, 6)] == "Poniedziałek Wielkanocny"
    assert days[date(2026, 5, 24)] == "Zielone Świątki"
    assert days[date(2026, 6, 4)] == "Boże Ciało"
    assert days[date(2026, 12, 24)] == "Wigilia Bożego Narodzenia"


def test_christmas_eve_is_a_day_off_since_2025():
    assert date(2024, 12, 24) not in dict(polish_public_holidays(2024))
    assert date(2025, 12, 24) in dict(polish_public_holidays(2025))


async def test_the_admin_adds_a_years_public_holidays_once(client, admin_headers):
    first = await client.post("/holidays/public/2026", headers=admin_headers)
    again = await client.post("/holidays/public/2026", headers=admin_headers)
    listed = await client.get("/holidays/2026", headers=admin_headers)

    assert first.status_code == 200, first.text
    assert len(first.json()) == 14
    assert again.json() == []
    assert [h["day"] for h in listed.json()][:2] == ["2026-01-01", "2026-01-06"]


async def test_the_admin_adds_and_removes_a_day(client, admin_headers):
    added = await client.post(
        "/holidays",
        headers=admin_headers,
        json={"day": "2026-12-31", "name": " Inwentaryzacja roczna "},
    )
    duplicate = await client.post(
        "/holidays", headers=admin_headers, json={"day": "2026-12-31"}
    )
    removed = await client.delete(
        f"/holidays/{added.json()['uuid']}", headers=admin_headers
    )
    listed = await client.get("/holidays/2026", headers=admin_headers)

    assert added.json()["name"] == "Inwentaryzacja roczna"
    assert duplicate.status_code == 409
    assert duplicate.json() == {"message": "Dzień 31.12.2026 jest już na liście"}
    assert removed.status_code == 200
    assert listed.json() == []


async def test_a_day_without_a_name(client, admin_headers):
    response = await client.post(
        "/holidays", headers=admin_headers, json={"day": "2026-08-14"}
    )

    assert response.json()["name"] == "Dzień wolny"


async def test_removing_a_missing_day(client, admin_headers):
    response = await client.delete(f"/holidays/{uuid4()}", headers=admin_headers)

    assert response.status_code == 404


async def test_changes_are_logged(client, admin_headers):
    await client.post(
        "/holidays", headers=admin_headers, json={"day": "2026-12-31", "name": "X"}
    )

    [entry] = (
        await client.get("/audit", headers=admin_headers, params={"entity": "holiday"})
    ).json()
    assert entry["entity_label"] == "Dzień wolny"
    assert entry["new_data"] == {"day": "2026-12-31", "name": "X"}


@pytest.mark.parametrize("role", ["manager", "operator", "viewer"])
async def test_others_read_but_do_not_change(client, session, role):
    await make_user(session, "jan", role=role)
    headers = await login(client, "jan")

    listed = await client.get("/holidays/2026", headers=headers)
    added = await client.post("/holidays", headers=headers, json={"day": "2026-12-31"})
    public = await client.post("/holidays/public/2026", headers=headers)

    assert listed.status_code == 200
    assert added.status_code == public.status_code == 403


async def test_working_days(session):
    service = HolidayService(session)
    await service.add_public(None, 2026)

    assert await service.is_working_day(date(2026, 10, 14)) is True  # Wednesday
    assert await service.is_working_day(date(2026, 10, 17)) is False  # Saturday
    assert await service.is_working_day(date(2026, 11, 11)) is False  # holiday


async def test_the_seed_fills_an_empty_list_only(session):
    years = await seed_holidays(session)
    await session.commit()
    first = (await session.execute(select(Holiday))).scalars().all()
    await session.delete(first[0])
    await session.commit()

    again = await seed_holidays(session)

    assert len(years) == 2
    assert len(first) >= 27
    assert again == []
    remaining = (await session.execute(select(Holiday))).scalars().all()
    assert len(remaining) == len(first) - 1
