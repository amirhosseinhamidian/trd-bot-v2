"""Normalize optimization execution check-constraint names.

Revision ID: 20260919_0016
Revises: 20260919_0015
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260919_0016"
down_revision: str | None = "20260919_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE_NAME = "optimization_executions"

CHECK_CONSTRAINTS = (
    (
        "status_supported",
        "optimization_execution_status_supported",
        "status IN ('queued', 'running', 'succeeded', 'failed')",
    ),
    (
        "total_trials_positive",
        "optimization_execution_total_trials_positive",
        "total_trials > 0",
    ),
    (
        "progress_range",
        "optimization_execution_progress_range",
        "completed_trials >= 0 AND completed_trials <= total_trials",
    ),
    (
        "updated_after_created",
        "optimization_execution_updated_after_created",
        "updated_at >= created_at",
    ),
    (
        "started_after_created",
        "optimization_execution_started_after_created",
        "started_at IS NULL OR started_at >= created_at",
    ),
    (
        "finished_after_started",
        "optimization_execution_finished_after_started",
        "finished_at IS NULL OR (started_at IS NOT NULL AND finished_at >= started_at)",
    ),
)


def _constraint_name(suffix: str) -> str:
    return f"ck_{TABLE_NAME}_{suffix}"


def upgrade() -> None:
    with op.batch_alter_table(TABLE_NAME) as batch_op:
        for _, legacy_suffix, _ in CHECK_CONSTRAINTS:
            batch_op.drop_constraint(
                op.f(_constraint_name(legacy_suffix)),
                type_="check",
            )

        for suffix, _, expression in CHECK_CONSTRAINTS:
            batch_op.create_check_constraint(
                op.f(_constraint_name(suffix)),
                expression,
            )


def downgrade() -> None:
    with op.batch_alter_table(TABLE_NAME) as batch_op:
        for suffix, _, _ in reversed(CHECK_CONSTRAINTS):
            batch_op.drop_constraint(
                op.f(_constraint_name(suffix)),
                type_="check",
            )

        for _, legacy_suffix, expression in reversed(CHECK_CONSTRAINTS):
            batch_op.create_check_constraint(
                op.f(_constraint_name(legacy_suffix)),
                expression,
            )
