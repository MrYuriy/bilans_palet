from uuid import UUID

from fastapi import APIRouter

from app.dependencies import CurrentUserDep, MasterdataAdmin, SessionDep
from app.schemas.area import AreaCreate, AreaOut, AreaUpdate
from app.schemas.common import ActionResult
from app.services.area_service import AreaService

# Everyone signed in may read (to pick an area); only the admin changes them.
router = APIRouter(prefix="/areas", tags=["Areas"])


@router.get("", response_model=list[AreaOut])
async def list_areas(
    session: SessionDep, _: CurrentUserDep, active: bool | None = None
):
    return await AreaService(session).list(active)


@router.get("/{area_uuid}", response_model=AreaOut)
async def get_area(area_uuid: UUID, session: SessionDep, _: CurrentUserDep):
    return await AreaService(session).get(area_uuid)


@router.post("", response_model=AreaOut)
async def create_area(payload: AreaCreate, session: SessionDep, _: MasterdataAdmin):
    row = await AreaService(session).create(payload.model_dump())
    await session.commit()
    return row


@router.put("/{area_uuid}", response_model=AreaOut)
async def update_area(
    area_uuid: UUID, payload: AreaUpdate, session: SessionDep, _: MasterdataAdmin
):
    row = await AreaService(session).update(
        area_uuid, payload.model_dump(exclude_unset=True)
    )
    await session.commit()
    return row


@router.delete("/{area_uuid}", response_model=ActionResult)
async def delete_area(area_uuid: UUID, session: SessionDep, _: MasterdataAdmin):
    await AreaService(session).delete(area_uuid)
    await session.commit()
    return ActionResult()
