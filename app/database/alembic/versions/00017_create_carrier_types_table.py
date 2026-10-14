"""Create carrier types table

Revision ID: 00017
Revises: 00016
Create Date: 2026-10-14 12:01:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "00017"
down_revision: str | None = "00016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "carrier_types",
        sa.Column("group_uuid", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column(
            "sort_order", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column(
            "count_in_reports",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
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
        sa.ForeignKeyConstraint(
            ["group_uuid"], ["carrier_groups.uuid"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("uuid"),
        sa.UniqueConstraint("name"),
    )
    op.create_index(
        op.f("ix_carrier_types_created_at"),
        "carrier_types",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_carrier_types_group_uuid"),
        "carrier_types",
        ["group_uuid"],
        unique=False,
    )
    op.create_index(
        op.f("ix_carrier_types_uuid"), "carrier_types", ["uuid"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_carrier_types_uuid"), table_name="carrier_types")
    op.drop_index(op.f("ix_carrier_types_group_uuid"), table_name="carrier_types")
    op.drop_index(op.f("ix_carrier_types_created_at"), table_name="carrier_types")
    op.drop_table("carrier_types")
