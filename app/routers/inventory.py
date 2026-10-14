from fastapi import APIRouter

from app.dependencies import CurrentUserDep, SessionDep
from app.schemas.movement import InventoryCreate, MovementOut, SheetRowOut
from app.services.inventory_service import InventoryService

# Stock counts. A saved count is a movement (type INVENTORY): it is read
# through /movements like any other and never edited. Who may count is checked
# by the service.
router = APIRouter(prefix="/inventories", tags=["Inventories"])


@router.get("/sheet", response_model=list[SheetRowOut])
async def count_sheet(session: SessionDep, current_user: CurrentUserDep):
    return await InventoryService(session).sheet(current_user)


@router.post("", response_model=MovementOut)
async def approve_count(
    payload: InventoryCreate, session: SessionDep, current_user: CurrentUserDep
):
    movement = await InventoryService(session).create(current_user, payload)
    await session.commit()
    return movement
