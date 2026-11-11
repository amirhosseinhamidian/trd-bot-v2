"""Add atomic Nexora export jobs, artifacts, and manifests.

Revision ID: 20261111_0040
Revises: 20261107_0039
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261111_0040"
down_revision: str | None = "20261107_0039"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "nexora_export_jobs",
        sa.Column("export_id", sa.String(length=68), nullable=False),
        sa.Column("idempotency_key", sa.String(length=160), nullable=False),
        sa.Column("background_job_id", sa.String(length=24), nullable=False),
        sa.Column("request_checksum", sa.String(length=71), nullable=False),
        sa.Column("request_schema_version", sa.String(length=50), nullable=False),
        sa.Column("mode", sa.String(length=20), nullable=False),
        sa.Column("profile", sa.String(length=20), nullable=False),
        sa.Column("provider_version", sa.String(length=30), nullable=False),
        sa.Column("request_json", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("manifest_json", sa.Text(), nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("contains_secrets", sa.Boolean(), nullable=False),
        sa.CheckConstraint(
            "status IN ('accepted', 'running', 'complete', 'failed')",
            name=op.f("ck_nexora_export_jobs_status_supported"),
        ),
        sa.CheckConstraint(
            "mode IN ('full', 'incremental', 'selected')",
            name=op.f("ck_nexora_export_jobs_mode_supported"),
        ),
        sa.CheckConstraint(
            "profile IN ('private', 'ai_safe')",
            name=op.f("ck_nexora_export_jobs_profile_supported"),
        ),
        sa.CheckConstraint(
            "length(request_checksum) = 71",
            name=op.f("ck_nexora_export_jobs_request_checksum_length"),
        ),
        sa.CheckConstraint(
            "(status = 'complete' AND completed_at IS NOT NULL AND manifest_json IS NOT NULL "
            "AND error_code IS NULL) OR "
            "(status = 'failed' AND completed_at IS NOT NULL AND manifest_json IS NULL "
            "AND error_code IS NOT NULL) OR "
            "(status IN ('accepted', 'running') AND completed_at IS NULL "
            "AND manifest_json IS NULL AND error_code IS NULL)",
            name=op.f("ck_nexora_export_jobs_lifecycle_consistent"),
        ),
        sa.CheckConstraint(
            "NOT contains_secrets",
            name=op.f("ck_nexora_export_jobs_secrets_forbidden"),
        ),
        sa.ForeignKeyConstraint(
            ["background_job_id"],
            ["background_jobs.job_id"],
            name=op.f("fk_nexora_export_jobs_background_job_id_background_jobs"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("export_id", name=op.f("pk_nexora_export_jobs")),
        sa.UniqueConstraint(
            "background_job_id", name=op.f("uq_nexora_export_jobs_background_job_id")
        ),
    )
    op.create_index(
        op.f("ix_nexora_export_jobs_idempotency_key"),
        "nexora_export_jobs",
        ["idempotency_key"],
        unique=True,
    )
    for column in ("request_checksum", "requested_at", "status"):
        op.create_index(op.f(f"ix_nexora_export_jobs_{column}"), "nexora_export_jobs", [column])
    op.create_index(
        "ix_nexora_export_jobs_status_requested_at",
        "nexora_export_jobs",
        ["status", "requested_at"],
    )

    op.create_table(
        "nexora_export_artifacts",
        sa.Column("export_id", sa.String(length=68), nullable=False),
        sa.Column("path", sa.String(length=240), nullable=False),
        sa.Column("media_type", sa.String(length=120), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("schema_version", sa.String(length=120), nullable=False),
        sa.Column("content", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "row_count >= 0",
            name=op.f("ck_nexora_export_artifacts_row_count_nonnegative"),
        ),
        sa.CheckConstraint(
            "size_bytes >= 0",
            name=op.f("ck_nexora_export_artifacts_size_bytes_nonnegative"),
        ),
        sa.CheckConstraint(
            "length(sha256) = 64",
            name=op.f("ck_nexora_export_artifacts_sha256_length"),
        ),
        sa.ForeignKeyConstraint(
            ["export_id"],
            ["nexora_export_jobs.export_id"],
            name=op.f("fk_nexora_export_artifacts_export_id_nexora_export_jobs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("export_id", "path", name=op.f("pk_nexora_export_artifacts")),
    )
    op.create_index(
        op.f("ix_nexora_export_artifacts_created_at"),
        "nexora_export_artifacts",
        ["created_at"],
    )
    op.create_index(
        op.f("ix_nexora_export_artifacts_sha256"),
        "nexora_export_artifacts",
        ["sha256"],
    )


def downgrade() -> None:
    op.drop_table("nexora_export_artifacts")
    op.drop_table("nexora_export_jobs")
