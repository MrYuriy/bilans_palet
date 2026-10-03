from dataclasses import dataclass
from datetime import date
from uuid import UUID

from sqlalchemy import func, select

from app.models.movement import Movement, MovementLine, MovementType

# How each movement type shows in a day's balance.
CATEGORY = {
    MovementType.RECEIPT: "receipts",
    MovementType.LM_PURCHASE: "receipts",
    MovementType.SHIPMENT: "shipments",
    MovementType.CORRECTION: "corrections",
    MovementType.INVENTORY: "corrections",
    MovementType.RECLASSIFICATION: "reclassifications",
}

Key = tuple[UUID, UUID, UUID]  # area, pallet type, quality


@dataclass
class DayRow:
    """One area / pallet type / quality of a warehouse day."""

    area_uuid: UUID
    pallet_type_uuid: UUID
    quality_uuid: UUID
    opening: int = 0
    receipts: int = 0  # positive
    shipments: int = 0  # positive: pallets that left
    corrections: int = 0  # signed, stock counts included
    reclassifications: int = 0  # signed

    @property
    def closing(self) -> int:
        return (
            self.opening
            + self.receipts
            - self.shipments
            + self.corrections
            + self.reclassifications
        )


class BalanceRepository:
    """Sums of movement lines by warehouse day (the movement's operation_date)."""

    def __init__(self, session):
        self.session = session

    async def compute_day(self, day: date) -> list[DayRow]:
        """The day's balance per area, pallet type and quality: every row that had
        pallets at the start of the day or moved during it."""
        key_columns = (
            Movement.area_uuid,
            MovementLine.pallet_type_uuid,
            MovementLine.quality_uuid,
        )
        opening_query = (
            select(*key_columns, func.sum(MovementLine.quantity))
            .join(Movement, MovementLine.movement_uuid == Movement.uuid)
            .where(Movement.operation_date < day)
            .group_by(*key_columns)
        )
        day_query = (
            select(*key_columns, Movement.type, func.sum(MovementLine.quantity))
            .join(Movement, MovementLine.movement_uuid == Movement.uuid)
            .where(Movement.operation_date == day)
            .group_by(*key_columns, Movement.type)
        )

        rows: dict[Key, DayRow] = {}

        def row(key: Key) -> DayRow:
            if key not in rows:
                rows[key] = DayRow(*key)
            return rows[key]

        for area, pallet_type, quality, total in await self.session.execute(
            opening_query
        ):
            if total:
                row((area, pallet_type, quality)).opening = total

        for area, pallet_type, quality, kind, total in await self.session.execute(
            day_query
        ):
            target = row((area, pallet_type, quality))
            category = CATEGORY[MovementType(kind)]
            # Shipment lines are stored negative; the balance shows how many left.
            amount = -total if category == "shipments" else total
            setattr(target, category, getattr(target, category) + amount)

        return list(rows.values())

    async def current(self) -> dict[Key, int]:
        """What every area holds now, per pallet type and quality."""
        key_columns = (
            Movement.area_uuid,
            MovementLine.pallet_type_uuid,
            MovementLine.quality_uuid,
        )
        query = (
            select(*key_columns, func.sum(MovementLine.quantity))
            .join(Movement, MovementLine.movement_uuid == Movement.uuid)
            .group_by(*key_columns)
        )
        return {
            (area, pallet_type, quality): total
            for area, pallet_type, quality, total in await self.session.execute(query)
        }

    async def first_movement_day(self) -> date | None:
        return (
            await self.session.execute(select(func.min(Movement.operation_date)))
        ).scalar_one()
