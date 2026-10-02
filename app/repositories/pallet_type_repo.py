from app.models.pallet_type import PalletType
from app.repositories.base import BaseRepository


class PalletTypeRepository(BaseRepository[PalletType]):
    def __init__(self, session):
        super().__init__(session, PalletType)
