from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, File, Form, Query, UploadFile

from app.core.timeutils import local_now
from app.dependencies import CurrentUserDep, SaldoPaletClientDep, SessionDep
from app.models.movement import MovementType
from app.schemas.data_import import ImportOut, TransplanerPreviewOut
from app.services.saldo_palet_import_service import SaldoPaletImportService
from app.services.transplaner_import_service import (
    MAX_FILE_BYTES,
    TransplanerImportService,
)

# Imports book movements; who may run them is checked by the service against
# the operations they book.
router = APIRouter(prefix="/imports", tags=["Imports"])

Upload = Annotated[
    UploadFile, File(description="Raport rozliczeniowy nośników (.xlsx)")
]


async def _content(file: UploadFile) -> bytes:
    # One byte more than allowed is enough to tell the file is too big.
    return await file.read(MAX_FILE_BYTES + 1)


@router.post("/transplaner/preview", response_model=TransplanerPreviewOut)
async def preview_transplaner(file: Upload, session: SessionDep, user: CurrentUserDep):
    """What booking the file would change, without booking anything."""
    return await TransplanerImportService(session).preview(user, await _content(file))


@router.post("/transplaner", response_model=ImportOut)
async def book_transplaner(
    file: Upload,
    session: SessionDep,
    user: CurrentUserDep,
    types: Annotated[list[MovementType], Form(alias="type")],
):
    """Book the chosen operations of the file (only what changed since the
    earlier uploads), dated today."""
    result = await TransplanerImportService(session).book(
        user, await _content(file), file.filename, types
    )
    await session.commit()
    return result


@router.get("/transplaner", response_model=list[ImportOut])
async def list_transplaner_imports(
    session: SessionDep,
    _: CurrentUserDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
):
    return await TransplanerImportService(session).recent(limit)


@router.post("/saldo-palet", response_model=ImportOut)
async def import_saldo_palet(
    session: SessionDep,
    user: CurrentUserDep,
    client: SaldoPaletClientDep,
    day: date | None = None,
):
    """Import a day from Saldo Palet now (by default yesterday); the morning
    import does this by itself. A day imported again books only what changed."""
    service = SaldoPaletImportService(session, client)
    service.check_allowed(user)
    result = await service.import_day(
        user, day or local_now().date() - timedelta(days=1)
    )
    await session.commit()
    return result


@router.get("/saldo-palet", response_model=list[ImportOut])
async def list_saldo_palet_imports(
    session: SessionDep,
    _: CurrentUserDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
):
    # The client is not needed to read the history.
    return await SaldoPaletImportService(session, None).recent(limit)
