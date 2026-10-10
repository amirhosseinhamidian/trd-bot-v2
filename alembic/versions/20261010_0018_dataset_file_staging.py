"""Add durable temporary staging for dataset file imports.

Revision ID: 20261010_0018
Revises: 20260926_0017
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261010_0018"
down_revision: str | None = "20260926_0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "dataset_file_stages",
        sa.Column("stage_id", sa.String(length=100), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("file_checksum", sa.String(length=64), nullable=False),
        sa.Column("file_size_bytes", sa.Integer(), nullable=False),
        sa.Column("content_bytes", sa.LargeBinary(), nullable=False),
        sa.Column("request_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "file_size_bytes > 0 AND file_size_bytes <= 10485760",
            name=op.f("ck_dataset_file_stages_file_size_bounded"),
        ),
        sa.CheckConstraint(
            "length(file_checksum) = 64",
            name=op.f("ck_dataset_file_stages_checksum_length"),
        ),
        sa.CheckConstraint(
            "expires_at > created_at",
            name=op.f("ck_dataset_file_stages_expiry_after_created"),
        ),
        sa.PrimaryKeyConstraint("stage_id", name=op.f("pk_dataset_file_stages")),
    )
    op.create_index(
        op.f("ix_dataset_file_stages_file_checksum"),
        "dataset_file_stages",
        ["file_checksum"],
    )
    op.create_index(
        op.f("ix_dataset_file_stages_created_at"),
        "dataset_file_stages",
        ["created_at"],
    )
    op.create_index(
        op.f("ix_dataset_file_stages_expires_at"),
        "dataset_file_stages",
        ["expires_at"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_dataset_file_stages_expires_at"),
        table_name="dataset_file_stages",
    )
    op.drop_index(
        op.f("ix_dataset_file_stages_created_at"),
        table_name="dataset_file_stages",
    )
    op.drop_index(
        op.f("ix_dataset_file_stages_file_checksum"),
        table_name="dataset_file_stages",
    )
    op.drop_table("dataset_file_stages")
