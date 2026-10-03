from typing import Annotated

from fastapi import APIRouter, Depends

from app.dependencies import CurrentUserDep, SessionDep, require_permission
from app.models.user import User
from app.schemas.setting import SettingsOut, SettingsUpdate
from app.services.settings_service import SettingsService

# Everyone signed in may read them (the UI shows the warehouse day);
# only the admin changes them.
router = APIRouter(prefix="/settings", tags=["Settings"])

SettingsAdmin = Annotated[User, Depends(require_permission("settings"))]


async def _out(service: SettingsService) -> SettingsOut:
    return SettingsOut(
        day_cutoff=(await service.day_cutoff()).strftime("%H:%M"),
        current_day=await service.current_day(),
    )


@router.get("", response_model=SettingsOut)
async def get_settings(session: SessionDep, _: CurrentUserDep):
    return await _out(SettingsService(session))


@router.put("", response_model=SettingsOut)
async def update_settings(
    payload: SettingsUpdate, session: SessionDep, admin: SettingsAdmin
):
    service = SettingsService(session)
    await service.update(admin, payload.day_cutoff)
    await session.commit()
    return await _out(service)
