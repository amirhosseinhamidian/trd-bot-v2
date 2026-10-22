"""Add durable alert acknowledgement and snooze lifecycle.

Revision ID: 20261018_0027
Revises: 20261017_0026
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261018_0027"
down_revision: str | None = "20261017_0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "alert_inbox_states",
        sa.Column("alert_id", sa.String(length=100), nullable=False),
        sa.Column("schema_version", sa.String(length=50), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("acknowledged_by", sa.String(length=100), nullable=True),
        sa.Column("snoozed_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("snoozed_by", sa.String(length=100), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "(acknowledged_at IS NULL AND acknowledged_by IS NULL) OR "
            "(acknowledged_at IS NOT NULL AND acknowledged_by IS NOT NULL)",
            name=op.f("ck_alert_inbox_states_acknowledgement_consistent"),
        ),
        sa.CheckConstraint(
            "(snoozed_until IS NULL AND snoozed_by IS NULL) OR "
            "(snoozed_until IS NOT NULL AND snoozed_by IS NOT NULL)",
            name=op.f("ck_alert_inbox_states_snooze_consistent"),
        ),
        sa.CheckConstraint(
            "acknowledged_at IS NULL OR snoozed_until IS NULL",
            name=op.f("ck_alert_inbox_states_acknowledged_not_snoozed"),
        ),
        sa.ForeignKeyConstraint(
            ["alert_id"],
            ["alerts.alert_id"],
            name=op.f("fk_alert_inbox_states_alert_id_alerts"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("alert_id", name=op.f("pk_alert_inbox_states")),
    )
    for column in ("acknowledged_at", "snoozed_until", "updated_at"):
        op.create_index(op.f(f"ix_alert_inbox_states_{column}"), "alert_inbox_states", [column])

    op.execute(
        sa.text(
            "INSERT INTO alert_inbox_states "
            "(alert_id, schema_version, acknowledged_at, acknowledged_by, "
            "snoozed_until, snoozed_by, updated_at) "
            "SELECT alert_id, 'alert-inbox-state-v1', NULL, NULL, NULL, NULL, created_at "
            "FROM alerts"
        )
    )

    op.create_table(
        "alert_actions",
        sa.Column("action_id", sa.String(length=100), nullable=False),
        sa.Column("schema_version", sa.String(length=50), nullable=False),
        sa.Column("alert_id", sa.String(length=100), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("acted_by", sa.String(length=100), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("snoozed_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("action_checksum", sa.String(length=64), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "kind IN ('acknowledged', 'snoozed')",
            name=op.f("ck_alert_actions_kind_supported"),
        ),
        sa.CheckConstraint(
            "(kind = 'acknowledged' AND snoozed_until IS NULL) OR "
            "(kind = 'snoozed' AND snoozed_until IS NOT NULL "
            "AND snoozed_until > occurred_at)",
            name=op.f("ck_alert_actions_payload_consistent"),
        ),
        sa.CheckConstraint(
            "length(action_checksum) = 64",
            name=op.f("ck_alert_actions_checksum_length"),
        ),
        sa.ForeignKeyConstraint(
            ["alert_id"],
            ["alerts.alert_id"],
            name=op.f("fk_alert_actions_alert_id_alerts"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("action_id", name=op.f("pk_alert_actions")),
        sa.UniqueConstraint("action_checksum", name=op.f("uq_alert_actions_action_checksum")),
    )
    for column in ("alert_id", "kind", "occurred_at"):
        op.create_index(op.f(f"ix_alert_actions_{column}"), "alert_actions", [column])
    op.create_index(
        "ix_alert_actions_alert_occurred_at",
        "alert_actions",
        ["alert_id", "occurred_at"],
    )


def downgrade() -> None:
    op.drop_table("alert_actions")
    op.drop_table("alert_inbox_states")
