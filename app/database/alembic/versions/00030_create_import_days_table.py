"""Create import days table

Revision ID: 00030
Revises: 00029
Create Date: 2026-10-15 11:02:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "00030"
down_revision: str | None = "00029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "import_days",
        sa.Column("source", sa.String(length=30), nullable=False),
        sa.Column("carrier_type_uuid", sa.UUID(), nullable=False),
        sa.Column("movement_type", sa.String(length=30), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["carrier_type_uuid"], ["carrier_types.uuid"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("uuid"),
        sa.UniqueConstraint(
            "source",
            "carrier_type_uuid",
            "movement_type",
            "day",
            name="uq_import_days_source_type_kind_day",
        ),
    )
    for column in ("carrier_type_uuid", "created_at", "day", "uuid"):
        op.create_index(
            op.f(f"ix_import_days_{column}"), "import_days", [column], unique=False
        )


def downgrade() -> None:
    op.drop_table("import_days")
