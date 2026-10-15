"""Add import to movements

Revision ID: 00031
Revises: 00030
Create Date: 2026-10-15 11:03:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "00031"
down_revision: str | None = "00030"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("movements", sa.Column("import_uuid", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "fk_movements_import_uuid",
        "movements",
        "imports",
        ["import_uuid"],
        ["uuid"],
        ondelete="RESTRICT",
    )
    op.create_index(
        op.f("ix_movements_import_uuid"), "movements", ["import_uuid"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_movements_import_uuid"), table_name="movements")
    op.drop_constraint("fk_movements_import_uuid", "movements", type_="foreignkey")
    op.drop_column("movements", "import_uuid")
