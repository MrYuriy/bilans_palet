import asyncio
import logging
from collections.abc import Callable
from datetime import date, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exc import BadRequestException
from app.core.timeutils import business_date, local_now
from app.models.day_closure import DailyBalance, DayClosure
from app.repositories.area_repo import AreaRepository
from app.repositories.balance_repo import BalanceRepository
from app.services.settings_service import SettingsService

logger = logging.getLogger(__name__)


class DayCloseService:
    """Closes warehouse days and keeps their balance.

    A day closes when the next one starts (the cut-off hour). Closing stores the
    day's balance and from then on nothing can be entered for that day.
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.settings = SettingsService(session)
        self.balances = BalanceRepository(session)
        self.area_repo = AreaRepository(session)

    async def close_day(self, day: date) -> None:
        """Close one day and store its balance (the caller commits)."""
        # Movements lock their area before checking the day is open, so with
        # every area held no movement of this day is still being written.
        await self.area_repo.lock_all()
        self.session.add(DayClosure(business_date=day))
        for row in await self.balances.compute_day(day):
            self.session.add(
                DailyBalance(
                    business_date=day,
                    area_uuid=row.area_uuid,
                    pallet_type_uuid=row.pallet_type_uuid,
                    quality_uuid=row.quality_uuid,
                    opening=row.opening,
                    receipts=row.receipts,
                    shipments=row.shipments,
                    corrections=row.corrections,
                    reclassifications=row.reclassifications,
                    closing=row.closing,
                )
            )
        await self.session.flush()

    async def due_days(self, now: datetime | None = None) -> list[date]:
        """Days that have ended and are not closed yet, oldest first."""
        current = business_date(now or local_now(), await self.settings.day_cutoff())
        last_closed = await self.settings.last_closed_day()
        if last_closed is not None:
            start = last_closed + timedelta(days=1)
        else:
            # Nothing closed yet: from the first movement, or just yesterday.
            yesterday = current - timedelta(days=1)
            first = await self.balances.first_movement_day()
            start = min(first, yesterday) if first else yesterday
        return [
            start + timedelta(days=offset) for offset in range((current - start).days)
        ]

    async def close_due_days(self, now: datetime | None = None) -> list[date]:
        """Close every day that has ended, one transaction per day, so a day that
        was closed stays closed even if a later one fails. Catches up on days
        missed while the app was down."""
        closed = []
        for day in await self.due_days(now):
            await self.close_day(day)
            await self.session.commit()
            logger.info("Closed warehouse day %s", day)
            closed.append(day)
        return closed


async def ensure_day_open(session: AsyncSession, day: date) -> None:
    """Refuse a change dated on a closed day. Call it with the area locked."""
    last_closed = await SettingsService(session).last_closed_day()
    if last_closed is not None and day <= last_closed:
        raise BadRequestException(f"Doba {day.strftime('%d.%m.%Y')} jest już zamknięta")


async def day_close_loop(
    session_factory: Callable[[], AsyncSession], interval_seconds: int
) -> None:
    """Background task: close the days that have ended, then check again every
    interval. Runs from app start, so days missed while it was down close first."""
    while True:
        try:
            async with session_factory() as session:
                await DayCloseService(session).close_due_days()
        except Exception:
            # Keep the loop alive; the next round retries the same day.
            logger.exception("Closing warehouse days failed")
        await asyncio.sleep(interval_seconds)
