from datetime import date, timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exc import ObjectAlreadyExistsException, ObjectNotFoundException
from app.models.holiday import Holiday
from app.models.user import User
from app.repositories.holiday_repo import HolidayRepository
from app.services.audit_service import AuditService


def easter_sunday(year: int) -> date:
    """Gregorian Easter Sunday (the anonymous Gregorian algorithm)."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    g = (8 * b + 13) // 25
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    m = (32 + 2 * e + 2 * i - h - k) % 7
    n = (a + 11 * h + 19 * m) // 433
    month = (h + m - 7 * n + 90) // 25
    day = (h + m - 7 * n + 33 * month + 19) % 32
    return date(year, month, day)


def polish_public_holidays(year: int) -> list[tuple[date, str]]:
    """The statutory days off in Poland in the given year, in date order."""
    easter = easter_sunday(year)
    days = [
        (date(year, 1, 1), "Nowy Rok"),
        (date(year, 1, 6), "Święto Trzech Króli"),
        (easter, "Wielkanoc"),
        (easter + timedelta(days=1), "Poniedziałek Wielkanocny"),
        (date(year, 5, 1), "Święto Pracy"),
        (date(year, 5, 3), "Święto Konstytucji 3 Maja"),
        (easter + timedelta(days=49), "Zielone Świątki"),
        (easter + timedelta(days=60), "Boże Ciało"),
        (date(year, 8, 15), "Wniebowzięcie Najświętszej Maryi Panny"),
        (date(year, 11, 1), "Wszystkich Świętych"),
        (date(year, 11, 11), "Narodowe Święto Niepodległości"),
        (date(year, 12, 25), "Boże Narodzenie (pierwszy dzień)"),
        (date(year, 12, 26), "Boże Narodzenie (drugi dzień)"),
    ]
    if year >= 2025:  # a day off since 2025
        days.append((date(year, 12, 24), "Wigilia Bożego Narodzenia"))
    return sorted(days)


def _audit_view(holiday: Holiday) -> dict:
    return {"day": holiday.day.isoformat(), "name": holiday.name}


class HolidayService:
    """Days off. Weekends are days off without a row; these are the others."""

    def __init__(self, session: AsyncSession):
        self.repo = HolidayRepository(session)
        self.audit = AuditService(session)

    async def in_year(self, year: int) -> list[Holiday]:
        return await self.repo.in_year(year)

    async def create(self, actor: User, day: date, name: str) -> Holiday:
        name = name.strip()
        if await self.repo.get_one(day=day):
            raise ObjectAlreadyExistsException(
                f"Dzień {day.strftime('%d.%m.%Y')} jest już na liście"
            )
        holiday = await self.repo.create_one(
            {"day": day, "name": name or "Dzień wolny"}
        )
        await self.audit.log(
            actor,
            "create",
            "holiday",
            holiday.uuid,
            holiday.name,
            new_data=_audit_view(holiday),
        )
        return holiday

    async def delete(self, actor: User, holiday_uuid: UUID) -> None:
        holiday = await self.repo.get_one(uuid=holiday_uuid)
        if holiday is None:
            raise ObjectNotFoundException("Nie znaleziono dnia wolnego")
        await self.audit.log(
            actor,
            "delete",
            "holiday",
            holiday.uuid,
            holiday.name,
            old_data=_audit_view(holiday),
        )
        await self.repo.delete_one(holiday_uuid)

    async def add_public(self, actor: User | None, year: int) -> list[Holiday]:
        """Add the Polish public holidays of a year that are not on the list yet.
        Without an actor (the seed) nothing goes to the audit log."""
        taken = await self.repo.days(date(year, 1, 1), date(year, 12, 31))
        added = []
        for day, name in polish_public_holidays(year):
            if day in taken:
                continue
            holiday = await self.repo.create_one({"day": day, "name": name})
            if actor is not None:
                await self.audit.log(
                    actor,
                    "create",
                    "holiday",
                    holiday.uuid,
                    holiday.name,
                    new_data=_audit_view(holiday),
                )
            added.append(holiday)
        return added

    async def is_working_day(self, day: date) -> bool:
        """Monday to Friday and not on the list."""
        return day.weekday() < 5 and await self.repo.get_one(day=day) is None
