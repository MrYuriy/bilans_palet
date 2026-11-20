"""Most a line of the limited operations may carry

Revision ID: 00034
Revises: 00033
Create Date: 2026-11-20 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "00034"
down_revision: str | None = "00033"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "system_settings",
        sa.Column(
            "max_line_quantity",
            sa.Integer(),
            server_default=sa.text("700"),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_system_settings_max_line", "system_settings", "max_line_quantity > 0"
    )


def downgrade() -> None:
    op.drop_constraint("ck_system_settings_max_line", "system_settings", type_="check")
    op.drop_column("system_settings", "max_line_quantity")
