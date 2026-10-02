from datetime import datetime
from zoneinfo import ZoneInfo

from app.core.config import settings


def local_now() -> datetime:
    """Current time in the configured timezone, as a naive datetime.

    Used for created_at/updated_at so timestamps are stored in local wall-clock
    time regardless of the DB server / connection-pooler timezone.
    """
    return datetime.now(ZoneInfo(settings.app.TIMEZONE)).replace(tzinfo=None)
