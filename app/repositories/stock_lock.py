from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.setting import DEFAULT_DAY_CUTOFF, SystemSettings


class StockLock:
    """One lock for the whole stock, held on the settings row until commit.

    Movements take it shared: they run side by side, but a day cannot be closed
    while one is being written. Closing a day and approving a stock count take
    it exclusively: nothing else changes the stock meanwhile.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def _hold(self, *, exclusive: bool) -> None:
        if await self.session.get(SystemSettings, 1) is None:
            # Migration 00026 inserts the row; this covers a database made
            # without migrations (the tests).
            self.session.add(SystemSettings(id=1, day_cutoff=DEFAULT_DAY_CUTOFF))
            await self.session.flush()
        await self.session.execute(
            select(SystemSettings.id)
            .where(SystemSettings.id == 1)
            .with_for_update(read=not exclusive)
        )

    async def shared(self) -> None:
        await self._hold(exclusive=False)

    async def exclusive(self) -> None:
        await self._hold(exclusive=True)
