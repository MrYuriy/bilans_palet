from datetime import date

from sqlalchemy import select

from app.models.holiday import Holiday
from app.repositories.base import BaseRepository


class HolidayRepository(BaseRepository[Holiday]):
    def __init__(self, session):
        super().__init__(session, Holiday)

    async def in_year(self, year: int) -> list[Holiday]:
        query = (
            select(Holiday)
            .where(Holiday.day >= date(year, 1, 1), Holiday.day <= date(year, 12, 31))
            .order_by(Holiday.day)
        )
        return list((await self.session.execute(query)).scalars().all())

    async def days(self, first: date, last: date) -> set[date]:
        query = select(Holiday.day).where(Holiday.day >= first, Holiday.day <= last)
        return set((await self.session.execute(query)).scalars().all())
