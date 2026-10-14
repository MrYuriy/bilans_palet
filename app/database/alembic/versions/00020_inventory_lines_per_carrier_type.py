"""Inventory lines per carrier type

Revision ID: 00020
Revises: 00019
Create Date: 2026-10-15 09:20:00.000000

"""

import importlib
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "00020"
down_revision: str | None = "00019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _original(name: str):
    """An earlier migration module; its upgrade() recreates what this one drops."""
    return importlib.import_module(f"app.database.alembic.versions.{name}")


def upgrade() -> None:
    # Empty since 00018: recreated with a carrier type instead of a pallet
    # type and quality.
    op.drop_table("inventory_lines")
    op.create_table(
        "inventory_lines",
        sa.Column("movement_uuid", sa.UUID(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("carrier_type_uuid", sa.UUID(), nullable=False),
        sa.Column("system_quantity", sa.Integer(), nullable=False),
        sa.Column("counted_quantity", sa.Integer(), nullable=False),
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
        sa.CheckConstraint(
            "counted_quantity >= 0", name="ck_inventory_lines_counted_not_negative"
        ),
        sa.ForeignKeyConstraint(
            ["carrier_type_uuid"], ["carrier_types.uuid"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["movement_uuid"], ["movements.uuid"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("uuid"),
    )
    for column in ("carrier_type_uuid", "created_at", "movement_uuid", "uuid"):
        op.create_index(
            op.f(f"ix_inventory_lines_{column}"),
            "inventory_lines",
            [column],
            unique=False,
        )


def downgrade() -> None:
    op.drop_table("inventory_lines")
    _original("00010_create_inventory_lines_table").upgrade()
