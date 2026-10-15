"""Reminders: the admin's list, and the mail that goes out when a job is not
done by its time on a working day."""

from datetime import date, datetime, time

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.models.data_import import DataImport
from app.models.reminder import Reminder
from app.models.user import User
from app.services import mailer as mailer_module
from app.services.holiday_service import HolidayService
from app.services.mailer import Mailer
from app.services.reminder_service import reminder_mail, run_reminders
from tests.conftest import line, login, make_user, move

WEDNESDAY = date(2026, 10, 14)
SATURDAY = date(2026, 10, 17)


class FakeMailer:
    sender = "monolit@example.com"

    def __init__(self):
        self.sent: list[tuple[list[str], str, str]] = []

    async def send(self, recipients, subject, body):
        self.sent.append((recipients, subject, body))


def at(day: date, hh: int, mm: int = 0) -> datetime:
    return datetime.combine(day, time(hh, mm))


async def reminder(session, **fields) -> Reminder:
    row = Reminder(
        **{
            "name": "Wysyłka i zwroty z Transplanera",
            "check": "transplaner",
            "deadline": time(12, 30),
            "recipients": ["kierownik@example.com"],
            **fields,
        }
    )
    session.add(row)
    await session.commit()
    return row


# ---------- the admin's list ----------


async def test_the_admin_adds_a_reminder(client, admin_headers):
    response = await client.post(
        "/reminders",
        headers=admin_headers,
        json={
            "name": "Przyjęcia z Salda Palet",
            "check": "saldo_palet",
            "deadline": "08:00",
            "recipients": [" a@example.com", "", "A@example.com", "b@example.com"],
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["description"] == "Import z Salda Palet"
    assert body["deadline"] == "08:00"
    assert body["recipients"] == ["a@example.com", "b@example.com"]
    assert body["is_active"] is True


async def test_a_reminder_on_an_operation(client, admin_headers):
    response = await client.post(
        "/reminders",
        headers=admin_headers,
        json={
            "name": "Przesunięcie na ECOM",
            "check": "movement",
            "movement_type": "ECOM_TRANSFER",
            "deadline": "15:00",
        },
    )

    assert response.json()["description"] == "Operacja: Przesunięcie na ECOM"


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({"check": "nothing"}, "Wybierz, co ma być sprawdzane"),
        ({"check": "movement"}, "Wybierz operację do sprawdzania"),
        ({"recipients": ["nie-adres"]}, "Nieprawidłowy adres e-mail: nie-adres"),
    ],
)
async def test_invalid_reminders(client, admin_headers, payload, message):
    response = await client.post(
        "/reminders",
        headers=admin_headers,
        json={"name": "X", "check": "transplaner", "deadline": "12:30", **payload},
    )

    assert response.status_code == 400
    assert response.json() == {"message": message}


async def test_changes_are_logged(client, admin_headers):
    created = (
        await client.post(
            "/reminders",
            headers=admin_headers,
            json={"name": "X", "check": "transplaner", "deadline": "12:30"},
        )
    ).json()
    await client.put(
        f"/reminders/{created['uuid']}",
        headers=admin_headers,
        json={"deadline": "13:00", "recipients": ["a@example.com"]},
    )

    update, create = (
        await client.get("/audit", headers=admin_headers, params={"entity": "reminder"})
    ).json()
    assert create["entity_label"] == "Powiadomienie"
    assert (update["old_data"], update["new_data"]) == (
        {"deadline": "12:30", "recipients": []},
        {"deadline": "13:00", "recipients": ["a@example.com"]},
    )


async def test_the_status(client, admin_headers):
    body = (await client.get("/reminders/status", headers=admin_headers)).json()

    assert body["smtp_configured"] is False
    assert set(body["checks"]) == {"saldo_palet", "transplaner", "movement"}


async def test_a_test_mail_needs_smtp(client, admin_headers, session):
    row = await reminder(session)

    response = await client.post(f"/reminders/{row.uuid}/test", headers=admin_headers)

    assert response.status_code == 400
    assert response.json() == {
        "message": "Wysyłka poczty nie jest skonfigurowana (SMTP)"
    }


