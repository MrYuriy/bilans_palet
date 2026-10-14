from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exc import BadRequestException
from app.models.carrier_type import CarrierType
from app.models.day_closure import DailyBalance, DayClosure
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

    A group's total adds up only the types counted in reports.
    """

    def __init__(self, session: AsyncSession):
        self.session = session
        self.movements = MovementRepository(session)
        self.types = CarrierTypeRepository(session)
        self.settings = SettingsService(session)

    async def _shown(self, with_data: set[UUID]) -> list[CarrierType]:
        """Active types, plus inactive ones that still have something to show."""
        return [
            t
            for t in await self.types.list_with_group()
            if t.is_active or t.uuid in with_data
        ]

    # ---------- now ----------

    async def current(self) -> CurrentBalanceOut:
        stock = await self.movements.balances()
        types = await self._shown({k for k, v in stock.items() if v})

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
                GroupStock(
                    group=group,
                    rows=rows,
                    total=sum(
                        r.quantity for r in rows if r.carrier_type.count_in_reports
                    ),
                )
            )
        return CurrentBalanceOut(groups=groups)

    # ---------- per day ----------

    async def daily(self, day: date | None) -> DailyBalanceOut:
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

        types = await self._shown(set(day_rows))
        groups = []
        for group, members in _by_group(types):
            rows = [
                DayRowOut(
                    carrier_type=CarrierTypeRef.model_validate(t),
                    **day_rows.get(t.uuid, DayRow(t.uuid)).values(),
                )
                for t in members
            ]
            total = DayValues()
            for r in rows:
                if r.carrier_type.count_in_reports:
                    for field in DayValues.model_fields:
                        setattr(total, field, getattr(total, field) + getattr(r, field))
            groups.append(GroupDay(group=group, rows=rows, total=total))

        return DailyBalanceOut(
            day=day,
            closed=closure is not None,
            closed_at=closure.created_at if closure else None,
            groups=groups,
        )
