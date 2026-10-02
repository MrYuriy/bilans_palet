from app.models.pallet_type import PalletType
from app.repositories.pallet_type_repo import PalletTypeRepository
from app.services.dictionary_service import DictionaryService


class PalletTypeService(DictionaryService[PalletType]):
    not_found_message = "Nie znaleziono typu palety"
    duplicate_message = "Typ palety o tej nazwie już istnieje"

    def __init__(self, session):
        super().__init__(PalletTypeRepository(session))
