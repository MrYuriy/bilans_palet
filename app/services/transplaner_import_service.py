"""Booking the Transplaner file: shipments to the stores, returns, and UKR apart.

The file covers a whole month and is uploaded again and again; numbers of past
days change (returns appear once the warehouse confirms them). Each upload books
only the difference against what earlier uploads booked, as one movement per
operation, dated the day of the upload: closed days never change.
"""

import calendar
from dataclasses import dataclass
from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.exc import BadRequestException
from app.models.carrier_type import CarrierType
from app.models.data_import import DataImport, ImportDay
from app.models.movement import Movement, MovementLine, MovementType
from app.models.user import User
from app.repositories.import_repo import ImportRepository
from app.schemas.common import NamedRef
from app.schemas.data_import import (
    DayChange,
    ImportKindOut,
    ImportOut,
    TransplanerPreviewOut,
)
from app.services.day_close_service import ensure_day_open
from app.services.movement_service import MovementService
from app.services.operation_catalog import OPERATIONS
from app.services.settings_service import SettingsService
from app.services.transplaner_file import (
    RETURNS,
    SHIPMENTS,
    TransplanerFile,
    read_transplaner,
)

SOURCE = "transplaner"
MAX_FILE_BYTES = 5 * 1024 * 1024

# Booked apart from the stores (the manager counts UKR separately).
UKR_RECIPIENTS = frozenset({"Leroy Merlin Ukraine LLC"})

# (sheet, UKR row?) -> operation
KINDS = {
    (SHIPMENTS, False): MovementType.STORE_SHIPMENT,
    (SHIPMENTS, True): MovementType.UKR_SHIPMENT,
    (RETURNS, False): MovementType.STORE_RETURN,
    (RETURNS, True): MovementType.UKR_RETURN,
}


@dataclass
class _Kind:
    type: MovementType
    in_file: dict[date, int]  # day -> quantity in the file
    booked: dict[date, ImportDay]  # day -> booked so far

    def days(self) -> list[DayChange]:
        """The days whose number differs from what was booked."""
        changes = []
        for day in sorted(set(self.in_file) | set(self.booked)):
            now = self.in_file.get(day, 0)
            before = self.booked[day].quantity if day in self.booked else 0
            if now != before:
                changes.append(DayChange(day=day, in_file=now, booked=before))
        return changes

    @property
    def change(self) -> int:
        """Signed change of the stock: more shipped -> minus, more returned -> plus."""
        sign = OPERATIONS[self.type].sign
        return sign * sum(d.in_file - d.booked for d in self.days())

    def out(self) -> ImportKindOut:
        return ImportKindOut(
            type=self.type,
            label=OPERATIONS[self.type].label,
            in_file=sum(self.in_file.values()),
            booked=sum(r.quantity for r in self.booked.values()),
            change=self.change,
            days=self.days(),
        )


@dataclass
class _Plan:
    file: TransplanerFile
    carrier_type: CarrierType
    kinds: dict[MovementType, _Kind]
    warnings: list[str]


