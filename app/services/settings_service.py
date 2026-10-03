from datetime import date, time
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.timeutils import business_date, local_now
from app.models.setting import DEFAULT_DAY_CUTOFF, SystemSettings
from app.models.user import User
from app.services.audit_service import AuditService

# The settings row has no UUID of its own; the audit log needs one.
# uuid5(NAMESPACE_URL, "bilans-palet:system-settings"). Not an all-digit value:
# SQLite would read such a UUID back as a number.
SETTINGS_ENTITY_UUID = UUID("35aff6ae-68e7-5a23-bb6d-7cb7a3419c70")


def _hhmm(value: time) -> str:
    return value.strftime("%H:%M")


class SettingsService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.audit = AuditService(session)

    async def get(self) -> SystemSettings:
        """The settings row, or the defaults while the admin has not saved any."""
        row = await self.session.get(SystemSettings, 1)
        return row or SystemSettings(id=1, day_cutoff=DEFAULT_DAY_CUTOFF)

    async def day_cutoff(self) -> time:
        return (await self.get()).day_cutoff

    async def current_day(self) -> date:
        """The warehouse day it is now."""
        return business_date(local_now(), await self.day_cutoff())

    async def update(self, actor: User, day_cutoff: time) -> SystemSettings:
        row = await self.session.get(SystemSettings, 1)
        if row is None:
            row = SystemSettings(id=1, day_cutoff=DEFAULT_DAY_CUTOFF)
            self.session.add(row)

        before = {"day_cutoff": _hhmm(row.day_cutoff)}
        row.day_cutoff = day_cutoff.replace(second=0, microsecond=0)
        await self.session.flush()

        await self.audit.log_update(
            actor,
            "settings",
            SETTINGS_ENTITY_UUID,
            "Ustawienia",
            before,
            {"day_cutoff": _hhmm(row.day_cutoff)},
        )
        return row
