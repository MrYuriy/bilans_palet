from typing import Any

from app.core.exc import ObjectAlreadyExistsException
from app.models.inventory import InventoryLine
from app.models.movement import MovementLine
from app.models.quality import Quality
from app.repositories.quality_repo import QualityRepository
from app.services.dictionary_service import DictionaryService


class QualityService(DictionaryService[Quality]):
    not_found_message = "Nie znaleziono jakości"
    duplicate_message = "Jakość o tej nazwie już istnieje"
    in_use_message = "Jakość występuje w ruchach. Możesz ją dezaktywować."
    used_by = (MovementLine.quality_uuid, InventoryLine.quality_uuid)
    entity = "quality"

    def __init__(self, session):
        super().__init__(QualityRepository(session))

    def _order_by(self) -> list:
        return [Quality.sort_order]

    async def _validate(self, data: dict[str, Any], current: Quality | None) -> None:
        order = data.get("sort_order")
        if order is None or (current is not None and order == current.sort_order):
            return
        if await self.repo.get_one(sort_order=order):
            raise ObjectAlreadyExistsException("Jakość o tej kolejności już istnieje")
