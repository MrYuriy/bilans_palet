"""Create movements table

Revision ID: 00007
Revises: 00006
Create Date: 2026-10-03 01:39:22.743630

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "00007"
down_revision: str | None = "00006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "movements",
        # Movement type kept as text (see MovementType), so new types need no migration.
        sa.Column("type", sa.String(length=30), nullable=False),
        sa.Column("area_uuid", sa.UUID(), nullable=False),
        sa.Column("user_uuid", sa.UUID(), nullable=False),
        sa.Column("operation_date", sa.Date(), nullable=False),
        sa.Column("document_number", sa.String(length=100), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(["area_uuid"], ["areas.uuid"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_uuid"], ["users.uuid"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("uuid"),
    )
    op.create_index(
        op.f("ix_movements_area_uuid"), "movements", ["area_uuid"], unique=False
    )
    op.create_index(
        op.f("ix_movements_created_at"), "movements", ["created_at"], unique=False
    )
    op.create_index(
        op.f("ix_movements_operation_date"),
        "movements",
        ["operation_date"],
        unique=False,
    )
    op.create_index(op.f("ix_movements_type"), "movements", ["type"], unique=False)
    op.create_index(
        op.f("ix_movements_user_uuid"), "movements", ["user_uuid"], unique=False
    )
    op.create_index(op.f("ix_movements_uuid"), "movements", ["uuid"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_movements_uuid"), table_name="movements")
    op.drop_index(op.f("ix_movements_user_uuid"), table_name="movements")
    op.drop_index(op.f("ix_movements_type"), table_name="movements")
    op.drop_index(op.f("ix_movements_operation_date"), table_name="movements")
    op.drop_index(op.f("ix_movements_created_at"), table_name="movements")
    op.drop_index(op.f("ix_movements_area_uuid"), table_name="movements")
    op.drop_table("movements")
