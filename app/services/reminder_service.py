"""Reminders: what the team must do each working day by a given time, and the
mail that goes out when it is not done.

A reminder is checked once a day, after its deadline, on working days only
(Monday to Friday, not a day off). Done means: the Saldo Palet import ran
today, a Transplaner file was uploaded today, or a movement of the given type
was entered today.
"""

import asyncio
import logging
import re
from collections.abc import Callable
from datetime import date, datetime, time
from typing import Any, ClassVar

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exc import BadRequestException
from app.core.timeutils import local_now
from app.models.data_import import DataImport
from app.models.movement import Movement, MovementType
from app.models.reminder import Reminder
from app.repositories.reminder_repo import ReminderRepository
from app.services.dictionary_service import DictionaryService
from app.services.holiday_service import HolidayService
from app.services.mailer import Mailer, configured_mailer
from app.services.operation_catalog import OPERATIONS

logger = logging.getLogger(__name__)

# What a reminder checks, as the admin reads it.
CHECKS = {
    "saldo_palet": "Import z Salda Palet",
    "transplaner": "Plik z Transplanera",
    "movement": "Operacja",
}
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def describe(reminder: Reminder) -> str:
    """What the reminder waits for, in Polish."""
    if reminder.check == "movement" and reminder.movement_type:
        return f"Operacja: {OPERATIONS[MovementType(reminder.movement_type)].label}"
    return CHECKS.get(reminder.check, reminder.check)


class ReminderService(DictionaryService[Reminder]):
    not_found_message = "Nie znaleziono powiadomienia"
    duplicate_message = "Powiadomienie o tej nazwie już istnieje"
    in_use_message = ""
    used_by = ()
    entity = "reminder"
    _NOT_AUDITED: ClassVar[set[str]] = {"last_run_on", "last_sent_on"}

    def __init__(self, session):
        super().__init__(ReminderRepository(session))

    def _order_by(self) -> list:
        return [Reminder.deadline, Reminder.name]

    async def _validate(self, data: dict[str, Any], current: Reminder | None) -> None:
        check = data.get("check", current.check if current else None)
        if check not in CHECKS:
            raise BadRequestException("Wybierz, co ma być sprawdzane")
        movement_type = data.get(
            "movement_type", current.movement_type if current else None
        )
        if check == "movement":
            if movement_type is None:
                raise BadRequestException("Wybierz operację do sprawdzania")
        elif "check" in data or "movement_type" in data:
            data["movement_type"] = None
        if "recipients" in data:
            recipients = []
            for raw in data["recipients"] or []:
                address = raw.strip()
                if not address:
                    continue
                if not _EMAIL.match(address):
                    raise BadRequestException(f"Nieprawidłowy adres e-mail: {address}")
                if address.lower() not in {r.lower() for r in recipients}:
                    recipients.append(address)
            data["recipients"] = recipients
        if "deadline" in data and data["deadline"] is not None:
            data["deadline"] = data["deadline"].replace(second=0, microsecond=0)

    async def _audit_view(self, row: Reminder) -> dict[str, Any]:
        view = await super()._audit_view(row)
        for field in self._NOT_AUDITED:
            view.pop(field, None)
        view["deadline"] = row.deadline.strftime("%H:%M") if row.deadline else None
        if row.movement_type is not None:
            view["movement_type"] = MovementType(row.movement_type).value
        return view


async def is_done(session: AsyncSession, reminder: Reminder, day: date) -> bool:
    start = datetime.combine(day, time())
    if reminder.check in ("saldo_palet", "transplaner"):
        condition = exists().where(
            DataImport.source == reminder.check, DataImport.created_at >= start
        )
    else:
        condition = exists().where(
            Movement.type == reminder.movement_type, Movement.created_at >= start
        )
    return (await session.execute(select(condition))).scalar_one()


def reminder_mail(reminder: Reminder, day: date) -> tuple[str, str]:
    deadline = reminder.deadline.strftime("%H:%M")
    subject = f"MONOLIT: brak danych — {reminder.name} ({day:%d.%m.%Y})"
    lines = [
        f"Do godziny {deadline} nie wykonano: {reminder.name}.",
        f"Sprawdzane: {describe(reminder)}.",
        "",
        "Prosimy o uzupełnienie danych w MONOLIT.",
    ]
    if settings.app.APP_URL:
        lines.append(settings.app.APP_URL)
    lines += ["", "— wiadomość wysłana automatycznie"]
    return subject, "\n".join(lines)


async def run_reminders(
    session: AsyncSession, mailer: Mailer | None, now: datetime
) -> list[str]:
    """Check the reminders whose deadline has passed today; mail those not
    done. Returns the names mailed. The caller commits."""
    today = now.date()
    if not await HolidayService(session).is_working_day(today):
        return []
    due = (
        await session.execute(
            select(Reminder).where(
                Reminder.is_active.is_(True), Reminder.deadline <= now.time()
            )
        )
    ).scalars()
    mailed = []
    for reminder in due:
        if reminder.last_run_on == today:
            continue
        reminder.last_run_on = today
        if await is_done(session, reminder, today):
            continue
        if not reminder.recipients:
            logger.warning(
                "Reminder %s not done, but it has no recipients", reminder.name
            )
            continue
        if mailer is None:
            logger.warning("Reminder %s not done, but SMTP is not set", reminder.name)
            continue
        subject, body = reminder_mail(reminder, today)
        await mailer.send(list(reminder.recipients), subject, body)
        reminder.last_sent_on = today
        mailed.append(reminder.name)
    await session.flush()
    return mailed


async def reminders_loop(
    session_factory: Callable[[], AsyncSession], interval_seconds: int = 60
) -> None:
    """Background task: once a minute, check the reminders that are due."""
    while True:
        try:
            async with session_factory() as session:
                mailed = await run_reminders(session, configured_mailer(), local_now())
                await session.commit()
                for name in mailed:
                    logger.info("Reminder mailed: %s", name)
        except Exception:
            logger.exception("Checking reminders failed")
        await asyncio.sleep(interval_seconds)
