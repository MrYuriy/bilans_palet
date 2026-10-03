from app.models.inventory import InventoryLine
from app.models.movement import MovementLine
from app.models.pallet_type import PalletType
from app.repositories.pallet_type_repo import PalletTypeRepository
from app.services.dictionary_service import DictionaryService


class PalletTypeService(DictionaryService[PalletType]):
    not_found_message = "Nie znaleziono typu palety"
    duplicate_message = "Typ palety o tej nazwie już istnieje"
    in_use_message = "Typ palety występuje w ruchach. Możesz go dezaktywować."
    used_by = (MovementLine.pallet_type_uuid, InventoryLine.pallet_type_uuid)
    entity = "pallet_type"

    def __init__(self, session):
        super().__init__(PalletTypeRepository(session))
