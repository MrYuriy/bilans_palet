"""Create daily balances table

Revision ID: 00013
Revises: 00012
Create Date: 2026-10-03 02:54:11.761817

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "00013"
down_revision: str | None = "00012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "daily_balances",
        sa.Column("business_date", sa.Date(), nullable=False),
        sa.Column("area_uuid", sa.UUID(), nullable=False),
        sa.Column("pallet_type_uuid", sa.UUID(), nullable=False),
        sa.Column("quality_uuid", sa.UUID(), nullable=False),
        sa.Column("opening", sa.Integer(), nullable=False),
        sa.Column("receipts", sa.Integer(), nullable=False),
        sa.Column("shipments", sa.Integer(), nullable=False),
        sa.Column("corrections", sa.Integer(), nullable=False),
        sa.Column("reclassifications", sa.Integer(), nullable=False),
        sa.Column("closing", sa.Integer(), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["pallet_type_uuid"], ["pallet_types.uuid"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["quality_uuid"], ["qualities.uuid"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("uuid"),
        sa.UniqueConstraint(
            "business_date",
            "area_uuid",
            "pallet_type_uuid",
            "quality_uuid",
            name="uq_daily_balances_day_area_type_quality",
        ),
    )
    op.create_index(
        op.f("ix_daily_balances_area_uuid"),
        "daily_balances",
        ["area_uuid"],
        unique=False,
    )
    op.create_index(
        op.f("ix_daily_balances_business_date"),
        "daily_balances",
        ["business_date"],
        unique=False,
    )
    op.create_index(
        op.f("ix_daily_balances_created_at"),
        "daily_balances",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_daily_balances_uuid"), "daily_balances", ["uuid"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_daily_balances_uuid"), table_name="daily_balances")
    op.drop_index(op.f("ix_daily_balances_created_at"), table_name="daily_balances")
    op.drop_index(op.f("ix_daily_balances_business_date"), table_name="daily_balances")
    op.drop_index(op.f("ix_daily_balances_area_uuid"), table_name="daily_balances")
    op.drop_table("daily_balances")
