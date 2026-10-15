"""Create reminders table

Revision ID: 00033
Revises: 00032
Create Date: 2026-10-15 15:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "00033"
down_revision: str | None = "00032"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "reminders",
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("check", sa.String(length=30), nullable=False),
        sa.Column("movement_type", sa.String(length=30), nullable=True),
        sa.Column("deadline", sa.Time(), nullable=False),
        sa.Column(
            "recipients", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column(
            "is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
        sa.Column("last_run_on", sa.Date(), nullable=True),
        sa.Column("last_sent_on", sa.Date(), nullable=True),
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
        sa.UniqueConstraint("name"),
    )
    op.create_index(
        op.f("ix_reminders_created_at"), "reminders", ["created_at"], unique=False
    )
    op.create_index(op.f("ix_reminders_uuid"), "reminders", ["uuid"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_reminders_uuid"), table_name="reminders")
    op.drop_index(op.f("ix_reminders_created_at"), table_name="reminders")
    op.drop_table("reminders")
