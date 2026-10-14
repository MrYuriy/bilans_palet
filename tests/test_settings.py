# ruff: noqa: DTZ001 - warehouse times are naive local wall-clock times by design
"""The day cut-off and the warehouse day it defines."""

from datetime import date, datetime, time

import pytest

from app.core.timeutils import business_date
from tests.conftest import login, make_user, warehouse_today


@pytest.mark.parametrize(
    ("moment", "cutoff", "day"),
    [
        (datetime(2026, 10, 4, 3, 0), time(6, 0), date(2026, 10, 3)),
        (datetime(2026, 10, 4, 5, 59), time(6, 0), date(2026, 10, 3)),
        (datetime(2026, 10, 4, 6, 0), time(6, 0), date(2026, 10, 4)),
        (datetime(2026, 10, 4, 23, 59), time(6, 0), date(2026, 10, 4)),
        (datetime(2026, 10, 4, 0, 0), time(0, 0), date(2026, 10, 4)),
        (datetime(2026, 10, 4, 7, 15), time(7, 30), date(2026, 10, 3)),
        (datetime(2026, 1, 1, 2, 0), time(6, 0), date(2025, 12, 31)),
    ],
)
def test_business_date(moment, cutoff, day):
    assert business_date(moment, cutoff) == day


async def test_default_cutoff_is_midnight(client, admin_headers):
    response = await client.get("/settings", headers=admin_headers)

    assert response.status_code == 200
    assert response.json() == {
        "day_cutoff": "00:00",
        "current_day": warehouse_today().isoformat(),
        "last_closed_day": None,
    }


async def test_admin_changes_the_cutoff(client, admin_headers):
    response = await client.put(
        "/settings", headers=admin_headers, json={"day_cutoff": "07:30"}
    )
    again = await client.get("/settings", headers=admin_headers)

    assert response.status_code == 200, response.text
    assert response.json()["day_cutoff"] == "07:30"
    assert again.json()["day_cutoff"] == "07:30"


async def test_changing_the_cutoff_is_logged(client, admin_headers):
    await client.put("/settings", headers=admin_headers, json={"day_cutoff": "05:00"})

    [entry] = (await client.get("/audit", headers=admin_headers)).json()

    assert (entry["entity"], entry["entity_label"]) == ("settings", "Ustawienia")
    assert entry["old_data"] == {"day_cutoff": "00:00"}
    assert entry["new_data"] == {"day_cutoff": "05:00"}


async def test_saving_the_same_cutoff_is_not_logged(client, admin_headers):
    await client.put("/settings", headers=admin_headers, json={"day_cutoff": "00:00"})

    assert (await client.get("/audit", headers=admin_headers)).json() == []


async def test_an_invalid_hour_is_rejected(client, admin_headers):
    response = await client.put(
        "/settings", headers=admin_headers, json={"day_cutoff": "25:00"}
    )

    assert response.status_code == 422
    assert response.json()["message"] == "Nieprawidłowe dane: day_cutoff"


@pytest.mark.parametrize("role", ["operator", "viewer"])
async def test_others_read_but_do_not_change(client, session, role):
    await make_user(session, "jan", role=role)
    headers = await login(client, "jan")

    read = await client.get("/settings", headers=headers)
    change = await client.put(
        "/settings", headers=headers, json={"day_cutoff": "07:00"}
    )

    assert read.status_code == 200
    assert change.status_code == 403
