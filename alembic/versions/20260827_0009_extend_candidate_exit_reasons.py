"""Allow extended deterministic candidate exit reasons.

Revision ID: 20260827_0009
Revises: 20260826_0008
Create Date: 2026-08-27
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260827_0009"
down_revision: str | None = "20260826_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_EXTENDED_EXIT_REASON_CHECK = (
    "exit_reason IS NULL OR exit_reason IN "
    "('invalidation', 'target', 'trend_reversal', 'portfolio_risk', "
    "'data_unreliable', 'time_expiry', 'end_of_data')"
)

_LEGACY_EXIT_REASON_CHECK = (
    "exit_reason IS NULL OR exit_reason IN ('invalidation', 'target', 'time_expiry', 'end_of_data')"
)


def _replace_exit_reason_constraint(
    *,
    table_name: str,
    expression: str,
) -> None:
    constraint_name = op.f(f"ck_{table_name}_exit_reason_supported")

    with op.batch_alter_table(table_name) as batch_op:
        batch_op.drop_constraint(
            constraint_name,
            type_="check",
        )
        batch_op.create_check_constraint(
            constraint_name,
            expression,
        )


def upgrade() -> None:
    for table_name in (
        "candidate_journals",
        "candidate_projections",
    ):
        _replace_exit_reason_constraint(
            table_name=table_name,
            expression=_EXTENDED_EXIT_REASON_CHECK,
        )


def downgrade() -> None:
    for table_name in (
        "candidate_projections",
        "candidate_journals",
    ):
        _replace_exit_reason_constraint(
            table_name=table_name,
            expression=_LEGACY_EXIT_REASON_CHECK,
        )
