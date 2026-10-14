from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response

from app.dependencies import SessionDep, require_permission
from app.models.audit_log import AuditLog
from app.models.user import User
from app.repositories.audit_log_repo import AuditLogRepository
from app.schemas.audit import AuditLogOut
from app.services.audit_service import ACTION_LABELS, ENTITY_LABELS

# Read-only: the log is written by the services, never through the API.
router = APIRouter(prefix="/audit", tags=["Audit"])

AuditReader = Annotated[User, Depends(require_permission("audit"))]

# The entities the log knows, taken from the labels so a new one is added once.
AuditEntity = Literal[tuple(ENTITY_LABELS)]


def _out(entry: AuditLog) -> AuditLogOut:
    return AuditLogOut(
        uuid=entry.uuid,
        created_at=entry.created_at,
        user_uuid=entry.user_uuid,
        username=entry.username,
        action=entry.action,
        action_label=ACTION_LABELS.get(entry.action, entry.action),
        entity=entry.entity,
        entity_label=ENTITY_LABELS.get(entry.entity, entry.entity),
        entity_uuid=entry.entity_uuid,
        entity_name=entry.entity_name,
        old_data=entry.old_data,
        new_data=entry.new_data,
    )


@router.get("", response_model=list[AuditLogOut])
async def list_audit_log(
    response: Response,
    session: SessionDep,
    _: AuditReader,
    entity: AuditEntity | None = None,
    entity_uuid: UUID | None = None,
    user_uuid: UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    rows, total = await AuditLogRepository(session).search(
        entity, entity_uuid, user_uuid, date_from, date_to, limit, offset
    )
    response.headers["X-Total-Count"] = str(total)
    return [_out(r) for r in rows]
