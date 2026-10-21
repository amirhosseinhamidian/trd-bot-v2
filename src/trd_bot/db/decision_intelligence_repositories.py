from sqlalchemy import func, select
from sqlalchemy.orm import Session

from trd_bot.db.models import (
    DatasetSnapshotRow,
    DecisionCandidateRankingRow,
    DecisionEvaluationIntentRow,
    DecisionPolicyDefinitionRow,
    DecisionPortfolioIntelligenceRow,
    DecisionRiskGateRow,
    DecisionStageOutcomeRow,
    DecisionStrategyEvaluationRow,
    MarketRegimeAssessmentRow,
)
from trd_bot.decision_intelligence import (
    DecisionCandidateRankingRecord,
    DecisionDatasetReference,
    DecisionDisposition,
    DecisionEvaluationIntent,
    DecisionMode,
    DecisionPolicyDefinition,
    DecisionPolicyReference,
    DecisionPortfolioIntelligenceRecord,
    DecisionRiskDecision,
    DecisionRiskGateRecord,
    DecisionStage,
    DecisionStageOutcome,
    MarketContextDecisionReference,
    StrategyEvaluationRecord,
    build_decision_evaluation_idempotency_key,
)
from trd_bot.market_context import MarketContextProductView, MarketRegimeAssessment
from trd_bot.research.datasets import DatasetSnapshot

_STAGE_ORDER = tuple(DecisionStage)


