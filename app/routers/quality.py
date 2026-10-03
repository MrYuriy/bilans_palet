from uuid import UUID

from fastapi import APIRouter

from app.dependencies import CurrentUserDep, MasterdataAdmin, SessionDep
from app.schemas.common import ActionResult
from app.schemas.quality import QualityCreate, QualityOut, QualityUpdate
from app.services.quality_service import QualityService

# Everyone signed in may read; only the admin changes them.
router = APIRouter(prefix="/qualities", tags=["Qualities"])


@router.get("", response_model=list[QualityOut])
async def list_qualities(
    session: SessionDep, _: CurrentUserDep, active: bool | None = None
):
    return await QualityService(session).list(active)


@router.get("/{quality_uuid}", response_model=QualityOut)
async def get_quality(quality_uuid: UUID, session: SessionDep, _: CurrentUserDep):
    return await QualityService(session).get(quality_uuid)


@router.post("", response_model=QualityOut)
async def create_quality(
    payload: QualityCreate, session: SessionDep, admin: MasterdataAdmin
):
    row = await QualityService(session).create(admin, payload.model_dump())
    await session.commit()
    return row


@router.put("/{quality_uuid}", response_model=QualityOut)
async def update_quality(
    quality_uuid: UUID,
    payload: QualityUpdate,
    session: SessionDep,
    admin: MasterdataAdmin,
):
    row = await QualityService(session).update(
        admin, quality_uuid, payload.model_dump(exclude_unset=True)
    )
    await session.commit()
    return row


@router.delete("/{quality_uuid}", response_model=ActionResult)
async def delete_quality(
    quality_uuid: UUID, session: SessionDep, admin: MasterdataAdmin
):
    await QualityService(session).delete(admin, quality_uuid)
    await session.commit()
    return ActionResult()
