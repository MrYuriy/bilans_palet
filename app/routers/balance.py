from datetime import date
from uuid import UUID

from fastapi import APIRouter, Response

from app.dependencies import CurrentUserDep, SessionDep
from app.schemas.balance import CurrentBalanceOut, DailyBalanceOut
from app.services import export_service
from app.services.balance_service import BalanceService
from app.services.permission_service import PermissionService

# Read-only. Operators see their areas; the admin and viewers see all.
router = APIRouter(prefix="/balances", tags=["Balances"])


@router.get("/current", response_model=CurrentBalanceOut)
async def current_balance(
    session: SessionDep, current_user: CurrentUserDep, area_uuid: UUID | None = None
):
    return await BalanceService(session).current(current_user, area_uuid)


@router.get("/daily", response_model=DailyBalanceOut)
async def daily_balance(
    session: SessionDep,
    current_user: CurrentUserDep,
    day: date | None = None,
    area_uuid: UUID | None = None,
):
    return await BalanceService(session).daily(current_user, day, area_uuid)


@router.get("/daily.xlsx")
async def daily_balance_xlsx(
    session: SessionDep,
    current_user: CurrentUserDep,
    day: date | None = None,
    area_uuid: UUID | None = None,
):
    """The same day as /daily, as an XLSX file (the D-1 report for LM)."""
    data = await BalanceService(session).daily(current_user, day, area_uuid)
    if area_uuid is not None or not PermissionService().reads_every_area(
        current_user.role.name
    ):
        area_label = ", ".join(a.area.name for a in data.areas) or "—"
    else:
        area_label = "wszystkie"
    return Response(
        content=export_service.daily_balance_xlsx(data, area_label),
        media_type=export_service.XLSX_MEDIA_TYPE,
        headers={
            "Content-Disposition": f'attachment; filename="bilans_{data.day}.xlsx"'
        },
    )
