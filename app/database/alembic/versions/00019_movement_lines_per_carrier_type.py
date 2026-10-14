"""Movement lines per carrier type

Revision ID: 00019
Revises: 00018
Create Date: 2026-10-15 09:19:00.000000

"""

import importlib
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "00019"
down_revision: str | None = "00018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _original(name: str):
    """An earlier migration module; its upgrade() recreates what this one drops."""
    return importlib.import_module(f"app.database.alembic.versions.{name}")


def upgrade() -> None:
    # Empty since 00018: recreated with a carrier type instead of a pallet
    # type and quality.
    op.drop_table("movement_lines")
    op.create_table(
        "movement_lines",
        sa.Column("movement_uuid", sa.UUID(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("carrier_type_uuid", sa.UUID(), nullable=False),
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
            ["carrier_type_uuid"], ["carrier_types.uuid"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["movement_uuid"], ["movements.uuid"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("uuid"),
    )
    for column in ("carrier_type_uuid", "created_at", "movement_uuid", "uuid"):
        op.create_index(
            op.f(f"ix_movement_lines_{column}"),
            "movement_lines",
            [column],
            unique=False,
        )


def downgrade() -> None:
    op.drop_table("movement_lines")
    _original("00008_create_movement_lines_table").upgrade()
