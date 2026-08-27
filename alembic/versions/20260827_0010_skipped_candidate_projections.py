"""Allow skipped candidate projections without fabricated replay outcomes.

Revision ID: 20260827_0010
Revises: 20260827_0009
Create Date: 2026-08-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260827_0010"
down_revision: str | None = "20260827_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_REPLAY_STATUS_CHECK = (
    "latest_replay_status IS NULL OR latest_replay_status IN ('opened', 'risk_rejected', 'no_fill')"
)
_RISK_DECISION_CHECK = (
    "latest_risk_decision IS NULL OR latest_risk_decision IN ('approved', 'rejected')"
)
_SELECTION_LINEAGE_CHECK = (
    "(selected = 1 "
    "AND latest_replay_status = 'opened' "
    "AND latest_risk_decision IS NOT NULL "
    "AND position_id IS NOT NULL "
    "AND exit_reason IS NOT NULL) "
    "OR "
    "(selected = 0 "
    "AND position_id IS NULL "
    "AND exit_reason IS NULL "
    "AND ((latest_replay_status IS NULL AND latest_risk_decision IS NULL) "
    "OR (latest_replay_status IS NOT NULL "
    "AND latest_replay_status <> 'opened' "
    "AND latest_risk_decision IS NOT NULL)))"
)

_LEGACY_REPLAY_STATUS_CHECK = "latest_replay_status IN ('opened', 'risk_rejected', 'no_fill')"
_LEGACY_RISK_DECISION_CHECK = "latest_risk_decision IN ('approved', 'rejected')"
_LEGACY_SELECTION_LINEAGE_CHECK = (
    "(selected = 1 "
    "AND latest_replay_status = 'opened' "
    "AND position_id IS NOT NULL "
    "AND exit_reason IS NOT NULL) "
    "OR "
    "(selected = 0 "
    "AND latest_replay_status <> 'opened' "
    "AND position_id IS NULL "
    "AND exit_reason IS NULL)"
)


def _replace_constraints_and_nullability(
    *,
    replay_status_check: str,
    risk_decision_check: str,
    selection_lineage_check: str,
    nullable: bool,
) -> None:
    table_name = "candidate_projections"

    with op.batch_alter_table(table_name) as batch_op:
        for constraint_name in (
            "latest_replay_status_supported",
            "latest_risk_decision_supported",
            "selection_lineage_consistent",
        ):
            batch_op.drop_constraint(
                op.f(f"ck_{table_name}_{constraint_name}"),
                type_="check",
            )

        batch_op.alter_column(
            "latest_replay_status",
            existing_type=sa.String(length=30),
            nullable=nullable,
        )
        batch_op.alter_column(
            "latest_risk_decision",
            existing_type=sa.String(length=30),
            nullable=nullable,
        )

        batch_op.create_check_constraint(
            op.f(f"ck_{table_name}_latest_replay_status_supported"),
            replay_status_check,
        )
        batch_op.create_check_constraint(
            op.f(f"ck_{table_name}_latest_risk_decision_supported"),
            risk_decision_check,
        )
        batch_op.create_check_constraint(
            op.f(f"ck_{table_name}_selection_lineage_consistent"),
            selection_lineage_check,
        )


def upgrade() -> None:
    _replace_constraints_and_nullability(
        replay_status_check=_REPLAY_STATUS_CHECK,
        risk_decision_check=_RISK_DECISION_CHECK,
        selection_lineage_check=_SELECTION_LINEAGE_CHECK,
        nullable=True,
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "DELETE FROM candidate_projections "
            "WHERE latest_replay_status IS NULL OR latest_risk_decision IS NULL"
        )
    )
    _replace_constraints_and_nullability(
        replay_status_check=_LEGACY_REPLAY_STATUS_CHECK,
        risk_decision_check=_LEGACY_RISK_DECISION_CHECK,
        selection_lineage_check=_LEGACY_SELECTION_LINEAGE_CHECK,
        nullable=False,
    )
