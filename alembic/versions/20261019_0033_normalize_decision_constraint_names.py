"""Normalize Decision Intelligence check-constraint names.

Revision ID: 20261019_0033
Revises: 20261019_0032
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20261019_0033"
down_revision: str | None = "20261019_0032"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EXPRESSION = "NOT external_order_submission_allowed"
TABLES = (
    "decision_policy_definitions",
    "decision_evaluation_intents",
    "decision_strategy_evaluations",
)
LEGACY_SUFFIX = "external_order_submission_forbidden"
NORMALIZED_SUFFIX = "external_order_forbidden"


def _constraint_name(table_name: str, suffix: str) -> str:
    return f"ck_{table_name}_{suffix}"


def upgrade() -> None:
    for table_name in TABLES:
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.drop_constraint(
                op.f(_constraint_name(table_name, LEGACY_SUFFIX)),
                type_="check",
            )
            batch_op.create_check_constraint(
                op.f(_constraint_name(table_name, NORMALIZED_SUFFIX)),
                EXPRESSION,
            )


def downgrade() -> None:
    for table_name in reversed(TABLES):
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.drop_constraint(
                op.f(_constraint_name(table_name, NORMALIZED_SUFFIX)),
                type_="check",
            )
            batch_op.create_check_constraint(
                op.f(_constraint_name(table_name, LEGACY_SUFFIX)),
                EXPRESSION,
            )
