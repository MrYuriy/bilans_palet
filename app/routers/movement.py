from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Response

from app.core.exc import BadRequestException
from app.dependencies import CurrentUserDep, SessionDep
from app.models.movement import MovementType
from app.schemas.movement import MovementCreate, MovementOut, MovementTypeOut
from app.services import export_service
from app.services.movement_service import MovementService
from app.services.settings_service import SettingsService

# Movements are only created and read: a saved movement is never edited or
# deleted, a mistake is fixed with a correction. Who may enter which operation
# is checked by the service (operation_catalog + PermissionService).
router = APIRouter(prefix="/movements", tags=["Movements"])


@router.get("/types", response_model=list[MovementTypeOut])
async def list_movement_types(session: SessionDep, current_user: CurrentUserDep):
    return MovementService(session).types(current_user)


@router.post("", response_model=MovementOut)
async def create_movement(
    payload: MovementCreate, session: SessionDep, current_user: CurrentUserDep
):
    movement = await MovementService(session).create(current_user, payload)
    await session.commit()
    return movement


@router.get("", response_model=list[MovementOut])
async def list_movements(
    response: Response,
    session: SessionDep,
    _: CurrentUserDep,
    type: MovementType | None = None,
    carrier_type_uuid: UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    rows, total = await MovementService(session).search(
        type, carrier_type_uuid, date_from, date_to, limit, offset
    )
    response.headers["X-Total-Count"] = str(total)
    return rows


# More would make a file nobody opens; narrow the filters instead.
EXPORT_LIMIT = 100_000


# Declared before /{movement_uuid}, which would otherwise catch this path.
@router.get("/export.xlsx")
async def export_movements(
    session: SessionDep,
    _: CurrentUserDep,
    type: MovementType | None = None,
    carrier_type_uuid: UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
):
    """The register with the same filters as the list, as an XLSX file."""
    rows, total = await MovementService(session).search(
        type, carrier_type_uuid, date_from, date_to, EXPORT_LIMIT, 0
    )
    if total > EXPORT_LIMIT:
        raise BadRequestException(
            "Za dużo operacji do eksportu — zawęź filtry (maks. 100 000)"
        )
    today = (await SettingsService(session).current_day()).isoformat()
    return Response(
        content=export_service.movements_xlsx(rows),
        media_type=export_service.XLSX_MEDIA_TYPE,
        headers={
            "Content-Disposition": f'attachment; filename="rejestr_operacji_{today}.xlsx"'
        },
    )


@router.get("/{movement_uuid}", response_model=MovementOut)
async def get_movement(movement_uuid: UUID, session: SessionDep, _: CurrentUserDep):
    return await MovementService(session).get(movement_uuid)
