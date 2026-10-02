from uuid import UUID

from pydantic import BaseModel


class ActionResult(BaseModel):
    """Generic acknowledgement returned by write operations without a body."""

    status: str = "ok"


class NamedRef(BaseModel):
    """A dictionary row (area, pallet type, quality) shown inside another object."""

    uuid: UUID
    name: str

    model_config = {"from_attributes": True}
