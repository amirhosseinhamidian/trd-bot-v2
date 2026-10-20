"""Persist deterministic Decision Intelligence risk gates.

Revision ID: 20261020_0035
Revises: 20261020_0034
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261020_0035"
down_revision: str | None = "20261020_0034"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "decision_risk_gates",
        sa.Column("evaluation_id", sa.String(length=100), nullable=False),
        sa.Column("outcome_id", sa.String(length=100), nullable=False),
        sa.Column("schema_version", sa.String(length=50), nullable=False),
        sa.Column("candidate_ranking_checksum", sa.String(length=64), nullable=False),
        sa.Column("policy_version", sa.String(length=50), nullable=False),
        sa.Column("policy_checksum", sa.String(length=64), nullable=False),
        sa.Column("disposition", sa.String(length=20), nullable=False),
        sa.Column("decision", sa.String(length=20), nullable=False),
        sa.Column("assessment_id", sa.String(length=100), nullable=False),
        sa.Column("assessment_checksum", sa.String(length=64), nullable=False),
        sa.Column("approved_candidate_id", sa.String(length=100), nullable=True),
        sa.Column("has_position_sizing", sa.Boolean(), nullable=False),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("offline_only", sa.Boolean(), nullable=False),
        sa.Column("external_order_submission_allowed", sa.Boolean(), nullable=False),
        sa.Column("record_checksum", sa.String(length=64), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "disposition IN ('accepted', 'rejected')",
            name=op.f("ck_decision_risk_gates_disposition_supported"),
        ),
        sa.CheckConstraint(
            "decision IN ('approved', 'rejected')",
            name=op.f("ck_decision_risk_gates_decision_supported"),
        ),
        sa.CheckConstraint(
            "(disposition = 'accepted' AND decision = 'approved' "
            "AND approved_candidate_id IS NOT NULL AND has_position_sizing) OR "
            "(disposition = 'rejected' AND decision = 'rejected' "
            "AND approved_candidate_id IS NULL AND NOT has_position_sizing)",
            name=op.f("ck_decision_risk_gates_risk_result_consistent"),
        ),
        sa.CheckConstraint(
            "offline_only",
            name=op.f("ck_decision_risk_gates_offline_only_required"),
        ),
        sa.CheckConstraint(
            "NOT external_order_submission_allowed",
            name=op.f("ck_decision_risk_gates_external_order_forbidden"),
        ),
        sa.CheckConstraint(
            "length(candidate_ranking_checksum) = 64",
            name=op.f("ck_decision_risk_gates_ranking_checksum_length"),
        ),
        sa.CheckConstraint(
            "length(policy_checksum) = 64",
            name=op.f("ck_decision_risk_gates_policy_checksum_length"),
        ),
        sa.CheckConstraint(
            "length(assessment_checksum) = 64",
            name=op.f("ck_decision_risk_gates_assessment_checksum_length"),
        ),
        sa.CheckConstraint(
            "length(record_checksum) = 64",
            name=op.f("ck_decision_risk_gates_record_checksum_length"),
        ),
        sa.ForeignKeyConstraint(
            ["evaluation_id"],
            ["decision_evaluation_intents.evaluation_id"],
            name=op.f("fk_decision_risk_gates_evaluation_id_decision_evaluation_intents"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["outcome_id"],
            ["decision_stage_outcomes.outcome_id"],
            name=op.f("fk_decision_risk_gates_outcome_id_decision_stage_outcomes"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "evaluation_id",
            name=op.f("pk_decision_risk_gates"),
        ),
        sa.UniqueConstraint(
            "assessment_id",
            name=op.f("uq_decision_risk_gates_assessment_id"),
        ),
        sa.UniqueConstraint(
            "assessment_checksum",
            name=op.f("uq_decision_risk_gates_assessment_checksum"),
        ),
        sa.UniqueConstraint(
            "outcome_id",
            name=op.f("uq_decision_risk_gates_outcome_id"),
        ),
        sa.UniqueConstraint(
            "record_checksum",
            name=op.f("uq_decision_risk_gates_record_checksum"),
        ),
    )
    for column in (
        "approved_candidate_id",
        "candidate_ranking_checksum",
        "decision",
        "disposition",
        "evaluated_at",
        "policy_checksum",
    ):
        op.create_index(
            op.f(f"ix_decision_risk_gates_{column}"),
            "decision_risk_gates",
            [column],
        )
    op.create_index(
        "ix_decision_risk_gates_disposition_evaluated_at",
        "decision_risk_gates",
        ["disposition", "evaluated_at"],
    )


def downgrade() -> None:
    op.drop_table("decision_risk_gates")
