"""Add the durable background job queue.

Revision ID: 20260926_0017
Revises: 20260919_0016
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260926_0017"
down_revision: str | None = "20260919_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "background_jobs",
        sa.Column("job_id", sa.String(length=100), nullable=False),
        sa.Column("kind", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("progress_percent", sa.Integer(), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=200), nullable=True),
        sa.Column("run_after", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lease_owner", sa.String(length=100), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_requested", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed', 'cancelled')",
            name=op.f("ck_background_jobs_status_supported"),
        ),
        sa.CheckConstraint(
            "progress_percent >= 0 AND progress_percent <= 100",
            name=op.f("ck_background_jobs_progress_range"),
        ),
        sa.CheckConstraint(
            "attempt_count >= 0 AND attempt_count <= max_attempts "
            "AND max_attempts > 0 AND max_attempts <= 10",
            name=op.f("ck_background_jobs_attempt_range"),
        ),
        sa.CheckConstraint(
            "updated_at >= created_at",
            name=op.f("ck_background_jobs_updated_after_created"),
        ),
        sa.CheckConstraint(
            "run_after >= created_at",
            name=op.f("ck_background_jobs_run_after_created"),
        ),
        sa.CheckConstraint(
            "started_at IS NULL OR started_at >= created_at",
            name=op.f("ck_background_jobs_started_after_created"),
        ),
        sa.CheckConstraint(
            "finished_at IS NULL OR (finished_at >= created_at "
            "AND (started_at IS NULL OR finished_at >= started_at))",
            name=op.f("ck_background_jobs_finished_after_started"),
        ),
        sa.CheckConstraint(
            "(status = 'running' AND lease_owner IS NOT NULL "
            "AND lease_expires_at IS NOT NULL) OR "
            "(status != 'running' AND lease_owner IS NULL AND lease_expires_at IS NULL)",
            name=op.f("ck_background_jobs_lease_consistent"),
        ),
        sa.CheckConstraint(
            "(status IN ('succeeded', 'failed', 'cancelled') AND finished_at IS NOT NULL) "
            "OR (status IN ('queued', 'running') AND finished_at IS NULL)",
            name=op.f("ck_background_jobs_finish_consistent"),
        ),
        sa.CheckConstraint(
            "status != 'succeeded' OR progress_percent = 100",
            name=op.f("ck_background_jobs_success_progress_complete"),
        ),
        sa.PrimaryKeyConstraint("job_id", name=op.f("pk_background_jobs")),
        sa.UniqueConstraint(
            "kind",
            "idempotency_key",
            name=op.f("uq_background_jobs_kind_idempotency_key"),
        ),
    )
    op.create_index(op.f("ix_background_jobs_kind"), "background_jobs", ["kind"])
    op.create_index(op.f("ix_background_jobs_status"), "background_jobs", ["status"])
    op.create_index(op.f("ix_background_jobs_run_after"), "background_jobs", ["run_after"])
    op.create_index(op.f("ix_background_jobs_created_at"), "background_jobs", ["created_at"])
    op.create_index(op.f("ix_background_jobs_updated_at"), "background_jobs", ["updated_at"])
    op.create_index(
        "ix_background_jobs_claim",
        "background_jobs",
        ["status", "run_after", "created_at"],
    )
    op.create_index(
        "ix_background_jobs_lease",
        "background_jobs",
        ["status", "lease_expires_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_background_jobs_lease", table_name="background_jobs")
    op.drop_index("ix_background_jobs_claim", table_name="background_jobs")
    op.drop_index(op.f("ix_background_jobs_updated_at"), table_name="background_jobs")
    op.drop_index(op.f("ix_background_jobs_created_at"), table_name="background_jobs")
    op.drop_index(op.f("ix_background_jobs_run_after"), table_name="background_jobs")
    op.drop_index(op.f("ix_background_jobs_status"), table_name="background_jobs")
    op.drop_index(op.f("ix_background_jobs_kind"), table_name="background_jobs")
    op.drop_table("background_jobs")
