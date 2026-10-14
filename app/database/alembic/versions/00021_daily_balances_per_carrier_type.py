"""Daily balances per carrier type

Revision ID: 00021
Revises: 00020
Create Date: 2026-10-15 09:21:00.000000

"""

import importlib
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "00021"
down_revision: str | None = "00020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _original(name: str):
    """An earlier migration module; its upgrade() recreates what this one drops."""
    return importlib.import_module(f"app.database.alembic.versions.{name}")


def upgrade() -> None:
    # Empty since 00018: recreated per carrier type (no area, pallet type, quality).
    op.drop_table("daily_balances")
    op.create_table(
        "daily_balances",
        sa.Column("business_date", sa.Date(), nullable=False),
        sa.Column("carrier_type_uuid", sa.UUID(), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["carrier_type_uuid"], ["carrier_types.uuid"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("uuid"),
        sa.UniqueConstraint(
            "business_date", "carrier_type_uuid", name="uq_daily_balances_day_type"
        ),
    )
    for column in ("business_date", "carrier_type_uuid", "created_at", "uuid"):
        op.create_index(
            op.f(f"ix_daily_balances_{column}"),
            "daily_balances",
            [column],
            unique=False,
        )


def downgrade() -> None:
    op.drop_table("daily_balances")
    _original("00013_create_daily_balances_table").upgrade()
