from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class AuditLogOut(BaseModel):
    uuid: UUID
    created_at: datetime
    user_uuid: UUID | None
    username: str
    action: str
    action_label: str
    entity: str
    entity_label: str
    entity_uuid: UUID
    entity_name: str
    old_data: dict[str, Any] | None
    new_data: dict[str, Any] | None
