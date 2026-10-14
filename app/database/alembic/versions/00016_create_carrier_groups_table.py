"""Create carrier groups table

Revision ID: 00016
Revises: 00015
Create Date: 2026-10-14 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "00016"
down_revision: str | None = "00015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "carrier_groups",
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column(
            "is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
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
        sa.UniqueConstraint("name"),
    )
    op.create_index(
        op.f("ix_carrier_groups_created_at"),
        "carrier_groups",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_carrier_groups_uuid"), "carrier_groups", ["uuid"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_carrier_groups_uuid"), table_name="carrier_groups")
    op.drop_index(op.f("ix_carrier_groups_created_at"), table_name="carrier_groups")
    op.drop_table("carrier_groups")
