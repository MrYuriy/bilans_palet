from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Response

from app.dependencies import CurrentUserDep, SessionDep
from app.schemas.balance import CurrentBalanceOut, DailyBalanceOut, HistoryOut
from app.services import export_service
from app.services.balance_service import BalanceService

# Read-only; everyone signed in sees the whole stock.
router = APIRouter(prefix="/balances", tags=["Balances"])

# The carrier types to show (repeat the parameter); left out: the types counted
# in reports.
TypesQuery = Annotated[list[UUID] | None, Query(alias="type")]


@router.get("/current", response_model=CurrentBalanceOut)
async def current_balance(
    session: SessionDep, _: CurrentUserDep, types: TypesQuery = None
):
    return await BalanceService(session).current(types)


@router.get("/daily", response_model=DailyBalanceOut)
async def daily_balance(
    session: SessionDep,
    _: CurrentUserDep,
    day: date | None = None,
    types: TypesQuery = None,
):
    return await BalanceService(session).daily(day, types)


@router.get("/daily.xlsx")
async def daily_balance_xlsx(
    session: SessionDep,
    _: CurrentUserDep,
    day: date | None = None,
    types: TypesQuery = None,
):
    """The same day as /daily, as an XLSX file (the D-1 report for LM)."""
    data = await BalanceService(session).daily(day, types)
    return Response(
        content=export_service.daily_balance_xlsx(data),
        media_type=export_service.XLSX_MEDIA_TYPE,
        headers={
            "Content-Disposition": f'attachment; filename="bilans_{data.day}.xlsx"'
        },
    )


@router.get("/history", response_model=HistoryOut)
async def balance_history(
    session: SessionDep,
    _: CurrentUserDep,
    days: Annotated[int, Query(ge=1, le=366)] = 30,
    types: TypesQuery = None,
):
    """The stock day by day for the chart (7 days, a month, three months)."""
    return await BalanceService(session).history(days, types)
