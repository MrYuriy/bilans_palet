from collections.abc import Collection
from datetime import date, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exc import BadRequestException
from app.models.carrier_type import CarrierType
from app.models.day_closure import DailyBalance, DayClosure
from app.repositories.balance_repo import BalanceRepository
from app.repositories.carrier_type_repo import CarrierTypeRepository
from app.repositories.movement_repo import MovementRepository
from app.schemas.balance import (
    CarrierTypeRef,
    CurrentBalanceOut,
    DailyBalanceOut,
    DayRowOut,
    DayValues,
    GroupDay,
    GroupRef,
    GroupStock,
    HistoryOut,
    HistoryPoint,
    StockRow,
)
from app.services.day_balance import DayRow, compute_day
from app.services.settings_service import SettingsService


def _by_group(types: list[CarrierType]) -> list[tuple[GroupRef, list[CarrierType]]]:
    """Types (already in list order) under their groups, groups in that order too."""
    groups: dict[UUID, tuple[GroupRef, list[CarrierType]]] = {}
    for carrier_type in types:
        group = carrier_type.group
        if group.uuid not in groups:
            groups[group.uuid] = (GroupRef.model_validate(group), [])
        groups[group.uuid][1].append(carrier_type)
    return list(groups.values())


class BalanceService:
    """The stock per carrier type: now, and per warehouse day.

    Reports show the types counted in reports unless the viewer picks others
    (``type_uuids``); a group's total adds up the rows shown.
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.movements = MovementRepository(session)
        self.types = CarrierTypeRepository(session)
        self.balances = BalanceRepository(session)
        self.settings = SettingsService(session)

    async def _shown(
        self, with_data: set[UUID], type_uuids: Collection[UUID] | None
    ) -> list[CarrierType]:
        """The types picked; by default the counted ones. An inactive type shows
        only while it still has something to show."""
        types = await self.types.list_with_group()
        if type_uuids is None:
            picked = [t for t in types if t.count_in_reports]
        else:
            wanted = set(type_uuids)
            picked = [t for t in types if t.uuid in wanted]
        return [t for t in picked if t.is_active or t.uuid in with_data]

    # ---------- now ----------

    async def current(
        self, type_uuids: Collection[UUID] | None = None
    ) -> CurrentBalanceOut:
        stock = await self.movements.balances()
        types = await self._shown({k for k, v in stock.items() if v}, type_uuids)

        groups = []
        for group, members in _by_group(types):
            rows = [
                StockRow(
                    carrier_type=CarrierTypeRef.model_validate(t),
                    quantity=stock.get(t.uuid, 0),
                )
                for t in members
            ]
            groups.append(
                GroupStock(group=group, rows=rows, total=sum(r.quantity for r in rows))
            )
        return CurrentBalanceOut(groups=groups)

    # ---------- per day ----------

    async def daily(
        self, day: date | None, type_uuids: Collection[UUID] | None = None
    ) -> DailyBalanceOut:
        """A closed day from its stored balance; the current day as a live preview.
        Without a day: the last closed one (D-1), or today while none is closed."""
        current_day = await self.settings.current_day()
        if day is None:
            day = await self.settings.last_closed_day() or current_day
        if day > current_day:
            raise BadRequestException("Ta doba jeszcze się nie zaczęła")

        closure = (
            await self.session.execute(
                select(DayClosure).where(DayClosure.business_date == day)
            )
        ).scalar_one_or_none()

        if closure is not None:
            stored = (
                await self.session.execute(
                    select(DailyBalance).where(DailyBalance.business_date == day)
                )
            ).scalars()
            day_rows = {
                r.carrier_type_uuid: DayRow(
                    r.carrier_type_uuid,
                    r.opening,
                    r.receipts,
                    r.shipments,
                    r.corrections,
                    r.reclassifications,
                )
                for r in stored
            }
        else:
            day_rows = {
                r.carrier_type_uuid: r for r in await compute_day(self.session, day)
            }

        types = await self._shown(set(day_rows), type_uuids)
        groups = []
        for group, members in _by_group(types):
            rows = [
                DayRowOut(
                    carrier_type=CarrierTypeRef.model_validate(t),
                    **day_rows.get(t.uuid, DayRow(t.uuid)).values(),
                )
                for t in members
            ]
            total = DayValues(
                **{
                    field: sum(getattr(r, field) for r in rows)
                    for field in DayValues.model_fields
                }
            )
            groups.append(GroupDay(group=group, rows=rows, total=total))

        return DailyBalanceOut(
            day=day,
            closed=closure is not None,
            closed_at=closure.created_at if closure else None,
            groups=groups,
        )

    # ---------- over time ----------

    async def history(
        self, days: int, type_uuids: Collection[UUID] | None = None
    ) -> HistoryOut:
        """The stock of the picked types (by default those counted in reports)
        at the end of each of the last ``days`` days, today included."""
        if type_uuids is None:
            picked = {
                t.uuid for t in await self.types.list_with_group() if t.count_in_reports
            }
        else:
            picked = set(type_uuids)

        last = await self.settings.current_day()
        first = last - timedelta(days=days - 1)

        stock = sum(
            total
            for t, total in (await self.balances.opening(first)).items()
            if t in picked
        )
        moved: dict[date, int] = {}
        for day, type_uuid, total in await self.balances.daily_totals(first, last):
            if type_uuid in picked:
                moved[day] = moved.get(day, 0) + total

        points = []
        for offset in range(days):
            day = first + timedelta(days=offset)
            stock += moved.get(day, 0)
            points.append(HistoryPoint(day=day, quantity=stock))
        return HistoryOut(days=points)
