from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response

from app.dependencies import CurrentUserDep, SessionDep, require_permission
from app.models.movement import MovementType
from app.models.user import User
from app.schemas.movement import MovementCreate, MovementOut, MovementTypeOut
from app.services.movement_service import MovementService

# Movements are only created and read: a saved movement is never edited or
# deleted, a mistake is fixed with a correction.
router = APIRouter(prefix="/movements", tags=["Movements"])

MovementsWriter = Annotated[User, Depends(require_permission("movements"))]


@router.get("/types", response_model=list[MovementTypeOut])
async def list_movement_types(_: CurrentUserDep):
    return MovementService.types()


@router.post("", response_model=MovementOut)
async def create_movement(
    payload: MovementCreate, session: SessionDep, current_user: MovementsWriter
):
    movement = await MovementService(session).create(current_user, payload)
    await session.commit()
    return movement


@router.get("", response_model=list[MovementOut])
async def list_movements(
    response: Response,
    session: SessionDep,
    current_user: CurrentUserDep,
    area_uuid: UUID | None = None,
    type: MovementType | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    rows, total = await MovementService(session).search(
        current_user, area_uuid, type, date_from, date_to, limit, offset
    )
    response.headers["X-Total-Count"] = str(total)
    return rows


@router.get("/{movement_uuid}", response_model=MovementOut)
async def get_movement(
    movement_uuid: UUID, session: SessionDep, current_user: CurrentUserDep
):
    return await MovementService(session).get(current_user, movement_uuid)
