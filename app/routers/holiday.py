from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Path

from app.dependencies import CurrentUserDep, SessionDep, SettingsAdmin
from app.schemas.common import ActionResult
from app.schemas.holiday import HolidayCreate, HolidayOut
from app.services.holiday_service import HolidayService

# Days off: everyone signed in may read them; only the admin changes them.
router = APIRouter(prefix="/holidays", tags=["Holidays"])

Year = Annotated[int, Path(ge=2000, le=2100)]


@router.get("/{year}", response_model=list[HolidayOut])
async def list_holidays(year: Year, session: SessionDep, _: CurrentUserDep):
    return await HolidayService(session).in_year(year)


@router.post("", response_model=HolidayOut)
async def add_holiday(
    payload: HolidayCreate, session: SessionDep, admin: SettingsAdmin
):
    holiday = await HolidayService(session).create(admin, payload.day, payload.name)
    await session.commit()
    return holiday


@router.post("/public/{year}", response_model=list[HolidayOut])
async def add_public_holidays(year: Year, session: SessionDep, admin: SettingsAdmin):
    """Add the Polish public holidays of the year that are not on the list yet."""
    added = await HolidayService(session).add_public(admin, year)
    await session.commit()
    return added


@router.delete("/{holiday_uuid}", response_model=ActionResult)
async def delete_holiday(holiday_uuid: UUID, session: SessionDep, admin: SettingsAdmin):
    await HolidayService(session).delete(admin, holiday_uuid)
    await session.commit()
    return ActionResult()
