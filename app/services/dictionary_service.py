from typing import Any, ClassVar
from uuid import UUID

from sqlalchemy import exists, select
from sqlalchemy.orm import InstrumentedAttribute

from app.core.exc import (
    BadRequestException,
    ObjectAlreadyExistsException,
    ObjectNotFoundException,
)
from app.models.user import User
from app.repositories.base import BaseRepository
from app.services.audit_service import AuditService

_NOT_AUDITED = {"uuid", "created_at", "updated_at"}


class DictionaryService[ModelType]:
    """Shared CRUD for the admin-managed dictionaries (carrier groups and types, ...).

    Every dictionary row has a unique ``name`` and an ``is_active`` flag.
    Subclasses set the Polish messages, the list order and where movements
    refer to the row (a row in use is deactivated, never deleted).
    """

    not_found_message: ClassVar[str]
    duplicate_message: ClassVar[str]
    in_use_message: ClassVar[str]
    # Columns of movements / count sheets that point at this dictionary.
    used_by: ClassVar[tuple[InstrumentedAttribute, ...]]
    # Entity code in the audit log.
    entity: ClassVar[str]

    def __init__(self, repo: BaseRepository[ModelType]):
        self.repo = repo
        self.audit = AuditService(repo.session)

    def _order_by(self) -> list:
        return [self.repo.model.name]

    async def _validate(self, data: dict[str, Any], current: ModelType | None) -> None:
        """Extra checks for a subclass; ``current`` is None on create."""

    async def _audit_view(self, row: ModelType) -> dict[str, Any]:
        """What the audit log keeps of a row (JSON-safe values only)."""
        return row.to_dict(exclude=_NOT_AUDITED)

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

    async def create(self, actor: User, data: dict[str, Any]) -> ModelType:
        await self._check_name(data, None)
        await self._validate(data, None)
        row = await self.repo.create_one(data)
        await self.audit.log(
            actor,
            "create",
            self.entity,
            row.uuid,
            row.name,
            new_data=await self._audit_view(row),
        )
        return row

    async def update(
        self, actor: User, row_uuid: UUID, data: dict[str, Any]
    ) -> ModelType:
        current = await self.get(row_uuid)
        await self._check_name(data, current)
        await self._validate(data, current)
        if not data:
            return current
        before = await self._audit_view(current)
        row = await self.repo.update_one(row_uuid, data)
        await self.audit.log_update(
            actor, self.entity, row.uuid, row.name, before, await self._audit_view(row)
        )
        return row

    async def delete(self, actor: User, row_uuid: UUID) -> None:
        row = await self.get(row_uuid)
        for column in self.used_by:
            in_use = await self.repo.session.execute(
                select(exists().where(column == row_uuid))
            )
            if in_use.scalar_one():
                raise ObjectAlreadyExistsException(self.in_use_message)
        await self.audit.log(
            actor,
            "delete",
            self.entity,
            row.uuid,
            row.name,
            old_data=await self._audit_view(row),
        )
        await self.repo.delete_one(row_uuid)
