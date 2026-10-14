"""Drop pallet types table

Revision ID: 00024
Revises: 00023
Create Date: 2026-10-15 09:24:00.000000

"""

import importlib
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "00024"
down_revision: str | None = "00023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _original(name: str):
    """An earlier migration module; its upgrade() recreates what this one drops."""
    return importlib.import_module(f"app.database.alembic.versions.{name}")


def upgrade() -> None:
    # Replaced by carrier groups and types; nothing refers to it any more.
    op.drop_table("pallet_types")


def downgrade() -> None:
    _original("00004_create_pallet_types_table").upgrade()
