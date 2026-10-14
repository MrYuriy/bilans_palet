"""Create holidays table

Revision ID: 00027
Revises: 00026
Create Date: 2026-10-15 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "00027"
down_revision: str | None = "00026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "holidays",
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column(
            "uuid",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True
        ),
        sa.PrimaryKeyConstraint("uuid"),
    )
    op.create_index(
        op.f("ix_holidays_created_at"), "holidays", ["created_at"], unique=False
    )
    op.create_index(op.f("ix_holidays_day"), "holidays", ["day"], unique=True)
    op.create_index(op.f("ix_holidays_uuid"), "holidays", ["uuid"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_holidays_uuid"), table_name="holidays")
    op.drop_index(op.f("ix_holidays_day"), table_name="holidays")
    op.drop_index(op.f("ix_holidays_created_at"), table_name="holidays")
    op.drop_table("holidays")
