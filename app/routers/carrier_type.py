from uuid import UUID

from fastapi import APIRouter

from app.dependencies import CurrentUserDep, MasterdataAdmin, SessionDep
from app.schemas.carrier import CarrierTypeCreate, CarrierTypeOut, CarrierTypeUpdate
from app.schemas.common import ActionResult
from app.services.carrier_type_service import CarrierTypeService

# Everyone signed in may read; only the admin changes them.
router = APIRouter(prefix="/carrier-types", tags=["Carrier types"])


@router.get("", response_model=list[CarrierTypeOut])
async def list_carrier_types(
    session: SessionDep, _: CurrentUserDep, active: bool | None = None
):
    return await CarrierTypeService(session).list(active)


@router.get("/{type_uuid}", response_model=CarrierTypeOut)
async def get_carrier_type(type_uuid: UUID, session: SessionDep, _: CurrentUserDep):
    return await CarrierTypeService(session).get(type_uuid)


@router.post("", response_model=CarrierTypeOut)
async def create_carrier_type(
    payload: CarrierTypeCreate, session: SessionDep, admin: MasterdataAdmin
):
    service = CarrierTypeService(session)
    row = await service.create(admin, payload.model_dump())
    await session.commit()
    return await service.get(row.uuid)


@router.put("/{type_uuid}", response_model=CarrierTypeOut)
async def update_carrier_type(
    type_uuid: UUID,
    payload: CarrierTypeUpdate,
    session: SessionDep,
    admin: MasterdataAdmin,
):
    service = CarrierTypeService(session)
    await service.update(admin, type_uuid, payload.model_dump(exclude_unset=True))
    await session.commit()
    return await service.get(type_uuid)


@router.delete("/{type_uuid}", response_model=ActionResult)
async def delete_carrier_type(
    type_uuid: UUID, session: SessionDep, admin: MasterdataAdmin
):
    await CarrierTypeService(session).delete(admin, type_uuid)
    await session.commit()
    return ActionResult()
