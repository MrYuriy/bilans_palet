"""Insert the settings row

Revision ID: 00026
Revises: 00025
Create Date: 2026-10-15 09:26:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "00026"
down_revision: str | None = "00025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Movements and day closing lock this row, so it must always exist.
    op.execute(
        "INSERT INTO system_settings (id, day_cutoff) VALUES (1, '00:00') "
        "ON CONFLICT (id) DO NOTHING"
    )


def downgrade() -> None:
    # The row may hold the admin's settings; it stays.
    pass
