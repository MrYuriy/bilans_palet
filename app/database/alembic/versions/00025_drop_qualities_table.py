"""Drop qualities table

Revision ID: 00025
Revises: 00024
Create Date: 2026-10-15 09:25:00.000000

"""

import importlib
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "00025"
down_revision: str | None = "00024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _original(name: str):
    """An earlier migration module; its upgrade() recreates what this one drops."""
    return importlib.import_module(f"app.database.alembic.versions.{name}")


def upgrade() -> None:
    # Replaced by carrier groups and types; nothing refers to it any more.
    op.drop_table("qualities")


def downgrade() -> None:
    _original("00005_create_qualities_table").upgrade()
