"""Remove areas from movements

Revision ID: 00018
Revises: 00017
Create Date: 2026-10-15 09:18:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "00018"
down_revision: str | None = "00017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # The stock is now kept per carrier type for the whole warehouse. Movements
    # recorded per area, pallet type and quality cannot be carried over, so the
    # stock history starts again (closed days included; the next close
    # rebuilds them).
    for table in (
        "daily_balances",
        "day_closures",
        "inventory_lines",
        "movement_lines",
        "movements",
    ):
        op.execute(f"DELETE FROM {table}")
    # Dropping the column drops its foreign key and index too.
    op.drop_column("movements", "area_uuid")


def downgrade() -> None:
    op.add_column("movements", sa.Column("area_uuid", sa.UUID(), nullable=True))
    op.create_foreign_key(
        None, "movements", "areas", ["area_uuid"], ["uuid"], ondelete="RESTRICT"
    )
    op.create_index(
        op.f("ix_movements_area_uuid"), "movements", ["area_uuid"], unique=False
    )