class TransplanerImportService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = ImportRepository(session)
        self.movements = MovementService(session)

    def _check_allowed(self, user: User, kinds) -> None:
        for kind in kinds:
            self.movements.check_allowed(user, OPERATIONS[kind])

    async def _plan(self, content: bytes) -> _Plan:
        if len(content) > MAX_FILE_BYTES:
            raise BadRequestException("Plik jest za duży (maks. 5 MB)")
        file = read_transplaner(content)

        carrier_type = (
            await self.session.execute(
                select(CarrierType).where(CarrierType.transplaner_name == file.carrier)
            )
        ).scalar_one_or_none()
        if carrier_type is None:
            raise BadRequestException(
                f"Nośnik „{file.carrier}” z pliku nie jest przypisany do typu nośnika"
                " (Ustawienia → Typy nośników → nazwa w Transplanerze)"
            )
        if not carrier_type.is_active:
            raise BadRequestException(
                f"Typ nośnika „{carrier_type.name}” jest nieaktywny"
            )

        today = await SettingsService(self.session).current_day()
        current_month = today.replace(day=1)
        if file.month > current_month:
            raise BadRequestException(
                f"Plik dotyczy miesiąca {file.month:%m.%Y}, który jeszcze się nie zaczął"
            )
        warnings = []
        if file.month < current_month:
            warnings.append(f"Plik dotyczy poprzedniego miesiąca ({file.month:%m.%Y})")

        in_file: dict[MovementType, dict[date, int]] = {}
        for sheet in file.sheets.values():
            for kind in (KINDS[sheet.kind, False], KINDS[sheet.kind, True]):
                in_file.setdefault(kind, {})
            for recipient, days in sheet.rows.items():
                kind = KINDS[sheet.kind, recipient in UKR_RECIPIENTS]
                for day, quantity in days.items():
                    in_file[kind][day] = in_file[kind].get(day, 0) + quantity
                    if day > today:
                        warnings.append(
                            f"Zakładka „{sheet.title}”: {recipient} ma ilość"
                            f" w przyszłym dniu {day:%d.%m.%Y}"
                        )

        month_end = file.month.replace(
            day=calendar.monthrange(file.month.year, file.month.month)[1]
        )
        kinds = {}
        for kind, days in in_file.items():
            booked = await self.repo.booked_days(
                SOURCE, carrier_type.uuid, kind, file.month, month_end
            )
            kinds[kind] = _Kind(kind, days, booked)
        return _Plan(file, carrier_type, kinds, warnings)

    async def preview(self, user: User, content: bytes) -> TransplanerPreviewOut:
        plan = await self._plan(content)
        self._check_allowed(user, plan.kinds)
        days_with_data = [
            day
            for sheet in plan.file.sheets.values()
            for days in sheet.rows.values()
            for day in days
        ]
        return TransplanerPreviewOut(
            carrier=plan.file.carrier,
            carrier_type=NamedRef.model_validate(plan.carrier_type),
            month=plan.file.month,
            recipients=len({r for s in plan.file.sheets.values() for r in s.rows}),
            last_day=max(days_with_data, default=None),
            kinds=[k.out() for k in plan.kinds.values()],
            warnings=plan.warnings,
        )

    async def book(
        self,
        user: User,
        content: bytes,
        file_name: str | None,
        kinds: list[MovementType],
    ) -> ImportOut:
        if not kinds:
            raise BadRequestException("Wybierz co najmniej jedną operację")
        plan = await self._plan(content)
        unknown = [k for k in kinds if k not in plan.kinds]
        if unknown:
            raise BadRequestException(
                f"„{OPERATIONS[unknown[0]].label}” nie występuje w tym pliku"
            )
        self._check_allowed(user, kinds)

        # Held until commit, like any movement: a day being closed waits.
        await self.movements.lock.shared()
        today = await SettingsService(self.session).current_day()
        await ensure_day_open(self.session, today)

        summary = {
            "carrier": plan.file.carrier,
            "month": plan.file.month.strftime("%Y-%m"),
            "kinds": {},
        }
        data_import = DataImport(
            source=SOURCE,
            file_name=(file_name or "")[:255] or None,
            user_uuid=user.uuid,
        )
        self.session.add(data_import)
        await self.session.flush()

        for kind in kinds:
            item = plan.kinds[kind]
            days = item.days()
            change = item.change
            if change:
                self.session.add(
                    Movement(
                        type=kind,
                        user_uuid=user.uuid,
                        operation_date=today,
                        comment=self._comment(plan.file.month, kind, days),
                        import_uuid=data_import.uuid,
                        lines=[
                            MovementLine(
                                position=1,
                                carrier_type_uuid=plan.carrier_type.uuid,
                                quantity=change,
                            )
                        ],
                    )
                )
            for changed in days:
                row = item.booked.get(changed.day)
                if row is None:
                    self.session.add(
                        ImportDay(
                            source=SOURCE,
                            carrier_type_uuid=plan.carrier_type.uuid,
                            movement_type=kind,
                            day=changed.day,
                            quantity=changed.in_file,
                        )
                    )
                else:
                    row.quantity = changed.in_file
            summary["kinds"][kind.value] = {
                "label": OPERATIONS[kind].label,
                "change": change,
                "days": len(days),
            }

        data_import.summary = summary
        await self.session.flush()
        # Read it back with its author; see MovementService.create for why expunge.
        self.session.expunge(data_import)
        return await self.get(data_import.uuid)

    @staticmethod
    def _comment(month: date, kind: MovementType, days: list[DayChange]) -> str:
        sign = OPERATIONS[kind].sign
        parts = [f"{d.day:%d.%m} {sign * (d.in_file - d.booked):+d}" for d in days[:10]]
        if len(days) > 10:
            parts.append(f"… (+{len(days) - 10} dni)")
        return f"Transplaner {month:%m.%Y} — według dni: " + ", ".join(parts)

    async def get(self, import_uuid: UUID) -> ImportOut:
        row = (
            await self.session.execute(
                select(DataImport)
                .options(joinedload(DataImport.user))
                .where(DataImport.uuid == import_uuid)
            )
        ).scalar_one()
        return ImportOut.model_validate(row)

    async def recent(self, limit: int = 20) -> list[ImportOut]:
        return [
            ImportOut.model_validate(r) for r in await self.repo.recent(SOURCE, limit)
        ]
