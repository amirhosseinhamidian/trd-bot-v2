from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from trd_bot.alerts import (
    AlertEvaluationDisposition,
    AlertEvaluationRecord,
    AlertExpiryRecord,
    AlertExpirySummary,
    AlertExpirySweepResult,
    AlertPublicationDecision,
    AlertPublicationPolicy,
    AlertRuleDefinition,
    AlertSuppressionReason,
    MarketContextAlertSourceReference,
)
from trd_bot.db.models import (
    AlertExpiryRecordRow,
    AlertInboxStateRow,
    AlertPublicationDecisionRow,
    AlertPublicationPolicyRow,
    AlertRow,
    MarketRegimeAssessmentRow,
)


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


class SqlAlchemyAlertPublicationRepository:
    """Persist publication preferences and enforce them against durable history."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_policy(self) -> AlertPublicationPolicy:
        row = self._session.scalar(
            select(AlertPublicationPolicyRow)
            .order_by(AlertPublicationPolicyRow.policy_version.desc())
            .limit(1)
        )
        return AlertPublicationPolicy.default() if row is None else self._policy_from_row(row)

    def update_policy(
        self,
        *,
        quiet_hours_enabled: bool,
        quiet_hours_start_minute: int,
        quiet_hours_end_minute: int,
        timezone_name: str,
        critical_bypass_quiet_hours: bool,
        updated_by: str,
        updated_at: datetime,
    ) -> AlertPublicationPolicy:
        latest = self._session.scalar(
            select(AlertPublicationPolicyRow)
            .order_by(AlertPublicationPolicyRow.policy_version.desc())
            .limit(1)
            .with_for_update()
        )
        policy = AlertPublicationPolicy.build(
            policy_version=1 if latest is None else latest.policy_version + 1,
            quiet_hours_enabled=quiet_hours_enabled,
            quiet_hours_start_minute=quiet_hours_start_minute,
            quiet_hours_end_minute=quiet_hours_end_minute,
            timezone_name=timezone_name,
            critical_bypass_quiet_hours=critical_bypass_quiet_hours,
            updated_by=updated_by,
            updated_at=_utc(updated_at),
        )
        self._session.add(
            AlertPublicationPolicyRow(
                policy_id=policy.policy_id,
                policy_version=policy.policy_version,
                schema_version=policy.schema_version,
                quiet_hours_enabled=policy.quiet_hours_enabled,
                quiet_hours_start_minute=policy.quiet_hours_start_minute,
                quiet_hours_end_minute=policy.quiet_hours_end_minute,
                timezone_name=policy.timezone_name,
                critical_bypass_quiet_hours=policy.critical_bypass_quiet_hours,
                updated_by=policy.updated_by,
                updated_at=policy.updated_at,
                policy_checksum=policy.policy_checksum,
                payload_json=policy.model_dump_json(),
            )
        )
        self._session.commit()
        return policy

    def evaluate(
        self,
        *,
        evaluation_id: str,
        rule: AlertRuleDefinition,
        source: MarketContextAlertSourceReference,
        evaluated_at: datetime,
        policy: AlertPublicationPolicy | None = None,
    ) -> AlertPublicationDecision:
        evaluated = _utc(evaluated_at)
        applied_policy = policy or self.get_policy()
        reasons: set[AlertSuppressionReason] = set()
        blocked_until: list[datetime] = []

        if source.expires_at <= evaluated:
            reasons.add(AlertSuppressionReason.SOURCE_EXPIRED)

        quiet_end = applied_policy.quiet_hours_end(evaluated_at=evaluated)
        if applied_policy.suppresses(severity=rule.severity, evaluated_at=evaluated):
            reasons.add(AlertSuppressionReason.QUIET_HOURS)
            if quiet_end is not None:
                blocked_until.append(quiet_end)

        previous = self._latest_stream_alert(rule=rule, source=source, evaluated_at=evaluated)
        previous_alert_id: str | None = None
        if previous is not None:
            alert, state = previous
            duplicate_until = _utc(alert.created_at) + timedelta(
                seconds=rule.deduplication_window_seconds
            )
            cooldown_until = _utc(alert.created_at) + timedelta(seconds=rule.cooldown_seconds)
            if duplicate_until > evaluated:
                reasons.add(AlertSuppressionReason.DUPLICATE)
                blocked_until.append(duplicate_until)
            if rule.cooldown_seconds and cooldown_until > evaluated:
                reasons.add(AlertSuppressionReason.COOLDOWN_ACTIVE)
                blocked_until.append(cooldown_until)
            if (
                state is not None
                and state.snoozed_until is not None
                and _utc(state.snoozed_until) > evaluated
                and _utc(alert.expires_at) > evaluated
            ):
                reasons.add(AlertSuppressionReason.SNOOZED)
                blocked_until.append(_utc(state.snoozed_until))
            if reasons.intersection(
                {
                    AlertSuppressionReason.DUPLICATE,
                    AlertSuppressionReason.COOLDOWN_ACTIVE,
                    AlertSuppressionReason.SNOOZED,
                }
            ):
                previous_alert_id = alert.alert_id

        return AlertPublicationDecision.build(
            evaluation_id=evaluation_id,
            policy=applied_policy,
            suppression_reasons=tuple(sorted(reasons, key=lambda item: item.value)),
            previous_alert_id=previous_alert_id,
            blocked_until=max(blocked_until) if blocked_until else None,
            evaluated_at=evaluated,
        )

    def stage_decision(
        self,
        decision: AlertPublicationDecision,
        *,
        evaluation: AlertEvaluationRecord,
    ) -> tuple[AlertPublicationDecision, bool]:
        existing = self.get_decision(evaluation.evaluation_id)
        if existing is not None:
            if existing != decision:
                raise ValueError("alert publication decision exists with different content")
            return existing, False
        if decision.evaluation_id != evaluation.evaluation_id:
            raise ValueError("publication decision does not match its evaluation")
        if decision.allowed != (evaluation.disposition is AlertEvaluationDisposition.PUBLISHED):
            raise ValueError("publication decision outcome does not match its evaluation")
        if not decision.allowed and decision.suppression_reasons != evaluation.suppression_reasons:
            raise ValueError("publication decision reasons do not match its evaluation")

        self._session.add(
            AlertPublicationDecisionRow(
                decision_id=decision.decision_id,
                schema_version=decision.schema_version,
                evaluation_id=decision.evaluation_id,
                policy_id=decision.policy_id,
                policy_version=decision.policy_version,
                policy_checksum=decision.policy_checksum,
                allowed=decision.allowed,
                suppression_reason_count=len(decision.suppression_reasons),
                previous_alert_id=decision.previous_alert_id,
                blocked_until=decision.blocked_until,
                evaluated_at=decision.evaluated_at,
                decision_checksum=decision.decision_checksum,
                payload_json=decision.model_dump_json(),
            )
        )
        self._session.flush()
        return decision, True

    def get_decision(self, evaluation_id: str) -> AlertPublicationDecision | None:
        row = self._session.scalar(
            select(AlertPublicationDecisionRow).where(
                AlertPublicationDecisionRow.evaluation_id == evaluation_id
            )
        )
        return (
            None if row is None else AlertPublicationDecision.model_validate_json(row.payload_json)
        )

    def expiry_summary(self, *, evaluated_at: datetime) -> AlertExpirySummary:
        evaluated = _utc(evaluated_at)
        expired_total = int(
            self._session.scalar(
                select(func.count()).select_from(AlertRow).where(AlertRow.expires_at <= evaluated)
            )
            or 0
        )
        materialized_total = int(
            self._session.scalar(
                select(func.count())
                .select_from(AlertExpiryRecordRow)
                .join(AlertRow, AlertRow.alert_id == AlertExpiryRecordRow.alert_id)
                .where(AlertRow.expires_at <= evaluated)
            )
            or 0
        )
        return AlertExpirySummary(
            evaluated_at=evaluated,
            expired_total=expired_total,
            materialized_total=materialized_total,
            pending_total=expired_total - materialized_total,
        )

    def sweep_expired(
        self,
        *,
        evaluated_at: datetime,
        recorded_by: str,
        limit: int,
    ) -> AlertExpirySweepResult:
        if limit <= 0 or limit > 1000:
            raise ValueError("alert expiry sweep limit must be between 1 and 1000")
        evaluated = _utc(evaluated_at)
        rows = self._session.scalars(
            select(AlertRow)
            .outerjoin(
                AlertExpiryRecordRow,
                AlertExpiryRecordRow.alert_id == AlertRow.alert_id,
            )
            .where(
                AlertRow.expires_at <= evaluated,
                AlertExpiryRecordRow.alert_id.is_(None),
            )
            .order_by(AlertRow.expires_at, AlertRow.alert_id)
            .limit(limit)
            .with_for_update()
        ).all()
        records = tuple(
            AlertExpiryRecord.build(
                alert_id=row.alert_id,
                expired_at=_utc(row.expires_at),
                recorded_at=evaluated,
                recorded_by=recorded_by,
            )
            for row in rows
        )
        for record in records:
            self._session.add(
                AlertExpiryRecordRow(
                    expiry_id=record.expiry_id,
                    schema_version=record.schema_version,
                    alert_id=record.alert_id,
                    expired_at=record.expired_at,
                    recorded_at=record.recorded_at,
                    recorded_by=record.recorded_by,
                    record_checksum=record.record_checksum,
                    payload_json=record.model_dump_json(),
                )
            )
        self._session.commit()
        remaining = self.expiry_summary(evaluated_at=evaluated).pending_total
        return AlertExpirySweepResult(
            evaluated_at=evaluated,
            recorded_by=recorded_by,
            recorded_count=len(records),
            expiry_ids=tuple(record.expiry_id for record in records),
            remaining_pending=remaining,
        )

    def _latest_stream_alert(
        self,
        *,
        rule: AlertRuleDefinition,
        source: MarketContextAlertSourceReference,
        evaluated_at: datetime,
    ) -> tuple[AlertRow, AlertInboxStateRow | None] | None:
        row = self._session.execute(
            select(AlertRow, AlertInboxStateRow)
            .join(
                MarketRegimeAssessmentRow,
                MarketRegimeAssessmentRow.assessment_id == AlertRow.source_event_id,
            )
            .outerjoin(AlertInboxStateRow, AlertInboxStateRow.alert_id == AlertRow.alert_id)
            .where(
                AlertRow.rule_id == rule.rule_id,
                AlertRow.created_at <= evaluated_at,
                MarketRegimeAssessmentRow.source == source.source,
                MarketRegimeAssessmentRow.base_asset == source.pair.base_asset,
                MarketRegimeAssessmentRow.quote_asset == source.pair.quote_asset,
                MarketRegimeAssessmentRow.market_type == source.pair.market_type.value,
            )
            .order_by(AlertRow.created_at.desc(), AlertRow.alert_id.desc())
            .limit(1)
        ).one_or_none()
        return None if row is None else (row[0], row[1])

    @staticmethod
    def _policy_from_row(row: AlertPublicationPolicyRow) -> AlertPublicationPolicy:
        return AlertPublicationPolicy.model_validate_json(row.payload_json)
