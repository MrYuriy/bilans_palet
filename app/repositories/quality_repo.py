from app.models.quality import Quality
from app.repositories.base import BaseRepository


class QualityRepository(BaseRepository[Quality]):
    def __init__(self, session):
        super().__init__(session, Quality)
