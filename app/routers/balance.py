from datetime import date

from fastapi import APIRouter, Response

from app.dependencies import CurrentUserDep, SessionDep
from app.schemas.balance import CurrentBalanceOut, DailyBalanceOut
from app.services import export_service
from app.services.balance_service import BalanceService

# Read-only; everyone signed in sees the whole stock.
router = APIRouter(prefix="/balances", tags=["Balances"])


@router.get("/current", response_model=CurrentBalanceOut)
async def current_balance(session: SessionDep, _: CurrentUserDep):
    return await BalanceService(session).current()


@router.get("/daily", response_model=DailyBalanceOut)
async def daily_balance(
    session: SessionDep, _: CurrentUserDep, day: date | None = None
):
    return await BalanceService(session).daily(day)


@router.get("/daily.xlsx")
async def daily_balance_xlsx(
    session: SessionDep, _: CurrentUserDep, day: date | None = None
):
    """The same day as /daily, as an XLSX file (the D-1 report for LM)."""
    data = await BalanceService(session).daily(day)
    return Response(
        content=export_service.daily_balance_xlsx(data),
        media_type=export_service.XLSX_MEDIA_TYPE,
        headers={
            "Content-Disposition": f'attachment; filename="bilans_{data.day}.xlsx"'
        },
    )
