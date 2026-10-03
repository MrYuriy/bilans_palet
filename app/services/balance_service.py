from collections import defaultdict
from collections.abc import Iterable
from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exc import BadRequestException, ForbiddenException
from app.models.area import Area
from app.models.day_closure import DailyBalance, DayClosure
from app.models.pallet_type import PalletType
from app.models.quality import Quality
from app.models.user import User
from app.repositories.balance_repo import BalanceRepository, DayRow
from app.schemas.balance import (
    AreaDay,
    AreaStock,
    CurrentBalanceOut,
    DailyBalanceOut,
    DayRowOut,
    StockRow,
)
from app.schemas.common import NamedRef
from app.services.permission_service import PermissionService
from app.services.settings_service import SettingsService

_DAY_FIELDS = (
    "opening",
    "receipts",
    "shipments",
    "corrections",
    "reclassifications",
    "closing",
)


class BalanceService:
    """Balances per area and in total: now, and per warehouse day."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = BalanceRepository(session)
        self.settings = SettingsService(session)
        self.permissions = PermissionService()

    # ---------- shared ----------

    async def _areas(self, user: User, area_uuid: UUID | None) -> list[Area]:
        """Areas the user may see (all of them, or the assigned ones), optionally
        just one."""
        if self.permissions.reads_every_area(user.role.name):
            areas = list(
                (await self.session.execute(select(Area).order_by(Area.name))).scalars()
            )
        else:
            areas = sorted(user.areas, key=lambda a: a.name)

        if area_uuid is None:
            return areas
        chosen = [a for a in areas if a.uuid == area_uuid]
        if not chosen:
            raise ForbiddenException("Brak dostępu do obszaru")
        return chosen

    async def _dictionaries(self):
        pallet_types = {
            t.uuid: t
            for t in (await self.session.execute(select(PalletType))).scalars()
        }
        qualities = {
            q.uuid: q for q in (await self.session.execute(select(Quality))).scalars()
        }
        return pallet_types, qualities

    @staticmethod
    def _order(pallet_types, qualities):
        def key(pair: tuple[UUID, UUID]):
            type_uuid, quality_uuid = pair
            return pallet_types[type_uuid].name, qualities[quality_uuid].sort_order

        return key

    @staticmethod
    def _active_pairs(pallet_types, qualities) -> set[tuple[UUID, UUID]]:
        return {
            (t.uuid, q.uuid)
            for t in pallet_types.values()
            if t.is_active
            for q in qualities.values()
            if q.is_active
        }

    @staticmethod
    def _shown(areas: list[Area], with_data: Iterable[UUID]) -> list[Area]:
        """Active areas, plus inactive ones that still have something to show."""
        with_data = set(with_data)
        return [a for a in areas if a.is_active or a.uuid in with_data]

    # ---------- now ----------

    async def current(self, user: User, area_uuid: UUID | None) -> CurrentBalanceOut:
        areas = await self._areas(user, area_uuid)
        visible = {a.uuid for a in areas}
        stock = {
            k: v for k, v in (await self.repo.current()).items() if k[0] in visible
        }
        pallet_types, qualities = await self._dictionaries()
        order = self._order(pallet_types, qualities)
        active = self._active_pairs(pallet_types, qualities)

        def row(pair, quantity) -> StockRow:
            return StockRow(
                pallet_type=NamedRef.model_validate(pallet_types[pair[0]]),
                quality=NamedRef.model_validate(qualities[pair[1]]),
                quantity=quantity,
            )

        total: dict[tuple[UUID, UUID], int] = defaultdict(int)
        out = []
        for area in self._shown(areas, (k[0] for k, v in stock.items() if v)):
            held = {(k[1], k[2]): v for k, v in stock.items() if k[0] == area.uuid}
            pairs = active | {pair for pair, v in held.items() if v}
            for pair in pairs:
                total[pair] += held.get(pair, 0)
            out.append(
                AreaStock(
                    area=NamedRef.model_validate(area),
                    rows=[row(p, held.get(p, 0)) for p in sorted(pairs, key=order)],
                )
            )

        return CurrentBalanceOut(
            areas=out,
            total=[row(p, total[p]) for p in sorted(total, key=order)],
        )

    # ---------- per day ----------

    async def daily(
        self, user: User, day: date | None, area_uuid: UUID | None
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
            rows = [
                DayRow(
                    r.area_uuid,
                    r.pallet_type_uuid,
                    r.quality_uuid,
                    r.opening,
                    r.receipts,
                    r.shipments,
                    r.corrections,
                    r.reclassifications,
                )
                for r in stored
            ]
        else:
            rows = await self.repo.compute_day(day)

        areas = await self._areas(user, area_uuid)
        visible = {a.uuid for a in areas}
        rows = [r for r in rows if r.area_uuid in visible]
        pallet_types, qualities = await self._dictionaries()
        order = self._order(pallet_types, qualities)

        def out_row(pair, values: dict[str, int]) -> DayRowOut:
            return DayRowOut(
                pallet_type=NamedRef.model_validate(pallet_types[pair[0]]),
                quality=NamedRef.model_validate(qualities[pair[1]]),
                **values,
            )

        def values_of(r: DayRow) -> dict[str, int]:
            return {f: getattr(r, f) for f in _DAY_FIELDS}

        total: dict[tuple[UUID, UUID], dict[str, int]] = defaultdict(
            lambda: dict.fromkeys(_DAY_FIELDS, 0)
        )
        out = []
        for area in self._shown(areas, (r.area_uuid for r in rows)):
            area_rows = {
                (r.pallet_type_uuid, r.quality_uuid): r
                for r in rows
                if r.area_uuid == area.uuid
            }
            for pair, r in area_rows.items():
                for f in _DAY_FIELDS:
                    total[pair][f] += getattr(r, f)
            out.append(
                AreaDay(
                    area=NamedRef.model_validate(area),
                    rows=[
                        out_row(p, values_of(area_rows[p]))
                        for p in sorted(area_rows, key=order)
                    ],
                )
            )

        return DailyBalanceOut(
            day=day,
            closed=closure is not None,
            closed_at=closure.created_at if closure else None,
            areas=out,
            total=[out_row(p, total[p]) for p in sorted(total, key=order)],
        )
