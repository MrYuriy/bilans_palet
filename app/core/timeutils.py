from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.core.config import settings


def local_now() -> datetime:
    """Current time in the configured timezone, as a naive datetime.

    Used for created_at/updated_at so timestamps are stored in local wall-clock
    time regardless of the DB server / connection-pooler timezone.
    """
    return datetime.now(ZoneInfo(settings.app.TIMEZONE)).replace(tzinfo=None)


def business_date(moment: datetime, day_cutoff: time) -> date:
    """The warehouse day a moment belongs to.

    A warehouse day runs from ``day_cutoff`` to the same hour the next day, so
    with a 06:00 cut-off 03:00 on the 4th still belongs to the 3rd.
    """
    return (moment - timedelta(hours=day_cutoff.hour, minutes=day_cutoff.minute)).date()
