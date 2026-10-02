from uuid import UUID

from fastapi import APIRouter

from app.dependencies import CurrentUserDep, MasterdataAdmin, SessionDep
from app.schemas.common import ActionResult
from app.schemas.pallet_type import PalletTypeCreate, PalletTypeOut, PalletTypeUpdate
from app.services.pallet_type_service import PalletTypeService

# Everyone signed in may read; only the admin changes them.
router = APIRouter(prefix="/pallet-types", tags=["Pallet types"])


@router.get("", response_model=list[PalletTypeOut])
async def list_pallet_types(
    session: SessionDep, _: CurrentUserDep, active: bool | None = None
):
    return await PalletTypeService(session).list(active)


@router.get("/{type_uuid}", response_model=PalletTypeOut)
async def get_pallet_type(type_uuid: UUID, session: SessionDep, _: CurrentUserDep):
    return await PalletTypeService(session).get(type_uuid)


@router.post("", response_model=PalletTypeOut)
async def create_pallet_type(
    payload: PalletTypeCreate, session: SessionDep, _: MasterdataAdmin
):
    row = await PalletTypeService(session).create(payload.model_dump())
    await session.commit()
    return row


@router.put("/{type_uuid}", response_model=PalletTypeOut)
async def update_pallet_type(
    type_uuid: UUID, payload: PalletTypeUpdate, session: SessionDep, _: MasterdataAdmin
):
    row = await PalletTypeService(session).update(
        type_uuid, payload.model_dump(exclude_unset=True)
    )
    await session.commit()
    return row


@router.delete("/{type_uuid}", response_model=ActionResult)
async def delete_pallet_type(type_uuid: UUID, session: SessionDep, _: MasterdataAdmin):
    await PalletTypeService(session).delete(type_uuid)
    await session.commit()
    return ActionResult()
