"""Create monitoring metric and recommendation tables."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260824_0002"
down_revision: str | None = "20260822_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "system_metric_samples",
        sa.Column(
            "sample_id",
            sa.String(length=100),
            nullable=False,
        ),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "metric_name",
            sa.String(length=100),
            nullable=False,
        ),
        sa.Column(
            "source",
            sa.String(length=50),
            nullable=False,
        ),
        sa.Column(
            "unit",
            sa.String(length=30),
            nullable=False,
        ),
        sa.Column(
            "value",
            sa.Numeric(
                precision=30,
                scale=10,
            ),
            nullable=False,
        ),
        sa.Column(
            "window_seconds",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "observed_count",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "labels_json",
            sa.JSON(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "observed_count > 0",
            name=op.f("ck_system_metric_samples_observed_count_positive"),
        ),
        sa.CheckConstraint(
            "value >= 0",
            name=op.f("ck_system_metric_samples_value_non_negative"),
        ),
        sa.CheckConstraint(
            "window_seconds > 0",
            name=op.f("ck_system_metric_samples_window_seconds_positive"),
        ),
        sa.PrimaryKeyConstraint(
            "sample_id",
            name=op.f("pk_system_metric_samples"),
        ),
    )

    op.create_index(
        op.f("ix_system_metric_samples_recorded_at"),
        "system_metric_samples",
        ["recorded_at"],
    )

    op.create_index(
        op.f("ix_system_metric_samples_metric_name"),
        "system_metric_samples",
        ["metric_name"],
    )

    op.create_index(
        op.f("ix_system_metric_samples_source"),
        "system_metric_samples",
        ["source"],
    )

    op.create_index(
        "ix_system_metric_samples_metric_recorded_at",
        "system_metric_samples",
        [
            "metric_name",
            "recorded_at",
        ],
    )

    op.create_index(
        "ix_system_metric_samples_source_recorded_at",
        "system_metric_samples",
        [
            "source",
            "recorded_at",
        ],
    )

    op.create_table(
        "architecture_recommendations",
        sa.Column(
            "recommendation_id",
            sa.String(length=100),
            nullable=False,
        ),
        sa.Column(
            "candidate",
            sa.String(length=50),
            nullable=False,
        ),
        sa.Column(
            "severity",
            sa.String(length=30),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=30),
            nullable=False,
        ),
        sa.Column(
            "first_detected_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "last_detected_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "payload_json",
            sa.Text(),
            nullable=False,
        ),
        sa.CheckConstraint(
            ("candidate IN ('postgresql_tuning', 'redis', 'timescaledb', 'clickhouse')"),
            name=op.f("ck_architecture_recommendations_candidate_supported"),
        ),
        sa.CheckConstraint(
            ("last_detected_at >= first_detected_at"),
            name=op.f("ck_architecture_recommendations_detection_time_order"),
        ),
        sa.CheckConstraint(
            ("severity IN ('info', 'warning', 'critical')"),
            name=op.f("ck_architecture_recommendations_severity_supported"),
        ),
        sa.CheckConstraint(
            ("status IN ('active', 'resolved', 'dismissed')"),
            name=op.f("ck_architecture_recommendations_status_supported"),
        ),
        sa.PrimaryKeyConstraint(
            "recommendation_id",
            name=op.f("pk_architecture_recommendations"),
        ),
    )

    op.create_index(
        op.f("ix_architecture_recommendations_candidate"),
        "architecture_recommendations",
        ["candidate"],
    )

    op.create_index(
        op.f("ix_architecture_recommendations_status"),
        "architecture_recommendations",
        ["status"],
    )

    op.create_index(
        op.f("ix_architecture_recommendations_last_detected_at"),
        "architecture_recommendations",
        ["last_detected_at"],
    )

    op.create_index(
        ("ix_architecture_recommendations_status_last_detected_at"),
        "architecture_recommendations",
        [
            "status",
            "last_detected_at",
        ],
    )


def downgrade() -> None:
    op.drop_index(
        ("ix_architecture_recommendations_status_last_detected_at"),
        table_name="architecture_recommendations",
    )

    op.drop_index(
        op.f("ix_architecture_recommendations_last_detected_at"),
        table_name="architecture_recommendations",
    )

    op.drop_index(
        op.f("ix_architecture_recommendations_status"),
        table_name="architecture_recommendations",
    )

    op.drop_index(
        op.f("ix_architecture_recommendations_candidate"),
        table_name="architecture_recommendations",
    )

    op.drop_table("architecture_recommendations")

    op.drop_index(
        "ix_system_metric_samples_source_recorded_at",
        table_name="system_metric_samples",
    )

    op.drop_index(
        "ix_system_metric_samples_metric_recorded_at",
        table_name="system_metric_samples",
    )

    op.drop_index(
        op.f("ix_system_metric_samples_source"),
        table_name="system_metric_samples",
    )

    op.drop_index(
        op.f("ix_system_metric_samples_metric_name"),
        table_name="system_metric_samples",
    )

    op.drop_index(
        op.f("ix_system_metric_samples_recorded_at"),
        table_name="system_metric_samples",
    )

    op.drop_table("system_metric_samples")
