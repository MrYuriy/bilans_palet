from typing import Any
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Base


class BaseRepository[ModelType: Base]:
    def __init__(self, session: AsyncSession, model: type[ModelType]):
        self.session = session
        self.model = model

    # -------------------
    # CREATE
    # -------------------
    async def create_one(self, data: dict) -> ModelType:
        row = self.model(**data)
        self.session.add(row)
        await self.session.flush()
        return row

    async def create_many(self, data: list[dict]) -> None:
        rows = [self.model(**item) for item in data]
        self.session.add_all(rows)
        await self.session.flush()

    # -------------------
    # UPSERT
    # -------------------
    async def upsert_one(
        self,
        data: dict,
        conflict_columns: list[str],
        update_columns: list[str],
    ):
        query = pg_insert(self.model).values(data)

        query = query.on_conflict_do_update(
            index_elements=conflict_columns,
            set_={col: getattr(query.excluded, col) for col in update_columns},
        )

        await self.session.execute(query)
        await self.session.flush()

    # -------------------
    # READ
    # -------------------
    async def get_one(
        self,
        filters: list | None = None,
        options: list | None = None,
        **params,
    ) -> ModelType | None:

        query = select(self.model).filter_by(**params)

        if filters:
            for condition in filters:
                query = query.filter(condition)

        if options:
            query = query.options(*options)

        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_many(
        self,
        page: int = 1,
        limit: int = 10,
        filters: list | None = None,
        options: list | None = None,
        order_by: list | None = None,
        **params,
    ) -> tuple[list[ModelType], int]:

        offset = (page - 1) * limit

        query = select(self.model).filter_by(**params).offset(offset).limit(limit)

        total_query = select(func.count()).select_from(self.model).filter_by(**params)

        if filters:
            for condition in filters:
                query = query.filter(condition)
                total_query = total_query.filter(condition)

        if order_by:
            query = query.order_by(*order_by)

        if options:
            query = query.options(*options)

        result = await self.session.execute(query)
        total = await self.session.execute(total_query)

        return result.scalars().all(), total.scalar()

    async def search_by_name(
        self,
        search: str = "",
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[ModelType], int]:
        """Paginated case-insensitive search on the model's ``name`` column.
        Returns (page_rows, total_matching). For named entities only."""
        name_col = self.model.name

        query = select(self.model)
        total_query = select(func.count()).select_from(self.model)

        if search:
            condition = name_col.ilike(f"%{search}%")
            query = query.where(condition)
            total_query = total_query.where(condition)

        query = query.order_by(name_col).limit(limit).offset(offset)

        rows = (await self.session.execute(query)).scalars().all()
        total = (await self.session.execute(total_query)).scalar()
        return rows, total

    async def list_all_by_ids(self, uuids: list[UUID]) -> list[ModelType]:
        if not uuids:
            return []

        query = select(self.model).where(self.model.uuid.in_(uuids))
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_all(
        self,
        filters: list | None = None,
        order_by: list | None = None,
        options: list | None = None,
        **params,
    ) -> list[ModelType]:

        query = select(self.model).filter_by(**params)

        if filters:
            for condition in filters:
                query = query.filter(condition)

        if order_by:
            query = query.order_by(*order_by)

        if options:
            query = query.options(*options)

        result = await self.session.execute(query)
        return result.scalars().all()

    # -------------------
    # UPDATE
    # -------------------
    async def update_one(self, model_uuid: UUID, data: dict) -> ModelType:
        query = select(self.model).where(self.model.uuid == model_uuid)

        result = await self.session.execute(query)
        obj = result.scalar_one()

        for key, value in data.items():
            setattr(obj, key, value)

        # updated_at is handled by the column's onupdate=local_now (naive local time).
        await self.session.flush()
        return obj

    # -------------------
    # DELETE
    # -------------------
    async def delete_one(self, model_uuid: UUID) -> ModelType:
        query = (
            delete(self.model)
            .where(self.model.uuid == model_uuid)
            .returning(self.model)
        )

        result = await self.session.execute(query)
        await self.session.flush()

        return result.scalar_one()

    async def delete_many(
        self,
        filters: list | None = None,
        **params: Any,
    ) -> None:

        query = delete(self.model).filter_by(**params)

        if filters:
            for condition in filters:
                query = query.filter(condition)

        await self.session.execute(query)
        await self.session.flush()
