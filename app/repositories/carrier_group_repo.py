from app.models.carrier_group import CarrierGroup
from app.repositories.base import BaseRepository


class CarrierGroupRepository(BaseRepository[CarrierGroup]):
    def __init__(self, session):
        super().__init__(session, CarrierGroup)
