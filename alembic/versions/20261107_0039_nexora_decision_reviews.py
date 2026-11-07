"""Add the durable Nexora decision-review command journal.

Revision ID: 20261107_0039
Revises: 20261107_0038
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261107_0039"
down_revision: str | None = "20261107_0038"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "nexora_decision_reviews",
        sa.Column("command_id", sa.String(length=75), nullable=False),
        sa.Column("idempotency_key", sa.String(length=160), nullable=False),
        sa.Column("decision_id", sa.String(length=100), nullable=False),
        sa.Column("command_schema_version", sa.String(length=50), nullable=False),
        sa.Column("command_type", sa.String(length=50), nullable=False),
        sa.Column("action", sa.String(length=20), nullable=False),
        sa.Column("portfolio_mode", sa.String(length=20), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("source_reference_schema_version", sa.String(length=50), nullable=False),
        sa.Column("source_product", sa.String(length=30), nullable=False),
        sa.Column("source_version", sa.String(length=30), nullable=False),
        sa.Column("source_resource_type", sa.String(length=80), nullable=False),
        sa.Column("source_resource_id", sa.String(length=160), nullable=False),
        sa.Column("source_resource_schema_version", sa.String(length=120), nullable=False),
        sa.Column("source_observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_evidence_checksum", sa.String(length=71), nullable=False),
        sa.Column("request_checksum", sa.String(length=71), nullable=False),
        sa.Column("correlation_id", sa.String(length=36), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("offline_only", sa.Boolean(), nullable=False),
        sa.Column("execution_authorization", sa.Boolean(), nullable=False),
        sa.Column("creates_live_order", sa.Boolean(), nullable=False),
        sa.Column("posts_portfolio_transaction", sa.Boolean(), nullable=False),
        sa.Column("request_json", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "command_type IN ('decision_review.accept.v1', "
            "'decision_review.reject.v1', 'decision_review.defer.v1')",
            name=op.f("ck_nexora_decision_reviews_command_type_supported"),
        ),
        sa.CheckConstraint(
            "action IN ('accept', 'reject', 'defer')",
            name=op.f("ck_nexora_decision_reviews_action_supported"),
        ),
        sa.CheckConstraint(
            "portfolio_mode IN ('paper', 'shadow')",
            name=op.f("ck_nexora_decision_reviews_portfolio_mode_supported"),
        ),
        sa.CheckConstraint(
            "(action = 'accept' AND command_type = 'decision_review.accept.v1') OR "
            "(action = 'reject' AND command_type = 'decision_review.reject.v1') OR "
            "(action = 'defer' AND command_type = 'decision_review.defer.v1')",
            name=op.f("ck_nexora_decision_reviews_command_action_consistent"),
        ),
        sa.CheckConstraint(
            "source_product = 'trd_bot'",
            name=op.f("ck_nexora_decision_reviews_source_product_trd_bot"),
        ),
        sa.CheckConstraint(
            "source_resource_type = 'decision_evaluation'",
            name=op.f("ck_nexora_decision_reviews_source_resource_type_decision_evaluation"),
        ),
        sa.CheckConstraint(
            "decision_id = source_resource_id",
            name=op.f("ck_nexora_decision_reviews_source_identity_consistent"),
        ),
        sa.CheckConstraint(
            "reviewed_at >= source_observed_at",
            name=op.f("ck_nexora_decision_reviews_review_after_source"),
        ),
        sa.CheckConstraint(
            "length(source_evidence_checksum) = 71",
            name=op.f("ck_nexora_decision_reviews_source_evidence_checksum_length"),
        ),
        sa.CheckConstraint(
            "length(request_checksum) = 71",
            name=op.f("ck_nexora_decision_reviews_request_checksum_length"),
        ),
        sa.CheckConstraint(
            "offline_only",
            name=op.f("ck_nexora_decision_reviews_offline_only_required"),
        ),
        sa.CheckConstraint(
            "NOT execution_authorization",
            name=op.f("ck_nexora_decision_reviews_execution_authorization_forbidden"),
        ),
        sa.CheckConstraint(
            "NOT creates_live_order",
            name=op.f("ck_nexora_decision_reviews_live_order_forbidden"),
        ),
        sa.CheckConstraint(
            "NOT posts_portfolio_transaction",
            name=op.f("ck_nexora_decision_reviews_portfolio_transaction_forbidden"),
        ),
        sa.ForeignKeyConstraint(
            ["decision_id"],
            ["decision_evaluation_intents.evaluation_id"],
            name=op.f("fk_nexora_decision_reviews_decision_id_decision_evaluation_intents"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("command_id", name=op.f("pk_nexora_decision_reviews")),
    )
    for column in (
        "accepted_at",
        "action",
        "decision_id",
        "portfolio_mode",
        "request_checksum",
        "reviewed_at",
        "source_evidence_checksum",
    ):
        op.create_index(
            op.f(f"ix_nexora_decision_reviews_{column}"), "nexora_decision_reviews", [column]
        )
    op.create_index(
        op.f("ix_nexora_decision_reviews_idempotency_key"),
        "nexora_decision_reviews",
        ["idempotency_key"],
        unique=True,
    )
    op.create_index(
        "ix_nexora_decision_reviews_decision_accepted_at",
        "nexora_decision_reviews",
        ["decision_id", "accepted_at"],
    )


def downgrade() -> None:
    op.drop_table("nexora_decision_reviews")
