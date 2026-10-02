from pydantic import BaseModel


class ActionResult(BaseModel):
    """Generic acknowledgement returned by write operations without a body."""

    status: str = "ok"