@pytest.mark.parametrize("role", ["manager", "operator", "viewer"])
async def test_only_the_admin_manages_reminders(client, session, role):
    await make_user(session, "jan", role=role)
    headers = await login(client, "jan")

    assert (await client.get("/reminders", headers=headers)).status_code == 403


# ---------- the mail ----------


async def test_after_the_deadline_a_job_not_done_is_mailed_once(session):
    await reminder(session)
    mailer = FakeMailer()

    before = await run_reminders(session, mailer, at(WEDNESDAY, 12, 29))
    after = await run_reminders(session, mailer, at(WEDNESDAY, 12, 31))
    again = await run_reminders(session, mailer, at(WEDNESDAY, 16, 0))

    assert (before, after, again) == ([], ["Wysyłka i zwroty z Transplanera"], [])
    [(recipients, subject, body)] = mailer.sent
    assert recipients == ["kierownik@example.com"]
    assert subject == (
        "MONOLIT: brak danych — Wysyłka i zwroty z Transplanera (14.10.2026)"
    )
    assert "Do godziny 12:30 nie wykonano" in body


async def test_a_job_done_sends_nothing(session, admin_headers):
    await reminder(session)
    admin = (await session.execute(select(User))).scalars().first()
    session.add(DataImport(source="transplaner", user_uuid=admin.uuid))
    await session.commit()
    mailer = FakeMailer()

    mailed = await run_reminders(session, mailer, at(WEDNESDAY, 13, 0))

    assert (mailed, mailer.sent) == ([], [])


async def test_an_operation_entered_today_counts(
    session, client, admin_headers, carriers
):
    await reminder(
        session, name="ECOM", check="movement", movement_type="ECOM_TRANSFER"
    )
    await move(client, admin_headers, "ECOM_TRANSFER", line(carriers.euro, 1))
    mailer = FakeMailer()

    await run_reminders(session, mailer, at(WEDNESDAY, 13, 0))

    assert mailer.sent == []


async def test_no_mail_on_weekends_and_days_off(session):
    await reminder(session)
    await HolidayService(session).add_public(None, 2026)
    await session.commit()
    mailer = FakeMailer()

    weekend = await run_reminders(session, mailer, at(SATURDAY, 13, 0))
    holiday = await run_reminders(session, mailer, at(date(2026, 11, 11), 13, 0))

    assert (weekend, holiday, mailer.sent) == ([], [], [])


@pytest.mark.parametrize("fields", [{"is_active": False}, {"recipients": []}])
async def test_nothing_without_recipients_or_when_off(session, fields):
    await reminder(session, **fields)
    mailer = FakeMailer()

    await run_reminders(session, mailer, at(WEDNESDAY, 13, 0))

    assert mailer.sent == []


async def test_without_smtp_nothing_breaks(session):
    await reminder(session)

    mailed = await run_reminders(session, None, at(WEDNESDAY, 13, 0))

    assert mailed == []


def test_the_mail_has_the_link_when_set(monkeypatch):
    monkeypatch.setattr(settings.app, "APP_URL", "https://monolit.example.com")
    row = Reminder(name="X", check="transplaner", deadline=time(12, 30), recipients=[])

    _subject, body = reminder_mail(row, WEDNESDAY)

    assert "https://monolit.example.com" in body


async def test_the_mailer_talks_smtp(monkeypatch):
    calls = []

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            calls.append(("connect", host, port))

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def starttls(self):
            calls.append(("starttls",))

        def login(self, user, password):
            calls.append(("login", user))

        def send_message(self, message):
            calls.append(("send", message["To"], message["Subject"], message["From"]))

    monkeypatch.setattr(mailer_module.smtplib, "SMTP", FakeSMTP)
    mailer = Mailer(
        "smtp.example.com", 587, "monolit", "secret", "MONOLIT <m@ex.com>", True
    )

    await mailer.send(["a@example.com", "b@example.com"], "Temat", "Treść")

    assert calls == [
        ("connect", "smtp.example.com", 587),
        ("starttls",),
        ("login", "monolit"),
        ("send", "a@example.com, b@example.com", "Temat", "MONOLIT <m@ex.com>"),
    ]
