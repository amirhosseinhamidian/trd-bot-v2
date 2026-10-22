"""Add immutable Decision Intelligence policies, intents, and stage outcomes.

Revision ID: 20261019_0031
Revises: 20261018_0030
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261019_0031"
down_revision: str | None = "20261018_0030"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "decision_policy_definitions",
        sa.Column("policy_id", sa.String(length=100), nullable=False),
        sa.Column("policy_version", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.String(length=50), nullable=False),
        sa.Column("policy_key", sa.String(length=100), nullable=False),
        sa.Column("supersedes_version", sa.Integer(), nullable=True),
        sa.Column("state", sa.String(length=20), nullable=False),
        sa.Column("allowed_mode_count", sa.Integer(), nullable=False),
        sa.Column("offline_only", sa.Boolean(), nullable=False),
        sa.Column("external_order_submission_allowed", sa.Boolean(), nullable=False),
        sa.Column("definition_checksum", sa.String(length=64), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "policy_version >= 1",
            name=op.f("ck_decision_policy_definitions_policy_version_positive"),
        ),
        sa.CheckConstraint(
            "(policy_version = 1 AND supersedes_version IS NULL) OR "
            "(policy_version > 1 AND supersedes_version = policy_version - 1)",
            name=op.f("ck_decision_policy_definitions_lineage_consistent"),
        ),
        sa.CheckConstraint(
            "state IN ('enabled', 'disabled')",
            name=op.f("ck_decision_policy_definitions_state_supported"),
        ),
        sa.CheckConstraint(
            "allowed_mode_count >= 1 AND allowed_mode_count <= 3",
            name=op.f("ck_decision_policy_definitions_allowed_mode_count_bounded"),
        ),
        sa.CheckConstraint(
            "offline_only",
            name=op.f("ck_decision_policy_definitions_offline_only_required"),
        ),
        sa.CheckConstraint(
            "NOT external_order_submission_allowed",
            name=op.f("ck_decision_policy_definitions_external_order_submission_forbidden"),
        ),
        sa.CheckConstraint(
            "length(definition_checksum) = 64",
            name=op.f("ck_decision_policy_definitions_checksum_length"),
        ),
        sa.PrimaryKeyConstraint(
            "policy_id",
            "policy_version",
            name=op.f("pk_decision_policy_definitions"),
        ),
        sa.UniqueConstraint(
            "definition_checksum",
            name=op.f("uq_decision_policy_definitions_definition_checksum"),
        ),
        sa.UniqueConstraint(
            "policy_key",
            "policy_version",
            name=op.f("uq_decision_policy_definitions_key_version"),
        ),
    )
    for column in ("created_at", "policy_key", "state"):
        op.create_index(
            op.f(f"ix_decision_policy_definitions_{column}"),
            "decision_policy_definitions",
            [column],
        )
    op.create_index(
        "ix_decision_policy_definitions_state_created_at",
        "decision_policy_definitions",
        ["state", "created_at"],
    )

    op.create_table(
        "decision_evaluation_intents",
        sa.Column("evaluation_id", sa.String(length=100), nullable=False),
        sa.Column("schema_version", sa.String(length=50), nullable=False),
        sa.Column("stage", sa.String(length=30), nullable=False),
        sa.Column("mode", sa.String(length=20), nullable=False),
        sa.Column("dataset_id", sa.String(length=100), nullable=False),
        sa.Column("dataset_reference_id", sa.String(length=100), nullable=False),
        sa.Column("dataset_reference_checksum", sa.String(length=64), nullable=False),
        sa.Column("strategy_reference_id", sa.String(length=100), nullable=False),
        sa.Column("strategy_name", sa.String(length=100), nullable=False),
        sa.Column("strategy_version", sa.String(length=50), nullable=False),
        sa.Column("strategy_behavior_fingerprint", sa.String(length=71), nullable=False),
        sa.Column("strategy_reference_checksum", sa.String(length=64), nullable=False),
        sa.Column("market_context_reference_id", sa.String(length=100), nullable=False),
        sa.Column("market_context_assessment_id", sa.String(length=100), nullable=False),
        sa.Column(
            "market_context_reference_checksum",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column("policy_id", sa.String(length=100), nullable=False),
        sa.Column("policy_version", sa.Integer(), nullable=False),
        sa.Column("policy_definition_checksum", sa.String(length=64), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("base_asset", sa.String(length=30), nullable=False),
        sa.Column("quote_asset", sa.String(length=30), nullable=False),
        sa.Column("market_type", sa.String(length=30), nullable=False),
        sa.Column("timeframe", sa.String(length=20), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("offline_only", sa.Boolean(), nullable=False),
        sa.Column("external_order_submission_allowed", sa.Boolean(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=100), nullable=False),
        sa.Column("intent_checksum", sa.String(length=64), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "stage = 'strategy_evaluation'",
            name=op.f("ck_decision_evaluation_intents_stage_supported"),
        ),
        sa.CheckConstraint(
            "mode IN ('research', 'shadow', 'paper')",
            name=op.f("ck_decision_evaluation_intents_mode_supported"),
        ),
        sa.CheckConstraint(
            "offline_only",
            name=op.f("ck_decision_evaluation_intents_offline_only_required"),
        ),
        sa.CheckConstraint(
            "NOT external_order_submission_allowed",
            name=op.f("ck_decision_evaluation_intents_external_order_submission_forbidden"),
        ),
        sa.CheckConstraint(
            "length(dataset_reference_checksum) = 64",
            name=op.f("ck_decision_evaluation_intents_dataset_checksum_length"),
        ),
        sa.CheckConstraint(
            "length(strategy_reference_checksum) = 64",
            name=op.f("ck_decision_evaluation_intents_strategy_checksum_length"),
        ),
        sa.CheckConstraint(
            "length(market_context_reference_checksum) = 64",
            name=op.f("ck_decision_evaluation_intents_market_context_checksum_length"),
        ),
        sa.CheckConstraint(
            "length(policy_definition_checksum) = 64",
            name=op.f("ck_decision_evaluation_intents_policy_checksum_length"),
        ),
        sa.CheckConstraint(
            "length(intent_checksum) = 64",
            name=op.f("ck_decision_evaluation_intents_intent_checksum_length"),
        ),
        sa.ForeignKeyConstraint(
            ["dataset_id"],
            ["dataset_snapshots.dataset_id"],
            name=op.f("fk_decision_evaluation_intents_dataset_id_dataset_snapshots"),
        ),
        sa.ForeignKeyConstraint(
            ["market_context_assessment_id"],
            ["market_regime_assessments.assessment_id"],
            name=op.f(
                "fk_decision_evaluation_intents_market_context_assessment_id_"
                "market_regime_assessments"
            ),
        ),
        sa.ForeignKeyConstraint(
            ["policy_id", "policy_version"],
            [
                "decision_policy_definitions.policy_id",
                "decision_policy_definitions.policy_version",
            ],
            name=op.f(
                "fk_decision_evaluation_intents_policy_id_policy_version_"
                "decision_policy_definitions"
            ),
        ),
        sa.PrimaryKeyConstraint(
            "evaluation_id",
            name=op.f("pk_decision_evaluation_intents"),
        ),
        sa.UniqueConstraint(
            "idempotency_key",
            name=op.f("uq_decision_evaluation_intents_idempotency_key"),
        ),
        sa.UniqueConstraint(
            "intent_checksum",
            name=op.f("uq_decision_evaluation_intents_intent_checksum"),
        ),
    )
    for column in (
        "dataset_id",
        "dataset_reference_id",
        "market_context_assessment_id",
        "market_context_reference_id",
        "mode",
        "policy_id",
        "requested_at",
        "source",
        "strategy_name",
        "strategy_reference_id",
    ):
        op.create_index(
            op.f(f"ix_decision_evaluation_intents_{column}"),
            "decision_evaluation_intents",
            [column],
        )
    op.create_index(
        "ix_decision_evaluation_intents_stream_requested_at",
        "decision_evaluation_intents",
        ["source", "base_asset", "quote_asset", "market_type", "requested_at"],
    )
    op.create_index(
        "ix_decision_evaluation_intents_strategy_requested_at",
        "decision_evaluation_intents",
        ["strategy_name", "strategy_version", "requested_at"],
    )

    op.create_table(
        "decision_stage_outcomes",
        sa.Column("outcome_id", sa.String(length=100), nullable=False),
        sa.Column("schema_version", sa.String(length=50), nullable=False),
        sa.Column("evaluation_id", sa.String(length=100), nullable=False),
        sa.Column("stage", sa.String(length=30), nullable=False),
        sa.Column("disposition", sa.String(length=20), nullable=False),
        sa.Column("reason_code_count", sa.Integer(), nullable=False),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("offline_only", sa.Boolean(), nullable=False),
        sa.Column("external_order_submission_allowed", sa.Boolean(), nullable=False),
        sa.Column("outcome_checksum", sa.String(length=64), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "stage IN ('strategy_evaluation', 'candidate_ranking', "
            "'risk_gate', 'portfolio_simulation')",
            name=op.f("ck_decision_stage_outcomes_stage_supported"),
        ),
        sa.CheckConstraint(
            "disposition IN ('accepted', 'rejected', 'deferred', 'unavailable')",
            name=op.f("ck_decision_stage_outcomes_disposition_supported"),
        ),
        sa.CheckConstraint(
            "reason_code_count >= 0",
            name=op.f("ck_decision_stage_outcomes_reason_code_count_nonnegative"),
        ),
        sa.CheckConstraint(
            "(disposition = 'accepted' AND reason_code_count = 0) OR "
            "(disposition != 'accepted' AND reason_code_count >= 1)",
            name=op.f("ck_decision_stage_outcomes_outcome_consistent"),
        ),
        sa.CheckConstraint(
            "offline_only",
            name=op.f("ck_decision_stage_outcomes_offline_only_required"),
        ),
        sa.CheckConstraint(
            "NOT external_order_submission_allowed",
            name=op.f("ck_decision_stage_outcomes_external_order_submission_forbidden"),
        ),
        sa.CheckConstraint(
            "length(outcome_checksum) = 64",
            name=op.f("ck_decision_stage_outcomes_checksum_length"),
        ),
        sa.ForeignKeyConstraint(
            ["evaluation_id"],
            ["decision_evaluation_intents.evaluation_id"],
            name=op.f("fk_decision_stage_outcomes_evaluation_id_decision_evaluation_intents"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("outcome_id", name=op.f("pk_decision_stage_outcomes")),
        sa.UniqueConstraint(
            "evaluation_id",
            "stage",
            name=op.f("uq_decision_stage_outcomes_evaluation_stage"),
        ),
        sa.UniqueConstraint(
            "outcome_checksum",
            name=op.f("uq_decision_stage_outcomes_outcome_checksum"),
        ),
    )
    for column in ("disposition", "evaluated_at", "evaluation_id", "stage"):
        op.create_index(
            op.f(f"ix_decision_stage_outcomes_{column}"),
            "decision_stage_outcomes",
            [column],
        )
    op.create_index(
        "ix_decision_stage_outcomes_stage_disposition_evaluated_at",
        "decision_stage_outcomes",
        ["stage", "disposition", "evaluated_at"],
    )


def downgrade() -> None:
    op.drop_table("decision_stage_outcomes")
    op.drop_table("decision_evaluation_intents")
    op.drop_table("decision_policy_definitions")
