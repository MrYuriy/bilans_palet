"""Default day cut-off at midnight

Revision ID: 00015
Revises: 00014
Create Date: 2026-10-14 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "00015"
down_revision: str | None = "00014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Only the column default: a cut-off the admin already saved stays as it is.
    op.alter_column("system_settings", "day_cutoff", server_default=sa.text("'00:00'"))


def downgrade() -> None:
    op.alter_column("system_settings", "day_cutoff", server_default=sa.text("'06:00'"))
