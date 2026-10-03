from datetime import date
from uuid import UUID

from fastapi import APIRouter

from app.dependencies import CurrentUserDep, SessionDep
from app.schemas.balance import CurrentBalanceOut, DailyBalanceOut
from app.services.balance_service import BalanceService

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
