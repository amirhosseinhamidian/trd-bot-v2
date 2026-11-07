from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from trd_bot.db.models import DecisionEvaluationIntentRow, NexoraDecisionReviewRow
from trd_bot.integration.nexora.decision_reviews import (
    CommandReceipt,
    DecisionReviewCommand,
    decision_review_command_id,
)
from trd_bot.integration.nexora.decision_snapshots import (
    DECISION_EVALUATION,
    DecisionSnapshotResourceReader,
)
from trd_bot.integration.nexora.snapshots import normalize_database_timestamp


class DecisionReviewError(ValueError):
    """Base error for rejected Nexora decision-review commands."""


class DecisionReviewIdempotencyConflictError(DecisionReviewError):
    pass


class DecisionReviewSourceEvidenceError(DecisionReviewError):
    pass


class SqlAlchemyNexoraDecisionReviewStore:
    """Persist idempotent Paper/Shadow feedback without authorizing execution."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def submit(
        self,
        *,
        command: DecisionReviewCommand,
        idempotency_key: str,
        correlation_id: UUID,
        accepted_at: datetime,
        source_version: str,
    ) -> CommandReceipt:
        if not 16 <= len(idempotency_key) <= 160 or idempotency_key != idempotency_key.strip():
            raise DecisionReviewError("Idempotency-Key must contain 16 to 160 canonical characters")
        normalized_accepted_at = normalize_database_timestamp(accepted_at)
        if normalized_accepted_at < command.reviewed_at:
            raise DecisionReviewSourceEvidenceError("reviewed_at cannot be in the future")
        existing = self._by_idempotency_key(idempotency_key)
        if existing is not None:
            return self._replayed_receipt(
                existing=existing,
                command=command,
                correlation_id=correlation_id,
            )

        self._validate_source_evidence(command=command, source_version=source_version)
        evidence = command.evidence
        row = NexoraDecisionReviewRow(
            command_id=decision_review_command_id(idempotency_key),
            idempotency_key=idempotency_key,
            decision_id=command.decision_id,
            command_schema_version=command.schema_version,
            command_type=command.command_type,
            action=command.action,
            portfolio_mode=command.portfolio_mode,
            reviewed_at=command.reviewed_at,
            reason=command.reason,
            source_reference_schema_version=evidence.schema_version,
            source_product=evidence.source_product,
            source_version=evidence.source_version,
            source_resource_type=evidence.resource_type,
            source_resource_id=evidence.resource_id,
            source_resource_schema_version=evidence.resource_schema_version,
            source_observed_at=evidence.observed_at,
            source_evidence_checksum=evidence.checksum,
            request_checksum=command.request_checksum,
            correlation_id=str(correlation_id),
            accepted_at=normalized_accepted_at,
            offline_only=True,
            execution_authorization=False,
            creates_live_order=False,
            posts_portfolio_transaction=False,
            request_json=command.model_dump_json(),
        )
        try:
            with self._session.begin_nested():
                self._session.add(row)
                self._session.flush()
        except IntegrityError:
            raced = self._by_idempotency_key(idempotency_key)
            if raced is None:
                raise
            return self._replayed_receipt(
                existing=raced,
                command=command,
                correlation_id=correlation_id,
            )
        return self._receipt(row=row, status="accepted", correlation_id=correlation_id)

    def _validate_source_evidence(
        self, *, command: DecisionReviewCommand, source_version: str
    ) -> None:
        evaluation = self._session.get(DecisionEvaluationIntentRow, command.decision_id)
        if evaluation is None:
            raise DecisionReviewSourceEvidenceError("source decision evidence was not found")
        if evaluation.mode != command.portfolio_mode:
            raise DecisionReviewSourceEvidenceError("portfolio mode does not match source evidence")
        record = DecisionSnapshotResourceReader(self._session).get_record(
            resource_type=DECISION_EVALUATION,
            resource_id=command.decision_id,
        )
        if record is None:
            raise DecisionReviewSourceEvidenceError("source decision evidence was not found")
        expected = record.to_item(source_version=source_version).source_reference
        if command.evidence != expected:
            raise DecisionReviewSourceEvidenceError(
                "source evidence reference or checksum does not match immutable evidence"
            )

    def _by_idempotency_key(self, idempotency_key: str) -> NexoraDecisionReviewRow | None:
        return self._session.scalar(
            select(NexoraDecisionReviewRow).where(
                NexoraDecisionReviewRow.idempotency_key == idempotency_key
            )
        )

    def _replayed_receipt(
        self,
        *,
        existing: NexoraDecisionReviewRow,
        command: DecisionReviewCommand,
        correlation_id: UUID,
    ) -> CommandReceipt:
        if existing.request_checksum != command.request_checksum:
            raise DecisionReviewIdempotencyConflictError(
                "Idempotency-Key already belongs to a different command payload"
            )
        return self._receipt(row=existing, status="duplicate", correlation_id=correlation_id)

    @staticmethod
    def _receipt(
        *,
        row: NexoraDecisionReviewRow,
        status: Literal["accepted", "duplicate"],
        correlation_id: UUID,
    ) -> CommandReceipt:
        return CommandReceipt.model_validate(
            {
                "schema_version": "nexora-command-receipt-v1",
                "command_id": row.command_id,
                "command_type": row.command_type,
                "status": status,
                "idempotency_key": row.idempotency_key,
                "correlation_id": correlation_id,
                "accepted_at": normalize_database_timestamp(row.accepted_at),
            }
        )
