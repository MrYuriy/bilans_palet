"""Booking the deliveries from Saldo Palet, once a day for the day before.

The manager's rule: a receipt (IN) adds to the stock, a return to the supplier
(OUT) takes from it, a correction counts the other way round (Saldo Palet
keeps the balance owed to the supplier, not the stock). Transactions count on
the day they were entered ("Data_dodania"); nothing is counted backwards.
Only units mapped to a carrier type count (EUR, euro uszkodzone, ...).

One movement per day, a line per carrier type with the day's net, dated the
day of the import. A day without transactions is still recorded (0), so the
morning check can see the import ran.
"""

import asyncio
import logging
from collections import defaultdict
from collections.abc import Callable
from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.config import settings
from app.core.exc import BadRequestException
from app.core.timeutils import local_now
from app.models.carrier_type import CarrierType
from app.models.data_import import DataImport, ImportDay
from app.models.movement import Movement, MovementLine, MovementType
from app.models.user import User
from app.repositories.import_repo import ImportRepository
from app.schemas.data_import import ImportOut
from app.services.day_close_service import ensure_day_open
from app.services.movement_service import MovementService
from app.services.operation_catalog import OPERATIONS
from app.services.saldo_palet_client import SaldoPaletClient, configured_client
from app.services.settings_service import SettingsService

logger = logging.getLogger(__name__)

SOURCE = "saldo_palet"
KIND = MovementType.SALDO_RECEIPT
SYSTEM_USERNAME = "system"


def effect(transaction_type: str, quantity: int) -> int:
    """How a Saldo Palet transaction changes the warehouse stock."""
    if transaction_type == "RECEIPT":
        return quantity
    # A return to the supplier takes pallets away; a correction of the
    # balance owed counts the other way round.
    return -quantity


