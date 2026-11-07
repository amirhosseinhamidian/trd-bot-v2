from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal
from typing import Final, TypeVar, cast

from pydantic import JsonValue
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import InstrumentedAttribute, Session

from trd_bot.db.models import (
    DecisionCandidateRankingRow,
    DecisionEvaluationIntentRow,
    DecisionRiskGateRow,
    MarketRegimeAssessmentRow,
)
from trd_bot.integration.nexora.snapshots import (
    SnapshotProtocolError,
    SnapshotRecord,
    normalize_database_timestamp,
)

MARKET_CONTEXT: Final = "market_context"
DECISION_EVALUATION: Final = "decision_evaluation"
CANDIDATE: Final = "candidate"
RISK_GATE: Final = "risk_gate"
DECISION_SNAPSHOT_RESOURCE_TYPES: Final = (
    MARKET_CONTEXT,
    DECISION_EVALUATION,
    CANDIDATE,
    RISK_GATE,
)
RESOURCE_SCHEMA_VERSIONS: Final = {
    MARKET_CONTEXT: "trd-bot-market-context-v1",
    DECISION_EVALUATION: "trd-bot-decision-evaluation-v1",
    CANDIDATE: "trd-bot-candidate-v1",
    RISK_GATE: "trd-bot-risk-gate-v1",
}
_RowT = TypeVar("_RowT")


def _canonical_timestamp(value: datetime) -> str:
    normalized = normalize_database_timestamp(value)
    return normalized.isoformat(timespec="microseconds").replace("+00:00", "Z")


def _sort_key(observed_at: datetime, resource_id: str) -> str:
    return f"{_canonical_timestamp(observed_at)}|{resource_id}"


def _parse_boundary(value: str) -> datetime:
    try:
        boundary = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise SnapshotProtocolError("decision snapshot boundary is invalid") from error
    normalized = boundary.astimezone(UTC)
    if _canonical_timestamp(normalized) != value:
        raise SnapshotProtocolError("decision snapshot boundary is not canonical")
    return normalized


def _parse_after_sort_key(value: str) -> tuple[datetime, str]:
    timestamp, separator, resource_id = value.partition("|")
    if not separator or not resource_id:
        raise SnapshotProtocolError("decision snapshot sort key is invalid")
    return _parse_boundary(timestamp), resource_id


def _loaded_payload(payload_json: str) -> dict[str, JsonValue]:
    loaded = json.loads(payload_json)
    if not isinstance(loaded, dict):
        raise SnapshotProtocolError("decision snapshot payload must be an object")
    return cast(dict[str, JsonValue], loaded)


def _decimal(value: Decimal) -> str:
    return format(value, "f")


