from datetime import date
from uuid import UUID

from sqlalchemy import func, select

from app.models.movement import Movement, MovementLine, MovementType


class BalanceRepository:
    """Sums of movement lines by warehouse day (the movement's operation_date)."""

    def __init__(self, session):
        self.session = session

    async def opening(self, day: date) -> dict[UUID, int]:
        """Stock per carrier type at the start of the day."""
        query = (
            select(MovementLine.carrier_type_uuid, func.sum(MovementLine.quantity))
            .join(Movement, MovementLine.movement_uuid == Movement.uuid)
            .where(Movement.operation_date < day)
            .group_by(MovementLine.carrier_type_uuid)
        )
        return dict((await self.session.execute(query)).all())

    async def day_moves(self, day: date) -> list[tuple[UUID, MovementType, int]]:
        """What moved during the day: (carrier type, movement type, signed sum)."""
        query = (
            select(
                MovementLine.carrier_type_uuid,
                Movement.type,
                func.sum(MovementLine.quantity),
            )
            .join(Movement, MovementLine.movement_uuid == Movement.uuid)
            .where(Movement.operation_date == day)
            .group_by(MovementLine.carrier_type_uuid, Movement.type)
        )
        return [
            (type_uuid, MovementType(kind), total)
            for type_uuid, kind, total in await self.session.execute(query)
        ]

    async def daily_totals(
        self, first: date, last: date
    ) -> list[tuple[date, UUID, int]]:
        """Signed sum per (day, carrier type) of the movements in the range."""
        query = (
            select(
                Movement.operation_date,
                MovementLine.carrier_type_uuid,
                func.sum(MovementLine.quantity),
            )
            .join(Movement, MovementLine.movement_uuid == Movement.uuid)
            .where(Movement.operation_date >= first, Movement.operation_date <= last)
            .group_by(Movement.operation_date, MovementLine.carrier_type_uuid)
        )
        return list((await self.session.execute(query)).all())

    async def first_movement_day(self) -> date | None:
        return (
            await self.session.execute(select(func.min(Movement.operation_date)))
        ).scalar_one()