class SaldoPaletImportService:
    def __init__(self, session: AsyncSession, client: SaldoPaletClient | None):
        self.session = session
        self.client = client
        self.repo = ImportRepository(session)
        self.movements = MovementService(session)

    def check_allowed(self, user: User) -> None:
        """For an import someone starts by hand (the morning one runs as system)."""
        self.movements.check_allowed(user, OPERATIONS[KIND])

    async def import_day(self, author: User, day: date) -> ImportOut:
        """Book the transactions entered on ``day`` (only a day that is over).
        Running it again books only what changed since."""
        today = local_now().date()
        if day >= today:
            raise BadRequestException("Można pobrać tylko zakończony dzień")

        transactions = await self.client.transactions_added_on(day)

        types = {
            t.saldo_palet_unit.strip().lower(): t
            for t in (
                await self.session.execute(
                    select(CarrierType).where(CarrierType.saldo_palet_unit.is_not(None))
                )
            ).scalars()
        }
        net: dict[CarrierType, int] = {t: 0 for t in types.values()}
        parts: dict[str, dict[str, int]] = defaultdict(
            lambda: {"in": 0, "out": 0, "corrections": 0}
        )
        ignored: dict[str, int] = defaultdict(int)
        for tr in transactions:
            carrier_type = types.get(tr.unit.strip().lower())
            if carrier_type is None:
                ignored[tr.unit] += 1
                continue
            net[carrier_type] += effect(tr.type, tr.quantity)
            key = {"RECEIPT": "in", "ISSUE": "out"}.get(tr.type, "corrections")
            parts[carrier_type.name][key] += tr.quantity

        # Held until commit, like any movement.
        await self.movements.lock.shared()
        booking_day = await SettingsService(self.session).current_day()
        await ensure_day_open(self.session, booking_day)

        data_import = DataImport(source=SOURCE, user_uuid=author.uuid)
        self.session.add(data_import)
        await self.session.flush()

        lines, summary_types = [], {}
        for carrier_type, quantity in net.items():
            booked = (
                await self.session.execute(
                    select(ImportDay).where(
                        ImportDay.source == SOURCE,
                        ImportDay.carrier_type_uuid == carrier_type.uuid,
                        ImportDay.movement_type == KIND,
                        ImportDay.day == day,
                    )
                )
            ).scalar_one_or_none()
            change = quantity - (booked.quantity if booked else 0)
            if change:
                lines.append(
                    MovementLine(
                        position=len(lines) + 1,
                        carrier_type_uuid=carrier_type.uuid,
                        quantity=change,
                    )
                )
            if booked is None:
                self.session.add(
                    ImportDay(
                        source=SOURCE,
                        carrier_type_uuid=carrier_type.uuid,
                        movement_type=KIND,
                        day=day,
                        quantity=quantity,
                    )
                )
            else:
                booked.quantity = quantity
            summary_types[carrier_type.name] = {
                **parts[carrier_type.name],
                "net": quantity,
                "change": change,
            }

        if lines:
            self.session.add(
                Movement(
                    type=KIND,
                    user_uuid=author.uuid,
                    operation_date=booking_day,
                    comment=self._comment(day, summary_types),
                    import_uuid=data_import.uuid,
                    lines=lines,
                )
            )
        data_import.summary = {
            "day": day.isoformat(),
            "transactions": len(transactions),
            "types": summary_types,
            "ignored": dict(ignored),
        }
        await self.session.flush()
        self.session.expunge(data_import)
        return await self._get(data_import.uuid)

    @staticmethod
    def _comment(day: date, summary_types: dict) -> str:
        parts = [
            f"{name} IN {v['in']}, OUT {v['out']}, korekty {v['corrections']}"
            for name, v in summary_types.items()
            if v["in"] or v["out"] or v["corrections"]
        ]
        return f"Saldo Palet {day:%d.%m.%Y} — " + ("; ".join(parts) or "bez transakcji")

    async def _get(self, import_uuid) -> ImportOut:
        row = (
            await self.session.execute(
                select(DataImport)
                .options(joinedload(DataImport.user))
                .where(DataImport.uuid == import_uuid)
            )
        ).scalar_one()
        return ImportOut.model_validate(row)

    async def recent(self, limit: int = 20) -> list[ImportOut]:
        return [
            ImportOut.model_validate(r) for r in await self.repo.recent(SOURCE, limit)
        ]

    async def due_days(self, now: datetime | None = None) -> list[date]:
        """Days over and not imported yet, oldest first: from the day after the
        last import (at most CATCH_UP_DAYS back), else just yesterday."""
        yesterday = (now or local_now()).date() - timedelta(days=1)
        last = (
            await self.session.execute(
                select(func.max(ImportDay.day)).where(ImportDay.source == SOURCE)
            )
        ).scalar_one()
        oldest = yesterday - timedelta(days=settings.app.SALDO_PALET_CATCH_UP_DAYS - 1)
        start = yesterday if last is None else max(last + timedelta(days=1), oldest)
        return [start + timedelta(days=n) for n in range((yesterday - start).days + 1)]


async def system_user(session: AsyncSession) -> User:
    user = (
        await session.execute(select(User).where(User.username == SYSTEM_USERNAME))
    ).scalar_one_or_none()
    if user is None:
        raise BadRequestException("Brak użytkownika systemowego (uruchom seed)")
    return user


def _import_at() -> tuple[int, int]:
    hours, minutes = settings.app.SALDO_PALET_IMPORT_AT.split(":")
    return int(hours), int(minutes)


async def saldo_palet_loop(
    session_factory: Callable[[], AsyncSession], interval_seconds: int = 60
) -> None:
    """Background task: after the import hour, book the days not imported yet.
    Off while Saldo Palet is not configured. A failure is retried later."""
    client = configured_client()
    if client is None:
        logger.info("Saldo Palet import is off (SALDO_PALET_URL not set)")
        return
    while True:
        wait = interval_seconds
        try:
            now = local_now()
            if (now.hour, now.minute) >= _import_at():
                async with session_factory() as session:
                    service = SaldoPaletImportService(session, client)
                    author = await system_user(session)
                    for day in await service.due_days(now):
                        await service.import_day(author, day)
                        await session.commit()
                        logger.info("Imported Saldo Palet for %s", day)
        except Exception:
            logger.exception("Saldo Palet import failed; retrying in 10 minutes")
            wait = 600
        await asyncio.sleep(wait)
