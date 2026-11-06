"""Add durable Nexora snapshot scan boundaries and opaque cursors.

Revision ID: 20261106_0037
Revises: 20261020_0036
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261106_0037"
down_revision: str | None = "20261020_0036"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "nexora_snapshot_scans",
        sa.Column("scan_id", sa.String(length=80), nullable=False),
        sa.Column("schema_version", sa.String(length=50), nullable=False),
        sa.Column("resource_type", sa.String(length=80), nullable=False),
        sa.Column("boundary_key", sa.String(length=512), nullable=False),
        sa.Column("boundary_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("page_limit", sa.Integer(), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "page_limit >= 1 AND page_limit <= 500",
            name=op.f("ck_nexora_snapshot_scans_page_limit_bounded"),
        ),
        sa.CheckConstraint(
            "expires_at > opened_at", name=op.f("ck_nexora_snapshot_scans_expiry_after_open")
        ),
        sa.CheckConstraint(
            "boundary_at = opened_at", name=op.f("ck_nexora_snapshot_scans_boundary_matches_open")
        ),
        sa.CheckConstraint(
            "length(boundary_key) >= 1", name=op.f("ck_nexora_snapshot_scans_boundary_key_required")
        ),
        sa.PrimaryKeyConstraint("scan_id", name=op.f("pk_nexora_snapshot_scans")),
    )
    for column in ("expires_at", "opened_at", "resource_type"):
        op.create_index(
            op.f(f"ix_nexora_snapshot_scans_{column}"), "nexora_snapshot_scans", [column]
        )
    op.create_index(
        "ix_nexora_snapshot_scans_resource_expires_at",
        "nexora_snapshot_scans",
        ["resource_type", "expires_at"],
    )

    op.create_table(
        "nexora_snapshot_cursors",
        sa.Column("cursor", sa.String(length=68), nullable=False),
        sa.Column("scan_id", sa.String(length=80), nullable=False),
        sa.Column("after_sort_key", sa.String(length=512), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "length(cursor) = 68", name=op.f("ck_nexora_snapshot_cursors_cursor_length")
        ),
        sa.CheckConstraint(
            "length(after_sort_key) >= 1",
            name=op.f("ck_nexora_snapshot_cursors_after_sort_key_required"),
        ),
        sa.CheckConstraint(
            "expires_at > created_at", name=op.f("ck_nexora_snapshot_cursors_expiry_after_create")
        ),
        sa.ForeignKeyConstraint(
            ["scan_id"],
            ["nexora_snapshot_scans.scan_id"],
            name=op.f("fk_nexora_snapshot_cursors_scan_id_nexora_snapshot_scans"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("cursor", name=op.f("pk_nexora_snapshot_cursors")),
        sa.UniqueConstraint(
            "scan_id", "after_sort_key", name="uq_nexora_snapshot_cursors_scan_after_sort_key"
        ),
    )
    for column in ("created_at", "expires_at", "scan_id"):
        op.create_index(
            op.f(f"ix_nexora_snapshot_cursors_{column}"), "nexora_snapshot_cursors", [column]
        )
    op.create_index(
        "ix_nexora_snapshot_cursors_scan_created_at",
        "nexora_snapshot_cursors",
        ["scan_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("nexora_snapshot_cursors")
    op.drop_table("nexora_snapshot_scans")
