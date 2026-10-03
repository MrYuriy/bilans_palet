from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from app.dependencies import SessionDep, require_permission
from app.models.user import User
from app.schemas.movement import InventoryCreate, MovementOut, SheetRowOut
from app.services.inventory_service import InventoryService

# Stock counts. A saved count is a movement (type INVENTORY): it is read
# through /movements like any other and never edited.
router = APIRouter(prefix="/inventories", tags=["Inventories"])

InventoryWriter = Annotated[User, Depends(require_permission("movements"))]


@router.get("/sheet", response_model=list[SheetRowOut])
async def count_sheet(
    session: SessionDep, current_user: InventoryWriter, area_uuid: UUID | None = None
):
    return await InventoryService(session).sheet(current_user, area_uuid)


@router.post("", response_model=MovementOut)
async def approve_count(
    payload: InventoryCreate, session: SessionDep, current_user: InventoryWriter
):
    movement = await InventoryService(session).create(current_user, payload)
    await session.commit()
    return movement
