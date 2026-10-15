from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import joinedload

from app.models.carrier_group import CarrierGroup
from app.models.carrier_type import CarrierType
from app.repositories.base import BaseRepository

# Grouped by group, then in the admin's order inside it.
TYPE_ORDER = (CarrierGroup.name, CarrierType.sort_order, CarrierType.name)


class CarrierTypeRepository(BaseRepository[CarrierType]):
    def __init__(self, session):
        super().__init__(session, CarrierType)

    async def list_with_group(self, active: bool | None = None) -> list[CarrierType]:
        query = (
            select(CarrierType)
            .join(CarrierType.group)
            .options(joinedload(CarrierType.group))
            .order_by(*TYPE_ORDER)
        )
        if active is not None:
            query = query.where(CarrierType.is_active == active)
        return list((await self.session.execute(query)).scalars().all())

    async def get_by_saldo_palet_unit(self, unit: str) -> CarrierType | None:
        query = select(CarrierType).where(
            func.lower(CarrierType.saldo_palet_unit) == unit.strip().lower()
        )
        return (await self.session.execute(query)).scalar_one_or_none()

    async def get_with_group(self, type_uuid: UUID) -> CarrierType | None:
        # populate_existing: after update_one the group relationship has expired.
        query = (
            select(CarrierType)
            .options(joinedload(CarrierType.group))
            .where(CarrierType.uuid == type_uuid)
            .execution_options(populate_existing=True)
        )
        return (await self.session.execute(query)).scalar_one_or_none()
