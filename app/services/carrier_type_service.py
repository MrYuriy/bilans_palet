from typing import Any
from uuid import UUID

from app.core.exc import (
    BadRequestException,
    ObjectAlreadyExistsException,
    ObjectNotFoundException,
)
from app.models.carrier_group import CarrierGroup
from app.models.carrier_type import CarrierType
from app.models.day_closure import DailyBalance
from app.models.inventory import InventoryLine
from app.models.movement import MovementLine
from app.models.user import User
from app.repositories.carrier_type_repo import CarrierTypeRepository
from app.services.dictionary_service import DictionaryService


class CarrierTypeService(DictionaryService[CarrierType]):
    not_found_message = "Nie znaleziono typu nośnika"
    duplicate_message = "Typ nośnika o tej nazwie już istnieje"
    in_use_message = "Typ nośnika występuje w ruchach. Możesz go dezaktywować."
    used_by = (
        MovementLine.carrier_type_uuid,
        InventoryLine.carrier_type_uuid,
        DailyBalance.carrier_type_uuid,
    )
    entity = "carrier_type"

    repo: CarrierTypeRepository

    def __init__(self, session):
        super().__init__(CarrierTypeRepository(session))

    async def list(self, active: bool | None = None) -> list[CarrierType]:
        return await self.repo.list_with_group(active)

    async def get(self, row_uuid: UUID) -> CarrierType:
        row = await self.repo.get_with_group(row_uuid)
        if row is None:
            raise ObjectNotFoundException(self.not_found_message)
        return row

    async def _validate(self, data: dict[str, Any], current: CarrierType | None):
        if "transplaner_name" in data:
            name = (data["transplaner_name"] or "").strip() or None
            data["transplaner_name"] = name
            if name is not None and (
                current is None or name != current.transplaner_name
            ):
                taken = await self.repo.get_one(transplaner_name=name)
                if taken is not None:
                    raise ObjectAlreadyExistsException(
                        f"Nazwa „{name}” z Transplanera jest już przypisana"
                        f" do „{taken.name}”"
                    )
        if "group_uuid" in data and data["group_uuid"] is None:
            del data["group_uuid"]
        group_uuid = data.get("group_uuid")
        if group_uuid is None:
            if current is None:
                raise BadRequestException("Wybierz grupę nośników")
            return
        group = await self.repo.session.get(CarrierGroup, group_uuid)
        if group is None:
            raise BadRequestException("Nieznana grupa nośników")
        moved = current is None or group_uuid != current.group_uuid
        if moved and not group.is_active:
            raise BadRequestException(f"Grupa „{group.name}” jest nieaktywna")

    async def _audit_view(self, row: CarrierType) -> dict[str, Any]:
        # The group by name: a uuid means nothing to whoever reads the log.
        view = await super()._audit_view(row)
        group = await self.repo.session.get(CarrierGroup, view.pop("group_uuid"))
        view["group"] = group.name if group else None
        return view

    async def create(self, actor: User, data: dict[str, Any]) -> CarrierType:
        row = await super().create(actor, data)
        return await self.get(row.uuid)

    async def update(
        self, actor: User, row_uuid: UUID, data: dict[str, Any]
    ) -> CarrierType:
        await super().update(actor, row_uuid, data)
        return await self.get(row_uuid)
