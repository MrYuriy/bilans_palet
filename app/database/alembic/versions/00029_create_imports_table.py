"""Create imports table

Revision ID: 00029
Revises: 00028
Create Date: 2026-10-15 11:01:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "00029"
down_revision: str | None = "00028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "imports",
        sa.Column("source", sa.String(length=30), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=True),
        sa.Column("user_uuid", sa.UUID(), nullable=False),
        sa.Column("summary", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
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
        sa.ForeignKeyConstraint(["user_uuid"], ["users.uuid"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("uuid"),
    )
    for column in ("created_at", "source", "user_uuid", "uuid"):
        op.create_index(op.f(f"ix_imports_{column}"), "imports", [column], unique=False)


def downgrade() -> None:
    op.drop_table("imports")
