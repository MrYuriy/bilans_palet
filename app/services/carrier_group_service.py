from app.models.carrier_group import CarrierGroup
from app.models.carrier_type import CarrierType
from app.repositories.carrier_group_repo import CarrierGroupRepository
from app.services.dictionary_service import DictionaryService


class CarrierGroupService(DictionaryService[CarrierGroup]):
    not_found_message = "Nie znaleziono grupy nośników"
    duplicate_message = "Grupa o tej nazwie już istnieje"
    in_use_message = "Grupa ma typy nośników. Możesz ją dezaktywować."
    used_by = (CarrierType.group_uuid,)
    entity = "carrier_group"

    def __init__(self, session):
        super().__init__(CarrierGroupRepository(session))
