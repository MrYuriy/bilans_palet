from uuid import UUID

from fastapi import APIRouter

from app.core.exc import BadRequestException
from app.core.timeutils import local_now
from app.dependencies import SessionDep, SettingsAdmin
from app.models.reminder import Reminder
from app.schemas.common import ActionResult
from app.schemas.reminder import (
    ReminderCreate,
    ReminderOut,
    RemindersStatus,
    ReminderUpdate,
)
from app.services.holiday_service import HolidayService
from app.services.mailer import configured_mailer
from app.services.reminder_service import (
    CHECKS,
    ReminderService,
    describe,
    reminder_mail,
)

# The reminders are part of the configuration: admin only.
router = APIRouter(prefix="/reminders", tags=["Reminders"])


def _out(row: Reminder) -> ReminderOut:
    return ReminderOut(
        uuid=row.uuid,
        name=row.name,
        check=row.check,
        movement_type=row.movement_type,
        description=describe(row),
        deadline=row.deadline.strftime("%H:%M"),
        recipients=list(row.recipients or []),
        is_active=row.is_active,
        last_sent_on=row.last_sent_on,
    )


@router.get("/status", response_model=RemindersStatus)
async def reminders_status(session: SessionDep, _: SettingsAdmin):
    mailer = configured_mailer()
    return RemindersStatus(
        smtp_configured=mailer is not None,
        sender=mailer.sender if mailer else None,
        working_day_today=await HolidayService(session).is_working_day(
            local_now().date()
        ),
        checks=CHECKS,
    )


@router.get("", response_model=list[ReminderOut])
async def list_reminders(session: SessionDep, _: SettingsAdmin):
    return [_out(r) for r in await ReminderService(session).list()]


@router.post("", response_model=ReminderOut)
async def create_reminder(
    payload: ReminderCreate, session: SessionDep, admin: SettingsAdmin
):
    row = await ReminderService(session).create(admin, payload.model_dump())
    await session.commit()
    return _out(row)


@router.put("/{reminder_uuid}", response_model=ReminderOut)
async def update_reminder(
    reminder_uuid: UUID,
    payload: ReminderUpdate,
    session: SessionDep,
    admin: SettingsAdmin,
):
    row = await ReminderService(session).update(
        admin, reminder_uuid, payload.model_dump(exclude_unset=True)
    )
    await session.commit()
    return _out(row)


@router.delete("/{reminder_uuid}", response_model=ActionResult)
async def delete_reminder(
    reminder_uuid: UUID, session: SessionDep, admin: SettingsAdmin
):
    await ReminderService(session).delete(admin, reminder_uuid)
    await session.commit()
    return ActionResult()


@router.post("/{reminder_uuid}/test", response_model=ActionResult)
async def send_test_mail(reminder_uuid: UUID, session: SessionDep, _: SettingsAdmin):
    """Send the reminder's mail now, to check the addresses and the SMTP setup."""
    row = await ReminderService(session).get(reminder_uuid)
    mailer = configured_mailer()
    if mailer is None:
        raise BadRequestException("Wysyłka poczty nie jest skonfigurowana (SMTP)")
    if not row.recipients:
        raise BadRequestException("Dodaj co najmniej jednego odbiorcę")
    subject, body = reminder_mail(row, local_now().date())
    try:
        await mailer.send(list(row.recipients), "[TEST] " + subject, body)
    except OSError as error:
        raise BadRequestException(
            f"Nie udało się wysłać wiadomości ({type(error).__name__})"
        ) from error
    return ActionResult()
