"""Deliveries from Saldo Palet: the manager's rule, one entry a day, the
morning import and its catch-up."""

from datetime import datetime, time, timedelta

import pytest
from sqlalchemy import select

from app.core.timeutils import local_now
from app.dependencies import get_saldo_palet_client
from app.main import app
from app.models.role import Role
from app.models.user import User
from app.services.saldo_palet_client import SaldoPaletUnavailable, SaldoTransaction
from app.services.saldo_palet_import_service import SaldoPaletImportService, effect
from scripts.seed_data import seed_system_user
from tests.conftest import TestSessionLocal, login, make_user, stock_of

TODAY = local_now().date()
YESTERDAY = TODAY - timedelta(days=1)


class FakeSaldo:
    """Saldo Palet as the tests set it: day -> transactions."""

    def __init__(self, days=None, fail=False):
        self.days = days or {}
        self.fail = fail
        self.asked: list = []

    async def transactions_added_on(self, day):
        self.asked.append(day)
        if self.fail:
            raise SaldoPaletUnavailable("Brak połączenia z Saldem Palet (ConnectError)")
        return self.days.get(day, [])


def tx(kind, quantity, unit="EUR"):
    return SaldoTransaction(type=kind, quantity=quantity, unit=unit)


@pytest.fixture
def saldo():
    fake = FakeSaldo()
    app.dependency_overrides[get_saldo_palet_client] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_saldo_palet_client, None)


async def run(client, headers, day=None):
    params = {"day": day.isoformat()} if day else {}
    return await client.post("/imports/saldo-palet", headers=headers, params=params)


@pytest.mark.parametrize(
    ("kind", "quantity", "change"),
    [
        ("RECEIPT", 10, 10),
        ("ISSUE", 3, -3),
        ("CORRECTION", 5, -5),
        ("CORRECTION", -4, 4),
    ],
)
def test_the_managers_rule(kind, quantity, change):
    assert effect(kind, quantity) == change


async def test_yesterday_is_booked_today_as_one_entry(
    client, admin_headers, carriers, saldo
):
    saldo.days[YESTERDAY] = [
        tx("RECEIPT", 1143),
        tx("ISSUE", 215),
        tx("CORRECTION", 33),
        tx("RECEIPT", 4, "euro uszkodzone"),
        tx("RECEIPT", 76, "Stojak"),
        tx("ISSUE", 260, "palety LM"),
    ]

    response = await run(client, admin_headers)

    assert response.status_code == 200, response.text
    summary = response.json()["summary"]
    assert summary["day"] == YESTERDAY.isoformat()
    assert summary["types"]["EURO"] == {
        "in": 1143,
        "out": 215,
        "corrections": 33,
        "net": 895,
        "change": 895,
    }
    # Units without a carrier type do not count.
    assert summary["ignored"] == {"Stojak": 1, "palety LM": 1}
    [movement] = (await client.get("/movements", headers=admin_headers)).json()
    assert (movement["type_label"], movement["operation_date"]) == (
        "Przyjęcia (Saldo Palet)",
        TODAY.isoformat(),
    )
    assert sorted(
        (ln["carrier_type"]["name"], ln["quantity"]) for ln in movement["lines"]
    ) == [("EURO", 895), ("EURO uszkodzone", 4)]
    assert movement["comment"].startswith(
        f"Saldo Palet {YESTERDAY:%d.%m.%Y} — EURO IN 1143"
    )
    assert (await stock_of(client, admin_headers))["EURO"] == 895


async def test_units_match_without_regard_to_case(
    client, admin_headers, carriers, saldo
):
    saldo.days[YESTERDAY] = [
        tx("RECEIPT", 7, " eur "),
        tx("RECEIPT", 2, "Euro Uszkodzone"),
    ]

    body = (await run(client, admin_headers)).json()

    assert body["summary"]["types"]["EURO"]["net"] == 7
    assert body["summary"]["types"]["EURO uszkodzone"]["net"] == 2


async def test_a_day_without_transactions_is_still_recorded(
    client, admin_headers, carriers, saldo
):
    response = await run(client, admin_headers)
    listed = (await client.get("/imports/saldo-palet", headers=admin_headers)).json()

    assert response.status_code == 200
    assert response.json()["summary"]["transactions"] == 0
    assert (await client.get("/movements", headers=admin_headers)).json() == []
    assert [i["summary"]["day"] for i in listed] == [YESTERDAY.isoformat()]


async def test_the_same_day_again_books_only_what_changed(
    client, admin_headers, carriers, saldo
):
    saldo.days[YESTERDAY] = [tx("RECEIPT", 100)]
    await run(client, admin_headers)

    again = await run(client, admin_headers)
    saldo.days[YESTERDAY].append(tx("ISSUE", 30))
    later = await run(client, admin_headers)

    assert again.json()["summary"]["types"]["EURO"]["change"] == 0
    assert later.json()["summary"]["types"]["EURO"]["change"] == -30
    assert (await stock_of(client, admin_headers))["EURO"] == 70


async def test_only_a_day_that_is_over(client, admin_headers, carriers, saldo):
    response = await run(client, admin_headers, TODAY)

    assert response.status_code == 400
    assert response.json() == {"message": "Można pobrać tylko zakończony dzień"}
    assert saldo.asked == []


async def test_saldo_palet_down(client, admin_headers, carriers, saldo):
    saldo.fail = True

    response = await run(client, admin_headers)

    assert response.status_code == 400
    assert response.json() == {
        "message": "Brak połączenia z Saldem Palet (ConnectError)"
    }


async def test_not_configured(client, admin_headers, carriers):
    response = await run(client, admin_headers)

    assert response.status_code == 400
    assert response.json() == {
        "message": "Połączenie z Saldem Palet nie jest skonfigurowane"
    }


@pytest.mark.parametrize(("role", "allowed"), [("operator", True), ("viewer", False)])
async def test_who_may_import_by_hand(client, session, carriers, saldo, role, allowed):
    await make_user(session, "jan", role=role)
    headers = await login(client, "jan")

    response = await run(client, headers)

    assert response.status_code == (200 if allowed else 403)


# ---------- the morning import ----------


async def test_due_days(session, carriers):
    service = SaldoPaletImportService(session, FakeSaldo())
    now = datetime.combine(TODAY, time(5, 30))

    first = await service.due_days(now)
    author = await make_user(session, "system", role="viewer", is_active=False)
    for day in first:
        await service.import_day(author, day)
    await session.commit()
    # Three days later, with the app down in between: the missed days catch up.
    later = await service.due_days(now + timedelta(days=3))

    assert first == [YESTERDAY]
    assert later == [TODAY, TODAY + timedelta(days=1), TODAY + timedelta(days=2)]


async def test_catching_up_stops_a_week_back(session, carriers):
    service = SaldoPaletImportService(session, FakeSaldo())
    author = await make_user(session, "system", role="viewer", is_active=False)
    await service.import_day(author, YESTERDAY)
    await session.commit()

    days = await service.due_days(datetime.combine(TODAY + timedelta(days=30), time(6)))

    assert len(days) == 7
    assert days[-1] == TODAY + timedelta(days=29)


async def test_the_system_user_cannot_sign_in(client, session):
    async with TestSessionLocal() as other:
        role = Role(name="viewer")
        other.add(role)
        await other.flush()
        created = await seed_system_user(other, role)
        again = await seed_system_user(other, role)
        await other.commit()

    user = (
        await session.execute(select(User).where(User.username == "system"))
    ).scalar_one()
    assert (created, again) == (True, False)
    assert user.is_active is False
