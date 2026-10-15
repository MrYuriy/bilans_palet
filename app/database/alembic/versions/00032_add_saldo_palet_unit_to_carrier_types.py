"""Add saldo palet unit to carrier types

Revision ID: 00032
Revises: 00031
Create Date: 2026-10-15 13:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "00032"
down_revision: str | None = "00031"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Saldo Palet units counted by MONOLIT, by the carrier type they go to.
UNITS = {
    "EURO": "EUR",
    "EURO uszkodzone": "euro uszkodzone",
    "Jednorazowe": "jednorazowe",
}


def upgrade() -> None:
    op.add_column(
        "carrier_types",
        sa.Column("saldo_palet_unit", sa.String(length=100), nullable=True),
    )
    op.create_unique_constraint(
        "uq_carrier_types_saldo_palet_unit", "carrier_types", ["saldo_palet_unit"]
    )
    for name, unit in UNITS.items():
        op.execute(
            sa.text(
                "UPDATE carrier_types SET saldo_palet_unit = :unit WHERE name = :name"
            ).bindparams(unit=unit, name=name)
        )


def downgrade() -> None:
    op.drop_constraint(
        "uq_carrier_types_saldo_palet_unit", "carrier_types", type_="unique"
    )
    op.drop_column("carrier_types", "saldo_palet_unit")
