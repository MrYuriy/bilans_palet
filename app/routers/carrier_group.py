from uuid import UUID

from fastapi import APIRouter

from app.dependencies import CurrentUserDep, MasterdataAdmin, SessionDep
from app.schemas.carrier import CarrierGroupCreate, CarrierGroupOut, CarrierGroupUpdate
from app.schemas.common import ActionResult
from app.services.carrier_group_service import CarrierGroupService

# Everyone signed in may read; only the admin changes them.
router = APIRouter(prefix="/carrier-groups", tags=["Carrier groups"])


@router.get("", response_model=list[CarrierGroupOut])
async def list_carrier_groups(
    session: SessionDep, _: CurrentUserDep, active: bool | None = None
):
    return await CarrierGroupService(session).list(active)


@router.get("/{group_uuid}", response_model=CarrierGroupOut)
async def get_carrier_group(group_uuid: UUID, session: SessionDep, _: CurrentUserDep):
    return await CarrierGroupService(session).get(group_uuid)


@router.post("", response_model=CarrierGroupOut)
async def create_carrier_group(
    payload: CarrierGroupCreate, session: SessionDep, admin: MasterdataAdmin
):
    row = await CarrierGroupService(session).create(admin, payload.model_dump())
    await session.commit()
    return row


@router.put("/{group_uuid}", response_model=CarrierGroupOut)
async def update_carrier_group(
    group_uuid: UUID,
    payload: CarrierGroupUpdate,
    session: SessionDep,
    admin: MasterdataAdmin,
):
    row = await CarrierGroupService(session).update(
        admin, group_uuid, payload.model_dump(exclude_unset=True)
    )
    await session.commit()
    return row


@router.delete("/{group_uuid}", response_model=ActionResult)
async def delete_carrier_group(
    group_uuid: UUID, session: SessionDep, admin: MasterdataAdmin
):
    await CarrierGroupService(session).delete(admin, group_uuid)
    await session.commit()
    return ActionResult()
