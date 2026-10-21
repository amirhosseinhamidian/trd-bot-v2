"""Persist bounded paper/shadow portfolio intelligence.

Revision ID: 20261020_0036
Revises: 20261020_0035
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261020_0036"
down_revision: str | None = "20261020_0035"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "decision_portfolio_intelligence",
        sa.Column("evaluation_id", sa.String(length=100), nullable=False),
        sa.Column("outcome_id", sa.String(length=100), nullable=False),
        sa.Column("schema_version", sa.String(length=50), nullable=False),
        sa.Column("risk_gate_checksum", sa.String(length=64), nullable=False),
        sa.Column("policy_version", sa.String(length=50), nullable=False),
        sa.Column("policy_checksum", sa.String(length=64), nullable=False),
        sa.Column("disposition", sa.String(length=20), nullable=False),
        sa.Column("recommendation", sa.String(length=20), nullable=False),
        sa.Column("has_analysis", sa.Boolean(), nullable=False),
        sa.Column("snapshot_id", sa.String(length=100), nullable=True),
        sa.Column("candidate_id", sa.String(length=100), nullable=True),
        sa.Column("analyzed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("offline_only", sa.Boolean(), nullable=False),
        sa.Column("external_order_submission_allowed", sa.Boolean(), nullable=False),
        sa.Column("record_checksum", sa.String(length=64), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "disposition IN ('accepted', 'rejected', 'unavailable')",
            name=op.f("ck_decision_portfolio_intelligence_disposition_supported"),
        ),
        sa.CheckConstraint(
            "recommendation IN ('accept', 'reject', 'unavailable')",
            name=op.f("ck_decision_portfolio_intelligence_recommendation_supported"),
        ),
        sa.CheckConstraint(
            "(disposition = 'accepted' AND recommendation = 'accept' AND has_analysis) OR "
            "(disposition = 'rejected' AND recommendation = 'reject' AND has_analysis) OR "
            "(disposition = 'unavailable' AND recommendation = 'unavailable' "
            "AND NOT has_analysis)",
            name=op.f("ck_decision_portfolio_intelligence_result_consistent"),
        ),
        sa.CheckConstraint(
            "offline_only",
            name=op.f("ck_decision_portfolio_intelligence_offline_only_required"),
        ),
        sa.CheckConstraint(
            "NOT external_order_submission_allowed",
            name=op.f("ck_decision_portfolio_intelligence_external_order_forbidden"),
        ),
        sa.CheckConstraint(
            "length(risk_gate_checksum) = 64",
            name=op.f("ck_decision_portfolio_intelligence_risk_checksum_length"),
        ),
        sa.CheckConstraint(
            "length(policy_checksum) = 64",
            name=op.f("ck_decision_portfolio_intelligence_policy_checksum_length"),
        ),
        sa.CheckConstraint(
            "length(record_checksum) = 64",
            name=op.f("ck_decision_portfolio_intelligence_record_checksum_length"),
        ),
        sa.ForeignKeyConstraint(
            ["evaluation_id"],
            ["decision_evaluation_intents.evaluation_id"],
            name=op.f(
                "fk_decision_portfolio_intelligence_evaluation_id_decision_evaluation_intents"
            ),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["outcome_id"],
            ["decision_stage_outcomes.outcome_id"],
            name=op.f("fk_decision_portfolio_intelligence_outcome_id_decision_stage_outcomes"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "evaluation_id",
            name=op.f("pk_decision_portfolio_intelligence"),
        ),
        sa.UniqueConstraint(
            "outcome_id",
            name=op.f("uq_decision_portfolio_intelligence_outcome_id"),
        ),
        sa.UniqueConstraint(
            "record_checksum",
            name=op.f("uq_decision_portfolio_intelligence_record_checksum"),
        ),
    )
    for column in (
        "analyzed_at",
        "candidate_id",
        "disposition",
        "policy_checksum",
        "recommendation",
        "risk_gate_checksum",
        "snapshot_id",
    ):
        op.create_index(
            op.f(f"ix_decision_portfolio_intelligence_{column}"),
            "decision_portfolio_intelligence",
            [column],
        )
    op.create_index(
        "ix_decision_portfolio_intelligence_disposition_analyzed_at",
        "decision_portfolio_intelligence",
        ["disposition", "analyzed_at"],
    )


def downgrade() -> None:
    op.drop_table("decision_portfolio_intelligence")
