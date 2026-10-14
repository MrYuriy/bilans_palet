from dataclasses import dataclass, fields
from datetime import date
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.balance_repo import BalanceRepository
from app.services.operation_catalog import OPERATIONS, SHIPMENTS


@dataclass
class DayRow:
    """One carrier type of a warehouse day."""

    carrier_type_uuid: UUID
    opening: int = 0
    receipts: int = 0  # positive
    shipments: int = 0  # positive: carriers that left
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

    def values(self) -> dict[str, int]:
        moved = {f.name: getattr(self, f.name) for f in fields(self)[1:]}
        return {**moved, "closing": self.closing}


async def compute_day(session: AsyncSession, day: date) -> list[DayRow]:
    """The day's balance per carrier type: every type that had stock at the
    start of the day or moved during it. Each operation adds up in the column
    the catalog gives it."""
    repo = BalanceRepository(session)
    rows: dict[UUID, DayRow] = {}

    def row(type_uuid: UUID) -> DayRow:
        if type_uuid not in rows:
            rows[type_uuid] = DayRow(type_uuid)
        return rows[type_uuid]

    for type_uuid, total in (await repo.opening(day)).items():
        if total:
            row(type_uuid).opening = total

    for type_uuid, kind, total in await repo.day_moves(day):
        target = row(type_uuid)
        category = OPERATIONS[kind].category
        # Shipment lines are stored negative; the balance shows how many left.
        amount = -total if category == SHIPMENTS else total
        setattr(target, category, getattr(target, category) + amount)

    return list(rows.values())