class SqlAlchemyDecisionIntelligenceStore:
    """Stage immutable Decision Intelligence evidence in caller-owned transactions."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def stage_policy_definition(
        self,
        policy: DecisionPolicyDefinition,
    ) -> tuple[DecisionPolicyDefinition, bool]:
        existing = self.get_policy_definition(policy.policy_id, policy.policy_version)
        if existing is not None:
            if existing != policy:
                raise ValueError("decision policy version exists with different content")
            return existing, False

        by_checksum = self._get_policy_definition_by_checksum(policy.definition_checksum)
        if by_checksum is not None:
            if by_checksum != policy:
                raise ValueError("decision policy checksum belongs to another definition")
            return by_checksum, False

        latest = self.get_latest_policy_definition(policy.policy_id)
        if policy.policy_version == 1:
            if latest is not None:
                raise ValueError("first decision policy version conflicts with existing lineage")
        elif latest is None or latest.policy_version != policy.policy_version - 1:
            raise ValueError(
                "decision policy version must extend its persisted immediate predecessor"
            )

        self._session.add(
            DecisionPolicyDefinitionRow(
                policy_id=policy.policy_id,
                policy_version=policy.policy_version,
                schema_version=policy.schema_version,
                policy_key=policy.policy_key,
                supersedes_version=policy.supersedes_version,
                state=policy.state.value,
                allowed_mode_count=len(policy.allowed_modes),
                offline_only=policy.offline_only,
                external_order_submission_allowed=(policy.external_order_submission_allowed),
                definition_checksum=policy.definition_checksum,
                payload_json=policy.model_dump_json(),
                created_at=policy.created_at,
            )
        )
        self._session.flush()
        return policy, True

    def get_policy_definition(
        self,
        policy_id: str,
        policy_version: int,
    ) -> DecisionPolicyDefinition | None:
        row = self._session.get(
            DecisionPolicyDefinitionRow,
            (policy_id, policy_version),
        )
        return None if row is None else self._policy_from_row(row)

    def get_latest_policy_definition(
        self,
        policy_id: str,
    ) -> DecisionPolicyDefinition | None:
        row = self._session.scalar(
            select(DecisionPolicyDefinitionRow)
            .where(DecisionPolicyDefinitionRow.policy_id == policy_id)
            .order_by(DecisionPolicyDefinitionRow.policy_version.desc())
            .limit(1)
        )
        return None if row is None else self._policy_from_row(row)

    def stage_evaluation_intent(
        self,
        intent: DecisionEvaluationIntent,
    ) -> tuple[DecisionEvaluationIntent, bool]:
        existing = self.get_evaluation_intent(intent.evaluation_id)
        if existing is not None:
            if existing != intent:
                raise ValueError("decision evaluation ID exists with different content")
            return existing, False

        idempotency_key = build_decision_evaluation_idempotency_key(intent)
        by_idempotency_key = self.get_evaluation_intent_by_idempotency_key(idempotency_key)
        if by_idempotency_key is not None:
            if by_idempotency_key != intent:
                raise ValueError("decision idempotency key belongs to another intent")
            return by_idempotency_key, False

        self._validate_policy_reference(intent)
        self._validate_dataset_reference(intent)
        self._validate_market_context_reference(intent)

        self._session.add(
            DecisionEvaluationIntentRow(
                evaluation_id=intent.evaluation_id,
                schema_version=intent.schema_version,
                stage=intent.stage.value,
                mode=intent.mode.value,
                dataset_id=intent.dataset.dataset_id,
                dataset_reference_id=intent.dataset.reference_id,
                dataset_reference_checksum=intent.dataset.reference_checksum,
                strategy_reference_id=intent.strategy.reference_id,
                strategy_name=intent.strategy.strategy_name,
                strategy_version=intent.strategy.strategy_version,
                strategy_behavior_fingerprint=intent.strategy.behavior_fingerprint,
                strategy_reference_checksum=intent.strategy.reference_checksum,
                market_context_reference_id=intent.market_context.reference_id,
                market_context_assessment_id=intent.market_context.assessment_id,
                market_context_reference_checksum=(intent.market_context.reference_checksum),
                policy_id=intent.policy.policy_id,
                policy_version=intent.policy.policy_version,
                policy_definition_checksum=intent.policy.definition_checksum,
                source=intent.dataset.source,
                base_asset=intent.dataset.pair.base_asset,
                quote_asset=intent.dataset.pair.quote_asset,
                market_type=intent.dataset.pair.market_type.value,
                timeframe=intent.dataset.timeframe.value,
                requested_at=intent.requested_at,
                offline_only=intent.offline_only,
                external_order_submission_allowed=(intent.external_order_submission_allowed),
                idempotency_key=idempotency_key,
                intent_checksum=intent.intent_checksum,
                payload_json=intent.model_dump_json(),
            )
        )
        self._session.flush()
        return intent, True

    def get_evaluation_intent(
        self,
        evaluation_id: str,
    ) -> DecisionEvaluationIntent | None:
        row = self._session.get(DecisionEvaluationIntentRow, evaluation_id)
        return None if row is None else self._intent_from_row(row)

    def list_evaluation_intents(
        self,
        *,
        strategy_name: str | None = None,
        strategy_version: str | None = None,
        mode: DecisionMode | None = None,
        stage: DecisionStage | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> tuple[DecisionEvaluationIntent, ...]:
        """List immutable evaluation intents newest first for read-only projections."""

        statement = select(DecisionEvaluationIntentRow)
        if strategy_name is not None:
            statement = statement.where(DecisionEvaluationIntentRow.strategy_name == strategy_name)
        if strategy_version is not None:
            statement = statement.where(
                DecisionEvaluationIntentRow.strategy_version == strategy_version
            )
        if mode is not None:
            statement = statement.where(DecisionEvaluationIntentRow.mode == mode.value)
        if stage is not None:
            statement = statement.join(
                DecisionStageOutcomeRow,
                DecisionStageOutcomeRow.evaluation_id == DecisionEvaluationIntentRow.evaluation_id,
            ).where(DecisionStageOutcomeRow.stage == stage.value)
        statement = statement.order_by(
            DecisionEvaluationIntentRow.requested_at.desc(),
            DecisionEvaluationIntentRow.evaluation_id.desc(),
        ).offset(offset)
        if limit is not None:
            statement = statement.limit(limit)

        rows = self._session.scalars(statement).all()
        return tuple(self._intent_from_row(row) for row in rows)

    def count_evaluation_intents(
        self,
        *,
        strategy_name: str | None = None,
        strategy_version: str | None = None,
        mode: DecisionMode | None = None,
        stage: DecisionStage | None = None,
    ) -> int:
        """Count immutable intents using the same SQL filters as the product projection."""

        statement = select(func.count()).select_from(DecisionEvaluationIntentRow)
        if strategy_name is not None:
            statement = statement.where(DecisionEvaluationIntentRow.strategy_name == strategy_name)
        if strategy_version is not None:
            statement = statement.where(
                DecisionEvaluationIntentRow.strategy_version == strategy_version
            )
        if mode is not None:
            statement = statement.where(DecisionEvaluationIntentRow.mode == mode.value)
        if stage is not None:
            statement = statement.join(
                DecisionStageOutcomeRow,
                DecisionStageOutcomeRow.evaluation_id == DecisionEvaluationIntentRow.evaluation_id,
            ).where(DecisionStageOutcomeRow.stage == stage.value)
        return int(self._session.scalar(statement) or 0)

    def get_evaluation_intent_by_idempotency_key(
        self,
        idempotency_key: str,
    ) -> DecisionEvaluationIntent | None:
        row = self._session.scalar(
            select(DecisionEvaluationIntentRow).where(
                DecisionEvaluationIntentRow.idempotency_key == idempotency_key
            )
        )
        return None if row is None else self._intent_from_row(row)

    def stage_outcome(
        self,
        outcome: DecisionStageOutcome,
    ) -> tuple[DecisionStageOutcome, bool]:
        existing = self.get_stage_outcome(
            outcome.evaluation_id,
            stage=outcome.stage,
        )
        if existing is not None:
            if existing != outcome:
                raise ValueError("decision stage outcome exists with different content")
            return existing, False

        intent = self.get_evaluation_intent(outcome.evaluation_id)
        if intent is None:
            raise ValueError("decision stage outcome intent does not exist")
        if outcome.evaluated_at < intent.requested_at:
            raise ValueError("decision stage outcome predates its evaluation intent")

        stage_index = _STAGE_ORDER.index(outcome.stage)
        if stage_index > 0:
            predecessor_stage = _STAGE_ORDER[stage_index - 1]
            predecessor = self.get_stage_outcome(
                outcome.evaluation_id,
                stage=predecessor_stage,
            )
            if predecessor is None:
                raise ValueError("decision stage outcome requires its immediate predecessor")
            if predecessor.disposition is not DecisionDisposition.ACCEPTED:
                raise ValueError(
                    "decision stage outcome requires an accepted immediate predecessor"
                )
            if outcome.evaluated_at < predecessor.evaluated_at:
                raise ValueError("decision stage outcome predates its predecessor")

        self._session.add(
            DecisionStageOutcomeRow(
                outcome_id=outcome.outcome_id,
                schema_version=outcome.schema_version,
                evaluation_id=outcome.evaluation_id,
                stage=outcome.stage.value,
                disposition=outcome.disposition.value,
                reason_code_count=len(outcome.reason_codes),
                evaluated_at=outcome.evaluated_at,
                offline_only=outcome.offline_only,
                external_order_submission_allowed=(outcome.external_order_submission_allowed),
                outcome_checksum=outcome.outcome_checksum,
                payload_json=outcome.model_dump_json(),
            )
        )
        self._session.flush()
        return outcome, True

    def get_stage_outcome(
        self,
        evaluation_id: str,
        *,
        stage: DecisionStage,
    ) -> DecisionStageOutcome | None:
        row = self._session.scalar(
            select(DecisionStageOutcomeRow).where(
                DecisionStageOutcomeRow.evaluation_id == evaluation_id,
                DecisionStageOutcomeRow.stage == stage.value,
            )
        )
        return None if row is None else self._outcome_from_row(row)

    def list_stage_outcomes(
        self,
        evaluation_id: str,
    ) -> tuple[DecisionStageOutcome, ...]:
        rows = self._session.scalars(
            select(DecisionStageOutcomeRow).where(
                DecisionStageOutcomeRow.evaluation_id == evaluation_id
            )
        ).all()
        outcomes = [self._outcome_from_row(row) for row in rows]
        order = {stage: index for index, stage in enumerate(_STAGE_ORDER)}
        return tuple(sorted(outcomes, key=lambda item: order[item.stage]))

    def stage_strategy_evaluation(
        self,
        record: StrategyEvaluationRecord,
    ) -> tuple[StrategyEvaluationRecord, bool]:
        existing = self.get_strategy_evaluation(record.evaluation_id)
        if existing is not None:
            if existing != record:
                raise ValueError("decision strategy evaluation exists with different content")
            return existing, False

        intent = self.get_evaluation_intent(record.evaluation_id)
        if intent is None:
            raise ValueError("decision strategy evaluation intent does not exist")
        outcome = self.get_stage_outcome(
            record.evaluation_id,
            stage=DecisionStage.STRATEGY_EVALUATION,
        )
        if outcome is None:
            raise ValueError("decision strategy evaluation outcome does not exist")
        if outcome != record.outcome:
            raise ValueError("decision strategy evaluation outcome is inconsistent")

        self._session.add(
            DecisionStrategyEvaluationRow(
                evaluation_id=record.evaluation_id,
                outcome_id=record.outcome.outcome_id,
                schema_version=record.schema_version,
                compatibility_policy_version=record.compatibility_policy_version,
                compatibility_policy_checksum=record.compatibility_policy_checksum,
                disposition=record.outcome.disposition.value,
                signal_count=record.signal_count,
                latest_signal_id=record.latest_signal_id,
                evaluated_at=record.outcome.evaluated_at,
                offline_only=record.offline_only,
                external_order_submission_allowed=(record.external_order_submission_allowed),
                record_checksum=record.record_checksum,
                payload_json=record.model_dump_json(),
            )
        )
        self._session.flush()
        return record, True

    def get_strategy_evaluation(
        self,
        evaluation_id: str,
    ) -> StrategyEvaluationRecord | None:
        row = self._session.get(DecisionStrategyEvaluationRow, evaluation_id)
        if row is None:
            return None
        return StrategyEvaluationRecord.model_validate_json(row.payload_json)

    def stage_candidate_ranking(
        self,
        record: DecisionCandidateRankingRecord,
    ) -> tuple[DecisionCandidateRankingRecord, bool]:
        existing = self.get_candidate_ranking(record.evaluation_id)
        if existing is not None:
            if existing != record:
                raise ValueError("decision candidate ranking exists with different content")
            return existing, False

        intent = self.get_evaluation_intent(record.evaluation_id)
        if intent is None:
            raise ValueError("decision candidate ranking intent does not exist")
        strategy_evaluation = self.get_strategy_evaluation(record.evaluation_id)
        if strategy_evaluation is None:
            raise ValueError("decision candidate ranking requires strategy evidence")
        if strategy_evaluation.outcome.disposition is not DecisionDisposition.ACCEPTED:
            raise ValueError("decision candidate ranking requires accepted strategy evidence")
        outcome = self.get_stage_outcome(
            record.evaluation_id,
            stage=DecisionStage.CANDIDATE_RANKING,
        )
        if outcome is None:
            raise ValueError("decision candidate ranking outcome does not exist")
        if outcome != record.outcome:
            raise ValueError("decision candidate ranking outcome is inconsistent")
        source_signal_ids = {item.signal_id for item in strategy_evaluation.signals}
        candidate_signal_ids = {item.candidate.signal_id for item in record.entries}
        if not candidate_signal_ids.issubset(source_signal_ids):
            raise ValueError("decision candidate ranking contains an unknown source signal")
        if record.source_signal_count != strategy_evaluation.signal_count:
            raise ValueError("decision candidate ranking source signal count is inconsistent")

        self._session.add(
            DecisionCandidateRankingRow(
                evaluation_id=record.evaluation_id,
                outcome_id=record.outcome.outcome_id,
                schema_version=record.schema_version,
                policy_version=record.policy_version,
                policy_checksum=record.policy_checksum,
                disposition=record.outcome.disposition.value,
                source_signal_count=record.source_signal_count,
                candidate_count=record.candidate_count,
                excluded_signal_count=record.excluded_signal_count,
                top_candidate_id=record.top_candidate_id,
                ranked_at=record.ranked_at,
                offline_only=record.offline_only,
                external_order_submission_allowed=(record.external_order_submission_allowed),
                record_checksum=record.record_checksum,
                payload_json=record.model_dump_json(),
            )
        )
        self._session.flush()
        return record, True

    def get_candidate_ranking(
        self,
        evaluation_id: str,
    ) -> DecisionCandidateRankingRecord | None:
        row = self._session.get(DecisionCandidateRankingRow, evaluation_id)
        if row is None:
            return None
        return DecisionCandidateRankingRecord.model_validate_json(row.payload_json)

    def stage_risk_gate(
        self,
        record: DecisionRiskGateRecord,
    ) -> tuple[DecisionRiskGateRecord, bool]:
        existing = self.get_risk_gate(record.evaluation_id)
        if existing is not None:
            if existing != record:
                raise ValueError("decision risk gate exists with different content")
            return existing, False

        intent = self.get_evaluation_intent(record.evaluation_id)
        if intent is None:
            raise ValueError("decision risk gate intent does not exist")
        ranking = self.get_candidate_ranking(record.evaluation_id)
        if ranking is None:
            raise ValueError("decision risk gate requires candidate ranking evidence")
        if ranking.outcome.disposition is not DecisionDisposition.ACCEPTED:
            raise ValueError("decision risk gate requires accepted candidate ranking")
        if record.candidate_ranking_checksum != ranking.record_checksum:
            raise ValueError("decision risk gate ranking checksum is inconsistent")
        if record.assessment.candidate_id != ranking.top_candidate_id:
            raise ValueError("decision risk gate did not assess the top candidate")
        outcome = self.get_stage_outcome(
            record.evaluation_id,
            stage=DecisionStage.RISK_GATE,
        )
        if outcome is None:
            raise ValueError("decision risk gate outcome does not exist")
        if outcome != record.outcome:
            raise ValueError("decision risk gate outcome is inconsistent")

        self._session.add(
            DecisionRiskGateRow(
                evaluation_id=record.evaluation_id,
                outcome_id=record.outcome.outcome_id,
                schema_version=record.schema_version,
                candidate_ranking_checksum=record.candidate_ranking_checksum,
                policy_version=record.policy_version,
                policy_checksum=record.policy_checksum,
                disposition=record.outcome.disposition.value,
                decision=record.assessment.decision.value,
                assessment_id=record.assessment.assessment_id,
                assessment_checksum=record.assessment.assessment_checksum,
                approved_candidate_id=record.approved_candidate_id,
                has_position_sizing=(record.assessment.position_sizing is not None),
                evaluated_at=record.evaluated_at,
                offline_only=record.offline_only,
                external_order_submission_allowed=(record.external_order_submission_allowed),
                record_checksum=record.record_checksum,
                payload_json=record.model_dump_json(),
            )
        )
        self._session.flush()
        return record, True

    def get_risk_gate(
        self,
        evaluation_id: str,
    ) -> DecisionRiskGateRecord | None:
        row = self._session.get(DecisionRiskGateRow, evaluation_id)
        if row is None:
            return None
        record = DecisionRiskGateRecord.model_validate_json(row.payload_json)
        approved = record.assessment.decision is DecisionRiskDecision.APPROVED
        if approved != (record.approved_candidate_id is not None):
            raise ValueError("persisted decision risk approval columns are inconsistent")
        return record

    def stage_portfolio_intelligence(
        self,
        record: DecisionPortfolioIntelligenceRecord,
    ) -> tuple[DecisionPortfolioIntelligenceRecord, bool]:
        existing = self.get_portfolio_intelligence(record.evaluation_id)
        if existing is not None:
            if existing != record:
                raise ValueError("decision portfolio intelligence exists with different content")
            return existing, False

        intent = self.get_evaluation_intent(record.evaluation_id)
        if intent is None:
            raise ValueError("decision portfolio intelligence intent does not exist")
        risk_gate = self.get_risk_gate(record.evaluation_id)
        if risk_gate is None:
            raise ValueError("decision portfolio intelligence requires risk evidence")
        if risk_gate.outcome.disposition is not DecisionDisposition.ACCEPTED:
            raise ValueError("decision portfolio intelligence requires accepted risk evidence")
        if record.risk_gate_checksum != risk_gate.record_checksum:
            raise ValueError("decision portfolio intelligence risk lineage is inconsistent")
        outcome = self.get_stage_outcome(
            record.evaluation_id,
            stage=DecisionStage.PORTFOLIO_SIMULATION,
        )
        if outcome is None or outcome != record.outcome:
            raise ValueError("decision portfolio intelligence outcome is inconsistent")

        analysis = record.analysis
        self._session.add(
            DecisionPortfolioIntelligenceRow(
                evaluation_id=record.evaluation_id,
                outcome_id=record.outcome.outcome_id,
                schema_version=record.schema_version,
                risk_gate_checksum=record.risk_gate_checksum,
                policy_version=record.policy_version,
                policy_checksum=record.policy_checksum,
                disposition=record.outcome.disposition.value,
                recommendation=record.recommendation.value,
                has_analysis=analysis is not None,
                snapshot_id=None if analysis is None else analysis.snapshot.snapshot_id,
                candidate_id=None if analysis is None else analysis.candidate_id,
                analyzed_at=record.analyzed_at,
                offline_only=record.offline_only,
                external_order_submission_allowed=(record.external_order_submission_allowed),
                record_checksum=record.record_checksum,
                payload_json=record.model_dump_json(),
            )
        )
        self._session.flush()
        return record, True

    def get_portfolio_intelligence(
        self,
        evaluation_id: str,
    ) -> DecisionPortfolioIntelligenceRecord | None:
        row = self._session.get(DecisionPortfolioIntelligenceRow, evaluation_id)
        if row is None:
            return None
        record = DecisionPortfolioIntelligenceRecord.model_validate_json(row.payload_json)
        if (record.analysis is not None) != row.has_analysis:
            raise ValueError("persisted portfolio analysis columns are inconsistent")
        return record

    def _validate_policy_reference(self, intent: DecisionEvaluationIntent) -> None:
        policy = self.get_policy_definition(
            intent.policy.policy_id,
            intent.policy.policy_version,
        )
        if policy is None:
            raise ValueError("decision evaluation policy version does not exist")
        if DecisionPolicyReference.from_definition(policy) != intent.policy:
            raise ValueError("decision evaluation does not match its persisted policy version")

    def _validate_dataset_reference(self, intent: DecisionEvaluationIntent) -> None:
        row = self._session.get(DatasetSnapshotRow, intent.dataset.dataset_id)
        if row is None:
            raise ValueError("decision evaluation dataset does not exist")
        dataset = DatasetSnapshot.model_validate_json(row.payload_json)
        if DecisionDatasetReference.from_dataset(dataset) != intent.dataset:
            raise ValueError("decision evaluation does not match its persisted dataset snapshot")

    def _validate_market_context_reference(
        self,
        intent: DecisionEvaluationIntent,
    ) -> None:
        row = self._session.get(
            MarketRegimeAssessmentRow,
            intent.market_context.assessment_id,
        )
        if row is None:
            raise ValueError("decision evaluation market context does not exist")
        assessment = MarketRegimeAssessment.model_validate_json(row.payload_json)
        persisted_reference = MarketContextDecisionReference.from_product_view(
            MarketContextProductView.from_assessment(
                assessment,
                evaluated_at=intent.requested_at,
            )
        )
        if persisted_reference != intent.market_context:
            raise ValueError("decision evaluation does not match its persisted market context")

    def _get_policy_definition_by_checksum(
        self,
        definition_checksum: str,
    ) -> DecisionPolicyDefinition | None:
        row = self._session.scalar(
            select(DecisionPolicyDefinitionRow).where(
                DecisionPolicyDefinitionRow.definition_checksum == definition_checksum
            )
        )
        return None if row is None else self._policy_from_row(row)

    @staticmethod
    def _policy_from_row(row: DecisionPolicyDefinitionRow) -> DecisionPolicyDefinition:
        return DecisionPolicyDefinition.model_validate_json(row.payload_json)

    @staticmethod
    def _intent_from_row(row: DecisionEvaluationIntentRow) -> DecisionEvaluationIntent:
        return DecisionEvaluationIntent.model_validate_json(row.payload_json)

    @staticmethod
    def _outcome_from_row(row: DecisionStageOutcomeRow) -> DecisionStageOutcome:
        return DecisionStageOutcome.model_validate_json(row.payload_json)
