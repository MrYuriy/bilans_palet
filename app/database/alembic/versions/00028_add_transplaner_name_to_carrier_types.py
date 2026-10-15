"""Add transplaner name to carrier types

Revision ID: 00028
Revises: 00027
Create Date: 2026-10-15 11:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "00028"
down_revision: str | None = "00027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "carrier_types",
        sa.Column("transplaner_name", sa.String(length=100), nullable=True),
    )
    op.create_unique_constraint(
        "uq_carrier_types_transplaner_name", "carrier_types", ["transplaner_name"]
    )
    # The file holds EUR pallets; they are booked on the plain EURO type.
    op.execute(
        "UPDATE carrier_types SET transplaner_name = 'PAL EUR/ EPAL' WHERE name = 'EURO'"
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_carrier_types_transplaner_name", "carrier_types", type_="unique"
    )
    op.drop_column("carrier_types", "transplaner_name")
