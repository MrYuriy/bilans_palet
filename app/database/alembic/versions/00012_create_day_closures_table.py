"""Create day closures table

Revision ID: 00012
Revises: 00011
Create Date: 2026-10-03 02:54:11.761817

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "00012"
down_revision: str | None = "00011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "day_closures",
        sa.Column("business_date", sa.Date(), nullable=False),
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
        sa.PrimaryKeyConstraint("uuid"),
    )
    op.create_index(
        op.f("ix_day_closures_business_date"),
        "day_closures",
        ["business_date"],
        unique=True,
    )
    op.create_index(
        op.f("ix_day_closures_created_at"), "day_closures", ["created_at"], unique=False
    )
    op.create_index(
        op.f("ix_day_closures_uuid"), "day_closures", ["uuid"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_day_closures_uuid"), table_name="day_closures")
    op.drop_index(op.f("ix_day_closures_created_at"), table_name="day_closures")
    op.drop_index(op.f("ix_day_closures_business_date"), table_name="day_closures")
    op.drop_table("day_closures")
