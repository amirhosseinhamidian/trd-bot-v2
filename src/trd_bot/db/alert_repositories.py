from sqlalchemy import select
from sqlalchemy.orm import Session

from trd_bot.alerts import (
    AlertDraft,
    AlertEvaluationDisposition,
    AlertEvaluationRecord,
    AlertRuleDefinition,
    AlertRuleReference,
    MarketContextAlertSourceReference,
)
from trd_bot.db.models import (
    AlertEvaluationRow,
    AlertRow,
    AlertRuleDefinitionRow,
    MarketRegimeAssessmentRow,
)
from trd_bot.market_context import MarketContextProductView, MarketRegimeAssessment


class SqlAlchemyAlertStore:
    """Stage immutable alert artifacts without owning caller transactions."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def stage_rule_definition(
        self,
        rule: AlertRuleDefinition,
    ) -> tuple[AlertRuleDefinition, bool]:
        existing = self.get_rule_definition(rule.rule_id, rule.rule_version)
        if existing is not None:
            if existing != rule:
                raise ValueError("alert rule version exists with different content")
            return existing, False

        by_checksum = self._get_rule_definition_by_checksum(rule.definition_checksum)
        if by_checksum is not None:
            if by_checksum != rule:
                raise ValueError("alert rule checksum belongs to another definition")
            return by_checksum, False

        latest = self.get_latest_rule_definition(rule.rule_id)
        if rule.rule_version == 1:
            if latest is not None:
                raise ValueError("first alert rule version conflicts with existing lineage")
        elif latest is None or latest.rule_version != rule.rule_version - 1:
            raise ValueError("alert rule version must extend its persisted immediate predecessor")

        self._session.add(
            AlertRuleDefinitionRow(
                rule_id=rule.rule_id,
                rule_version=rule.rule_version,
                schema_version=rule.schema_version,
                rule_key=rule.rule_key,
                source_kind=rule.source_kind.value,
                state=rule.state.value,
                severity=rule.severity.value,
                definition_checksum=rule.definition_checksum,
                payload_json=rule.model_dump_json(),
                created_at=rule.created_at,
            )
        )
        self._session.flush()
        return rule, True

    def get_rule_definition(
        self,
        rule_id: str,
        rule_version: int,
    ) -> AlertRuleDefinition | None:
        row = self._session.get(AlertRuleDefinitionRow, (rule_id, rule_version))
        return None if row is None else self._rule_from_row(row)

    def get_latest_rule_definition(self, rule_id: str) -> AlertRuleDefinition | None:
        row = self._session.scalar(
            select(AlertRuleDefinitionRow)
            .where(AlertRuleDefinitionRow.rule_id == rule_id)
            .order_by(AlertRuleDefinitionRow.rule_version.desc())
            .limit(1)
        )
        return None if row is None else self._rule_from_row(row)

    def stage_evaluation(
        self,
        evaluation: AlertEvaluationRecord,
        *,
        draft: AlertDraft | None = None,
    ) -> tuple[AlertEvaluationRecord, bool]:
        self._validate_evaluation_payload(evaluation, draft=draft)

        existing = self.get_evaluation(evaluation.evaluation_id)
        if existing is not None:
            if existing != evaluation:
                raise ValueError("alert evaluation ID exists with different content")
            self._validate_existing_alert(evaluation, draft=draft)
            return existing, False

        rule = self.get_rule_definition(
            evaluation.rule.rule_id,
            evaluation.rule.rule_version,
        )
        if rule is None:
            raise ValueError("alert evaluation rule version does not exist")
        if AlertRuleReference.from_definition(rule) != evaluation.rule:
            raise ValueError("alert evaluation does not match its persisted rule version")

        source_row = self._session.get(
            MarketRegimeAssessmentRow,
            evaluation.source.source_event_id,
        )
        if source_row is None:
            raise ValueError("alert evaluation source assessment does not exist")
        assessment = MarketRegimeAssessment.model_validate_json(source_row.payload_json)
        persisted_source = MarketContextAlertSourceReference.from_market_context_view(
            MarketContextProductView.from_assessment(
                assessment,
                evaluated_at=evaluation.evaluated_at,
            )
        )
        if persisted_source != evaluation.source:
            raise ValueError("alert evaluation source does not match persisted assessment")

        if draft is not None:
            deduplicated = self.get_alert_by_deduplication_key(draft.deduplication_key)
            if deduplicated is not None:
                raise ValueError("alert deduplication key already belongs to another evaluation")

        self._session.add(
            AlertEvaluationRow(
                evaluation_id=evaluation.evaluation_id,
                schema_version=evaluation.schema_version,
                rule_id=evaluation.rule.rule_id,
                rule_version=evaluation.rule.rule_version,
                source_kind=evaluation.source.source_kind.value,
                source_reference_id=evaluation.source.reference_id,
                source_event_id=evaluation.source.source_event_id,
                source_event_checksum=evaluation.source.source_event_checksum,
                disposition=evaluation.disposition.value,
                suppression_reason_count=len(evaluation.suppression_reasons),
                alert_id=evaluation.alert_id,
                evaluation_checksum=evaluation.evaluation_checksum,
                payload_json=evaluation.model_dump_json(),
                evaluated_at=evaluation.evaluated_at,
            )
        )
        self._session.flush()

        if draft is not None:
            self._session.add(
                AlertRow(
                    alert_id=draft.alert_id,
                    schema_version=draft.schema_version,
                    evaluation_id=evaluation.evaluation_id,
                    deduplication_key=draft.deduplication_key,
                    rule_id=draft.rule.rule_id,
                    rule_version=draft.rule.rule_version,
                    source_kind=draft.source.source_kind.value,
                    source_event_id=draft.source.source_event_id,
                    delivery_channel=draft.delivery_channel.value,
                    severity=draft.severity.value,
                    draft_checksum=draft.draft_checksum,
                    payload_json=draft.model_dump_json(),
                    created_at=draft.created_at,
                    expires_at=draft.expires_at,
                )
            )
            self._session.flush()
        return evaluation, True

    def get_evaluation(self, evaluation_id: str) -> AlertEvaluationRecord | None:
        row = self._session.get(AlertEvaluationRow, evaluation_id)
        return None if row is None else self._evaluation_from_row(row)

    def get_alert(self, alert_id: str) -> AlertDraft | None:
        row = self._session.get(AlertRow, alert_id)
        return None if row is None else self._alert_from_row(row)

    def get_alert_by_deduplication_key(self, deduplication_key: str) -> AlertDraft | None:
        row = self._session.scalar(
            select(AlertRow).where(AlertRow.deduplication_key == deduplication_key)
        )
        return None if row is None else self._alert_from_row(row)

    def _get_rule_definition_by_checksum(
        self,
        definition_checksum: str,
    ) -> AlertRuleDefinition | None:
        row = self._session.scalar(
            select(AlertRuleDefinitionRow).where(
                AlertRuleDefinitionRow.definition_checksum == definition_checksum
            )
        )
        return None if row is None else self._rule_from_row(row)

    def _validate_evaluation_payload(
        self,
        evaluation: AlertEvaluationRecord,
        *,
        draft: AlertDraft | None,
    ) -> None:
        if evaluation.disposition is AlertEvaluationDisposition.PUBLISHED:
            if draft is None:
                raise ValueError("published alert evaluation requires its draft")
            if AlertEvaluationRecord.published(draft) != evaluation:
                raise ValueError("published alert evaluation does not match its draft")
        elif draft is not None:
            raise ValueError("suppressed alert evaluation cannot persist a draft")

    def _validate_existing_alert(
        self,
        evaluation: AlertEvaluationRecord,
        *,
        draft: AlertDraft | None,
    ) -> None:
        if evaluation.disposition is AlertEvaluationDisposition.SUPPRESSED:
            return
        if draft is None or evaluation.alert_id is None:
            raise ValueError("published alert evaluation requires its persisted draft")
        existing_alert = self.get_alert(evaluation.alert_id)
        if existing_alert is None:
            raise ValueError("published alert evaluation is missing its persisted alert")
        if existing_alert != draft:
            raise ValueError("published alert exists with different content")

    @staticmethod
    def _rule_from_row(row: AlertRuleDefinitionRow) -> AlertRuleDefinition:
        return AlertRuleDefinition.model_validate_json(row.payload_json)

    @staticmethod
    def _evaluation_from_row(row: AlertEvaluationRow) -> AlertEvaluationRecord:
        return AlertEvaluationRecord.model_validate_json(row.payload_json)

    @staticmethod
    def _alert_from_row(row: AlertRow) -> AlertDraft:
        return AlertDraft.model_validate_json(row.payload_json)
