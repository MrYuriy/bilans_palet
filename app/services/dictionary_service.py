from typing import Any, ClassVar
from uuid import UUID

from sqlalchemy import exists, select
from sqlalchemy.orm import InstrumentedAttribute

from app.core.exc import (
    BadRequestException,
    ObjectAlreadyExistsException,
    ObjectNotFoundException,
)
from app.repositories.base import BaseRepository


class DictionaryService[ModelType]:
    """Shared CRUD for the admin-managed dictionaries (areas, pallet types, qualities).

    Every dictionary row has a unique ``name`` and an ``is_active`` flag.
    Subclasses set the Polish messages, the list order and where movements
    refer to the row (a row in use is deactivated, never deleted).
    """

    not_found_message: ClassVar[str]
    duplicate_message: ClassVar[str]
    in_use_message: ClassVar[str]
    # The movement column that points at this dictionary.
    used_by: ClassVar[InstrumentedAttribute]

    def __init__(self, repo: BaseRepository[ModelType]):
        self.repo = repo

    def _order_by(self) -> list:
        return [self.repo.model.name]

    async def _validate(self, data: dict[str, Any], current: ModelType | None) -> None:
        """Extra checks for a subclass; ``current`` is None on create."""

    async def list(self, active: bool | None = None) -> list[ModelType]:
        params = {} if active is None else {"is_active": active}
        return await self.repo.get_all(order_by=self._order_by(), **params)

    async def get(self, row_uuid: UUID) -> ModelType:
        row = await self.repo.get_one(uuid=row_uuid)
        if row is None:
            raise ObjectNotFoundException(self.not_found_message)
        return row

    async def _check_name(self, data: dict[str, Any], current: ModelType | None):
        if "name" not in data:
            return
        name = (data["name"] or "").strip()
        if not name:
            raise BadRequestException("Nazwa jest wymagana")
        data["name"] = name
        if current is not None and name == current.name:
            return
        if await self.repo.get_one(name=name):
            raise ObjectAlreadyExistsException(self.duplicate_message)

    async def create(self, data: dict[str, Any]) -> ModelType:
        await self._check_name(data, None)
        await self._validate(data, None)
        return await self.repo.create_one(data)

    async def update(self, row_uuid: UUID, data: dict[str, Any]) -> ModelType:
        current = await self.get(row_uuid)
        await self._check_name(data, current)
        await self._validate(data, current)
        if not data:
            return current
        return await self.repo.update_one(row_uuid, data)

    async def delete(self, row_uuid: UUID) -> None:
        await self.get(row_uuid)
        # Read through the class: a column attribute is a descriptor, and
        # self.used_by would try to read it from this (unmapped) service.
        used_by = type(self).used_by
        in_use = await self.repo.session.execute(
            select(exists().where(used_by == row_uuid))
        )
        if in_use.scalar_one():
            raise ObjectAlreadyExistsException(self.in_use_message)
        await self.repo.delete_one(row_uuid)
