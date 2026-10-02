"""Create movement lines table

Revision ID: 00008
Revises: 00007
Create Date: 2026-10-03 01:39:22.743630

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "00008"
down_revision: str | None = "00007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "movement_lines",
        sa.Column("movement_uuid", sa.UUID(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("pallet_type_uuid", sa.UUID(), nullable=False),
        sa.Column("quality_uuid", sa.UUID(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
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
        sa.CheckConstraint("quantity <> 0", name="ck_movement_lines_quantity_nonzero"),
        sa.ForeignKeyConstraint(
            ["movement_uuid"], ["movements.uuid"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["pallet_type_uuid"], ["pallet_types.uuid"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["quality_uuid"], ["qualities.uuid"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("uuid"),
    )
    op.create_index(
        op.f("ix_movement_lines_created_at"),
        "movement_lines",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_movement_lines_movement_uuid"),
        "movement_lines",
        ["movement_uuid"],
        unique=False,
    )
    op.create_index(
        op.f("ix_movement_lines_pallet_type_uuid"),
        "movement_lines",
        ["pallet_type_uuid"],
        unique=False,
    )
    op.create_index(
        op.f("ix_movement_lines_quality_uuid"),
        "movement_lines",
        ["quality_uuid"],
        unique=False,
    )
    op.create_index(
        op.f("ix_movement_lines_uuid"), "movement_lines", ["uuid"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_movement_lines_uuid"), table_name="movement_lines")
    op.drop_index(op.f("ix_movement_lines_quality_uuid"), table_name="movement_lines")
    op.drop_index(
        op.f("ix_movement_lines_pallet_type_uuid"), table_name="movement_lines"
    )
    op.drop_index(op.f("ix_movement_lines_movement_uuid"), table_name="movement_lines")
    op.drop_index(op.f("ix_movement_lines_created_at"), table_name="movement_lines")
    op.drop_table("movement_lines")
