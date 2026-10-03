from app.models.area import Area
from app.models.movement import Movement
from app.repositories.area_repo import AreaRepository
from app.services.dictionary_service import DictionaryService


class AreaService(DictionaryService[Area]):
    not_found_message = "Nie znaleziono obszaru"
    duplicate_message = "Obszar o tej nazwie już istnieje"
    in_use_message = "Obszar ma zarejestrowane ruchy. Możesz go dezaktywować."
    used_by = (Movement.area_uuid,)
    entity = "area"

    def __init__(self, session):
        super().__init__(AreaRepository(session))
