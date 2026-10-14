"""Drop areas table

Revision ID: 00023
Revises: 00022
Create Date: 2026-10-15 09:23:00.000000

"""

import importlib
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "00023"
down_revision: str | None = "00022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _original(name: str):
    """An earlier migration module; its upgrade() recreates what this one drops."""
    return importlib.import_module(f"app.database.alembic.versions.{name}")


def upgrade() -> None:
    # Replaced by carrier groups and types; nothing refers to it any more.
    op.drop_table("areas")


def downgrade() -> None:
    _original("00003_create_areas_table").upgrade()
