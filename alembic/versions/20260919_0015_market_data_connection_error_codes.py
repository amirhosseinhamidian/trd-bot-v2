"""Add stable market-data connection health failure codes.

Revision ID: 20260919_0015
Revises: 20260831_0014
Create Date: 2026-09-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260919_0015"
down_revision: str | None = "20260831_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("market_data_connections") as batch_op:
        batch_op.add_column(
            sa.Column("last_error_code", sa.String(length=100), nullable=True),
        )

    op.execute(
        "UPDATE market_data_connections "
        "SET last_error_code = 'provider_request_failed' "
        "WHERE health_status = 'unhealthy'"
    )

    with op.batch_alter_table("market_data_connections") as batch_op:
        batch_op.drop_constraint(
            op.f("ck_market_data_connections_health_details_consistent"),
            type_="check",
        )
        batch_op.create_check_constraint(
            op.f("ck_market_data_connections_health_details_consistent"),
            "(health_status = 'untested' AND last_tested_at IS NULL "
            "AND last_error_code IS NULL AND last_error IS NULL) "
            "OR (health_status = 'healthy' AND last_tested_at IS NOT NULL "
            "AND last_error_code IS NULL AND last_error IS NULL) "
            "OR (health_status = 'unhealthy' AND last_tested_at IS NOT NULL "
            "AND last_error_code IS NOT NULL AND last_error IS NOT NULL)",
        )


def downgrade() -> None:
    with op.batch_alter_table("market_data_connections") as batch_op:
        batch_op.drop_constraint(
            op.f("ck_market_data_connections_health_details_consistent"),
            type_="check",
        )
        batch_op.create_check_constraint(
            op.f("ck_market_data_connections_health_details_consistent"),
            "(health_status = 'untested' AND last_tested_at IS NULL AND last_error IS NULL) "
            "OR (health_status = 'healthy' AND last_tested_at IS NOT NULL "
            "AND last_error IS NULL) "
            "OR (health_status = 'unhealthy' AND last_tested_at IS NOT NULL "
            "AND last_error IS NOT NULL)",
        )
        batch_op.drop_column("last_error_code")
