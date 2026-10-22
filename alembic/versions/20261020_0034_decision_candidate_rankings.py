"""Persist deterministic Decision Intelligence candidate rankings.

Revision ID: 20261020_0034
Revises: 20261019_0033
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261020_0034"
down_revision: str | None = "20261019_0033"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "decision_candidate_rankings",
        sa.Column("evaluation_id", sa.String(length=100), nullable=False),
        sa.Column("outcome_id", sa.String(length=100), nullable=False),
        sa.Column("schema_version", sa.String(length=50), nullable=False),
        sa.Column("policy_version", sa.String(length=50), nullable=False),
        sa.Column("policy_checksum", sa.String(length=64), nullable=False),
        sa.Column("disposition", sa.String(length=20), nullable=False),
        sa.Column("source_signal_count", sa.Integer(), nullable=False),
        sa.Column("candidate_count", sa.Integer(), nullable=False),
        sa.Column("excluded_signal_count", sa.Integer(), nullable=False),
        sa.Column("top_candidate_id", sa.String(length=100), nullable=True),
        sa.Column("ranked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("offline_only", sa.Boolean(), nullable=False),
        sa.Column("external_order_submission_allowed", sa.Boolean(), nullable=False),
        sa.Column("record_checksum", sa.String(length=64), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "disposition IN ('accepted', 'deferred')",
            name=op.f("ck_decision_candidate_rankings_disposition_supported"),
        ),
        sa.CheckConstraint(
            "source_signal_count > 0",
            name=op.f("ck_decision_candidate_rankings_source_count_positive"),
        ),
        sa.CheckConstraint(
            "candidate_count >= 0",
            name=op.f("ck_decision_candidate_rankings_candidate_count_nonnegative"),
        ),
        sa.CheckConstraint(
            "excluded_signal_count >= 0",
            name=op.f("ck_decision_candidate_rankings_excluded_count_nonnegative"),
        ),
        sa.CheckConstraint(
            "candidate_count + excluded_signal_count = source_signal_count",
            name=op.f("ck_decision_candidate_rankings_counts_consistent"),
        ),
        sa.CheckConstraint(
            "(disposition = 'accepted' AND candidate_count > 0 "
            "AND top_candidate_id IS NOT NULL) OR "
            "(disposition = 'deferred' AND candidate_count = 0 "
            "AND top_candidate_id IS NULL)",
            name=op.f("ck_decision_candidate_rankings_ranking_consistent"),
        ),
        sa.CheckConstraint(
            "offline_only",
            name=op.f("ck_decision_candidate_rankings_offline_only_required"),
        ),
        sa.CheckConstraint(
            "NOT external_order_submission_allowed",
            name=op.f("ck_decision_candidate_rankings_external_order_forbidden"),
        ),
        sa.CheckConstraint(
            "length(policy_checksum) = 64",
            name=op.f("ck_decision_candidate_rankings_policy_checksum_length"),
        ),
        sa.CheckConstraint(
            "length(record_checksum) = 64",
            name=op.f("ck_decision_candidate_rankings_record_checksum_length"),
        ),
        sa.ForeignKeyConstraint(
            ["evaluation_id"],
            ["decision_evaluation_intents.evaluation_id"],
            name=op.f("fk_decision_candidate_rankings_evaluation_id_decision_evaluation_intents"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["outcome_id"],
            ["decision_stage_outcomes.outcome_id"],
            name=op.f("fk_decision_candidate_rankings_outcome_id_decision_stage_outcomes"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "evaluation_id",
            name=op.f("pk_decision_candidate_rankings"),
        ),
        sa.UniqueConstraint(
            "outcome_id",
            name=op.f("uq_decision_candidate_rankings_outcome_id"),
        ),
        sa.UniqueConstraint(
            "record_checksum",
            name=op.f("uq_decision_candidate_rankings_record_checksum"),
        ),
    )
    for column in (
        "disposition",
        "policy_checksum",
        "ranked_at",
        "top_candidate_id",
    ):
        op.create_index(
            op.f(f"ix_decision_candidate_rankings_{column}"),
            "decision_candidate_rankings",
            [column],
        )
    op.create_index(
        "ix_decision_candidate_rankings_disposition_ranked_at",
        "decision_candidate_rankings",
        ["disposition", "ranked_at"],
    )


def downgrade() -> None:
    op.drop_table("decision_candidate_rankings")
