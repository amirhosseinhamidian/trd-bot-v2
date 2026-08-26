"""Persist the last successful monitoring collector cycle.

Revision ID: 20260826_0006
Revises: 20260826_0005
Create Date: 2026-08-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260826_0006"
down_revision: str | None = "20260826_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "monitoring_runtime_state",
        sa.Column("state_key", sa.String(length=100), nullable=False),
        sa.Column(
            "last_checked_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("state_key"),
    )


def downgrade() -> None:
    op.drop_table("monitoring_runtime_state")
