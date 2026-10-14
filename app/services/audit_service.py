from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories.audit_log_repo import AuditLogRepository

# Codes stored in the log, with the Polish labels the UI shows.
ACTION_LABELS = {
    "create": "Utworzenie",
    "update": "Zmiana",
    "delete": "Usunięcie",
}
ENTITY_LABELS = {
    "user": "Użytkownik",
    "area": "Obszar",
    "pallet_type": "Typ palety",
    "quality": "Jakość",
    "carrier_group": "Grupa nośników",
    "carrier_type": "Typ nośnika",
    "settings": "Ustawienia",
}


def changes(
    before: dict[str, Any], after: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Only the fields that differ, as (old values, new values)."""
    keys = [k for k in after if before.get(k) != after.get(k)]
    return {k: before.get(k) for k in keys}, {k: after[k] for k in keys}


class AuditService:
    """Writes the audit log in the same transaction as the change it records."""

    def __init__(self, session: AsyncSession):
        self.repo = AuditLogRepository(session)

    async def log(
        self,
        actor: User,
        action: str,
        entity: str,
        entity_uuid: UUID,
        entity_name: str,
        old_data: dict[str, Any] | None = None,
        new_data: dict[str, Any] | None = None,
    ) -> None:
        await self.repo.create_one(
            {
                "user_uuid": actor.uuid,
                "username": actor.username,
                "action": action,
                "entity": entity,
                "entity_uuid": entity_uuid,
                "entity_name": entity_name,
                "old_data": old_data,
                "new_data": new_data,
            }
        )

    async def log_update(
        self,
        actor: User,
        entity: str,
        entity_uuid: UUID,
        entity_name: str,
        before: dict[str, Any],
        after: dict[str, Any],
    ) -> None:
        """Log only what changed; nothing when nothing changed."""
        old, new = changes(before, after)
        if new:
            await self.log(actor, "update", entity, entity_uuid, entity_name, old, new)