class DecisionSnapshotResourceReader:
    """Read immutable Market Context and Decision Intelligence evidence."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def capture_boundary(self, *, resource_type: str, captured_at: datetime) -> str:
        self._require_resource_type(resource_type)
        return _canonical_timestamp(captured_at)

    def get_record(self, *, resource_type: str, resource_id: str) -> SnapshotRecord | None:
        """Resolve one immutable resource for command source-evidence validation."""

        self._require_resource_type(resource_type)
        if resource_type == MARKET_CONTEXT:
            context = self._session.get(MarketRegimeAssessmentRow, resource_id)
            if context is None:
                return None
            return self._record(
                resource_type=resource_type,
                resource_id=context.assessment_id,
                observed_at=context.assessed_at,
                payload=self._market_context_payload(context),
            )
        if resource_type == DECISION_EVALUATION:
            evaluation = self._session.get(DecisionEvaluationIntentRow, resource_id)
            if evaluation is None:
                return None
            return self._record(
                resource_type=resource_type,
                resource_id=evaluation.evaluation_id,
                observed_at=evaluation.requested_at,
                payload=self._decision_evaluation_payload(evaluation),
            )
        if resource_type == CANDIDATE:
            candidate = self._session.get(DecisionCandidateRankingRow, resource_id)
            if candidate is None:
                return None
            return self._record(
                resource_type=resource_type,
                resource_id=candidate.evaluation_id,
                observed_at=candidate.ranked_at,
                payload=self._candidate_payload(candidate),
            )
        risk_gate = self._session.get(DecisionRiskGateRow, resource_id)
        if risk_gate is None:
            return None
        return self._record(
            resource_type=resource_type,
            resource_id=risk_gate.evaluation_id,
            observed_at=risk_gate.evaluated_at,
            payload=self._risk_gate_payload(risk_gate),
        )

    def list_records(
        self,
        *,
        resource_type: str,
        boundary_key: str,
        after_sort_key: str | None,
        limit: int,
    ) -> Sequence[SnapshotRecord]:
        self._require_resource_type(resource_type)
        if limit < 1:
            raise SnapshotProtocolError("decision snapshot read limit must be positive")
        boundary = _parse_boundary(boundary_key)
        after = None if after_sort_key is None else _parse_after_sort_key(after_sort_key)
        if resource_type == MARKET_CONTEXT:
            contexts = self._page_rows(
                MarketRegimeAssessmentRow,
                timestamp=MarketRegimeAssessmentRow.assessed_at,
                identity=MarketRegimeAssessmentRow.assessment_id,
                boundary=boundary,
                after=after,
                limit=limit,
            )
            return tuple(
                self._record(
                    resource_type=resource_type,
                    resource_id=row.assessment_id,
                    observed_at=row.assessed_at,
                    payload=self._market_context_payload(row),
                )
                for row in contexts
            )
        if resource_type == DECISION_EVALUATION:
            evaluations = self._page_rows(
                DecisionEvaluationIntentRow,
                timestamp=DecisionEvaluationIntentRow.requested_at,
                identity=DecisionEvaluationIntentRow.evaluation_id,
                boundary=boundary,
                after=after,
                limit=limit,
            )
            return tuple(
                self._record(
                    resource_type=resource_type,
                    resource_id=row.evaluation_id,
                    observed_at=row.requested_at,
                    payload=self._decision_evaluation_payload(row),
                )
                for row in evaluations
            )
        if resource_type == CANDIDATE:
            candidates = self._page_rows(
                DecisionCandidateRankingRow,
                timestamp=DecisionCandidateRankingRow.ranked_at,
                identity=DecisionCandidateRankingRow.evaluation_id,
                boundary=boundary,
                after=after,
                limit=limit,
            )
            return tuple(
                self._record(
                    resource_type=resource_type,
                    resource_id=row.evaluation_id,
                    observed_at=row.ranked_at,
                    payload=self._candidate_payload(row),
                )
                for row in candidates
            )
        risk_gates = self._page_rows(
            DecisionRiskGateRow,
            timestamp=DecisionRiskGateRow.evaluated_at,
            identity=DecisionRiskGateRow.evaluation_id,
            boundary=boundary,
            after=after,
            limit=limit,
        )
        return tuple(
            self._record(
                resource_type=resource_type,
                resource_id=row.evaluation_id,
                observed_at=row.evaluated_at,
                payload=self._risk_gate_payload(row),
            )
            for row in risk_gates
        )

    def _record(
        self,
        *,
        resource_type: str,
        resource_id: str,
        observed_at: datetime,
        payload: dict[str, JsonValue],
    ) -> SnapshotRecord:
        normalized = normalize_database_timestamp(observed_at)
        schema_version = RESOURCE_SCHEMA_VERSIONS[resource_type]
        return SnapshotRecord(
            resource_type=resource_type,
            resource_id=resource_id,
            resource_schema_version=schema_version,
            observed_at=normalized,
            sort_key=_sort_key(normalized, resource_id),
            payload={"resource_schema_version": schema_version, **payload},
        )

    @staticmethod
    def _market_context_payload(row: MarketRegimeAssessmentRow) -> dict[str, JsonValue]:
        return {
            "assessment_id": row.assessment_id,
            "record_schema_version": row.schema_version,
            "manifest_id": row.manifest_id,
            "feature_snapshot_id": row.feature_snapshot_id,
            "source": row.source,
            "base_asset": row.base_asset,
            "quote_asset": row.quote_asset,
            "market_type": row.market_type,
            "as_of": _canonical_timestamp(row.as_of),
            "input_checksum": row.input_checksum,
            "feature_set_version": row.feature_set_version,
            "feature_set_checksum": row.feature_set_checksum,
            "feature_snapshot_checksum": row.feature_snapshot_checksum,
            "algorithm_version": row.algorithm_version,
            "status": row.status,
            "trend": row.trend,
            "volatility": row.volatility,
            "confidence": _decimal(row.confidence),
            "evidence_count": row.evidence_count,
            "issue_count": row.issue_count,
            "assessed_at": _canonical_timestamp(row.assessed_at),
            "expires_at": _canonical_timestamp(row.expires_at),
            "record": _loaded_payload(row.payload_json),
            "offline_only": True,
            "external_order_submission_allowed": False,
        }

    @staticmethod
    def _decision_evaluation_payload(
        row: DecisionEvaluationIntentRow,
    ) -> dict[str, JsonValue]:
        return {
            "evaluation_id": row.evaluation_id,
            "record_schema_version": row.schema_version,
            "stage": row.stage,
            "mode": row.mode,
            "dataset_id": row.dataset_id,
            "dataset_reference_id": row.dataset_reference_id,
            "dataset_reference_checksum": row.dataset_reference_checksum,
            "strategy_reference_id": row.strategy_reference_id,
            "strategy_name": row.strategy_name,
            "strategy_version": row.strategy_version,
            "strategy_behavior_fingerprint": row.strategy_behavior_fingerprint,
            "strategy_reference_checksum": row.strategy_reference_checksum,
            "market_context_reference_id": row.market_context_reference_id,
            "market_context_assessment_id": row.market_context_assessment_id,
            "market_context_reference_checksum": row.market_context_reference_checksum,
            "policy_id": row.policy_id,
            "policy_version": row.policy_version,
            "policy_definition_checksum": row.policy_definition_checksum,
            "source": row.source,
            "base_asset": row.base_asset,
            "quote_asset": row.quote_asset,
            "market_type": row.market_type,
            "timeframe": row.timeframe,
            "requested_at": _canonical_timestamp(row.requested_at),
            "offline_only": row.offline_only,
            "external_order_submission_allowed": row.external_order_submission_allowed,
            "intent_checksum": row.intent_checksum,
            "record": _loaded_payload(row.payload_json),
        }

    @staticmethod
    def _candidate_payload(row: DecisionCandidateRankingRow) -> dict[str, JsonValue]:
        return {
            "evaluation_id": row.evaluation_id,
            "outcome_id": row.outcome_id,
            "record_schema_version": row.schema_version,
            "policy_version": row.policy_version,
            "policy_checksum": row.policy_checksum,
            "disposition": row.disposition,
            "source_signal_count": row.source_signal_count,
            "candidate_count": row.candidate_count,
            "excluded_signal_count": row.excluded_signal_count,
            "top_candidate_id": row.top_candidate_id,
            "ranked_at": _canonical_timestamp(row.ranked_at),
            "offline_only": row.offline_only,
            "external_order_submission_allowed": row.external_order_submission_allowed,
            "record_checksum": row.record_checksum,
            "record": _loaded_payload(row.payload_json),
        }

    @staticmethod
    def _risk_gate_payload(row: DecisionRiskGateRow) -> dict[str, JsonValue]:
        return {
            "evaluation_id": row.evaluation_id,
            "outcome_id": row.outcome_id,
            "record_schema_version": row.schema_version,
            "candidate_ranking_checksum": row.candidate_ranking_checksum,
            "policy_version": row.policy_version,
            "policy_checksum": row.policy_checksum,
            "disposition": row.disposition,
            "decision": row.decision,
            "assessment_id": row.assessment_id,
            "assessment_checksum": row.assessment_checksum,
            "approved_candidate_id": row.approved_candidate_id,
            "has_position_sizing": row.has_position_sizing,
            "evaluated_at": _canonical_timestamp(row.evaluated_at),
            "offline_only": row.offline_only,
            "external_order_submission_allowed": row.external_order_submission_allowed,
            "record_checksum": row.record_checksum,
            "record": _loaded_payload(row.payload_json),
        }

    def _page_rows(
        self,
        model: type[_RowT],
        *,
        timestamp: InstrumentedAttribute[datetime],
        identity: InstrumentedAttribute[str],
        boundary: datetime,
        after: tuple[datetime, str] | None,
        limit: int,
    ) -> Sequence[_RowT]:
        statement = select(model).where(timestamp <= boundary)
        if after is not None:
            after_timestamp, after_identity = after
            statement = statement.where(
                or_(
                    timestamp > after_timestamp,
                    and_(timestamp == after_timestamp, identity > after_identity),
                )
            )
        return self._session.scalars(
            statement.order_by(timestamp.asc(), identity.asc()).limit(limit)
        ).all()

    @staticmethod
    def _require_resource_type(resource_type: str) -> None:
        if resource_type not in DECISION_SNAPSHOT_RESOURCE_TYPES:
            raise SnapshotProtocolError("snapshot resource type is not available in this stage")
