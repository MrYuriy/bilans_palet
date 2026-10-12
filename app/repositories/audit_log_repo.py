from datetime import date, datetime, time, timedelta
from uuid import UUID

from sqlalchemy import func, select

from app.models.audit_log import AuditLog
from app.repositories.base import BaseRepository


class AuditLogRepository(BaseRepository[AuditLog]):
    def __init__(self, session):
        super().__init__(session, AuditLog)

    async def search(
        self,
        entity: str | None = None,
        entity_uuid: UUID | None = None,
        user_uuid: UUID | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[AuditLog], int]:
        """Newest first."""
        conditions = []
        if entity is not None:
            conditions.append(AuditLog.entity == entity)
        if entity_uuid is not None:
            conditions.append(AuditLog.entity_uuid == entity_uuid)
        if user_uuid is not None:
            conditions.append(AuditLog.user_uuid == user_uuid)
        if date_from is not None:
            conditions.append(
                AuditLog.created_at >= datetime.combine(date_from, time())
            )
        if date_to is not None:
            next_day = datetime.combine(date_to + timedelta(days=1), time())
            conditions.append(AuditLog.created_at < next_day)

        query = (
            select(AuditLog)
            .where(*conditions)
            .order_by(AuditLog.seq.desc())
            .limit(limit)
            .offset(offset)
        )
        total = select(func.count()).select_from(AuditLog).where(*conditions)

        rows = (await self.session.execute(query)).scalars().all()
        return list(rows), (await self.session.execute(total)).scalar_one()
