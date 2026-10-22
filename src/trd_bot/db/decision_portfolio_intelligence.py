from sqlalchemy import select
from sqlalchemy.orm import Session

from trd_bot.db.decision_intelligence_repositories import (
    SqlAlchemyDecisionIntelligenceStore,
)
from trd_bot.db.models import SimulatedPortfolioRow
from trd_bot.decision_intelligence import (
    DecisionDisposition,
    DecisionMode,
    DecisionPortfolioIntegrityError,
    DecisionPortfolioIntelligenceRecord,
    DecisionPortfolioPolicyV1,
    DecisionPortfolioSnapshot,
    decision_portfolio_policy_v1,
    evaluate_portfolio_intelligence,
)
from trd_bot.paper import SimulatedPortfolio


class SqlAlchemyDecisionPortfolioIntelligence:
    """Persist bounded portfolio advice without applying ledger transitions."""

    def __init__(
        self,
        session: Session,
        *,
        policy: DecisionPortfolioPolicyV1 | None = None,
    ) -> None:
        self._session = session
        self._store = SqlAlchemyDecisionIntelligenceStore(session)
        self._policy = policy or decision_portfolio_policy_v1()

    def evaluate(
        self,
        evaluation_id: str,
    ) -> tuple[DecisionPortfolioIntelligenceRecord, bool]:
        existing = self._store.get_portfolio_intelligence(evaluation_id)
        if existing is not None:
            if existing.policy_checksum != self._policy.definition_checksum:
                raise DecisionPortfolioIntegrityError(
                    "portfolio intelligence already uses another policy"
                )
            return existing, False

        intent = self._store.get_evaluation_intent(evaluation_id)
        if intent is None:
            raise DecisionPortfolioIntegrityError("portfolio intelligence intent does not exist")
        risk_gate = self._store.get_risk_gate(evaluation_id)
        if risk_gate is None:
            raise DecisionPortfolioIntegrityError("portfolio intelligence risk gate does not exist")
        if risk_gate.outcome.disposition is not DecisionDisposition.ACCEPTED:
            raise DecisionPortfolioIntegrityError(
                "portfolio intelligence requires accepted risk evidence"
            )

        snapshot: DecisionPortfolioSnapshot | None = None
        if intent.mode is not DecisionMode.RESEARCH:
            rows = self._session.scalars(
                select(SimulatedPortfolioRow)
                .where(
                    SimulatedPortfolioRow.mode == intent.mode.value,
                    SimulatedPortfolioRow.status == "active",
                    SimulatedPortfolioRow.dataset_id == intent.dataset.dataset_id,
                    SimulatedPortfolioRow.updated_at <= risk_gate.evaluated_at,
                )
                .order_by(
                    SimulatedPortfolioRow.updated_at.desc(),
                    SimulatedPortfolioRow.portfolio_id.asc(),
                )
                .limit(2)
            ).all()
            if len(rows) == 1:
                portfolio = SimulatedPortfolio.model_validate_json(rows[0].payload_json)
                snapshot = DecisionPortfolioSnapshot.from_portfolio(portfolio)
            elif not rows:
                sizing = risk_gate.assessment.position_sizing
                if sizing is None:
                    raise DecisionPortfolioIntegrityError(
                        "portfolio intelligence approved risk has no sizing"
                    )
                snapshot = DecisionPortfolioSnapshot.build_empty(
                    mode=intent.mode,
                    dataset_id=intent.dataset.dataset_id,
                    equity=sizing.reference_equity,
                    as_of=risk_gate.evaluated_at,
                )

        record = evaluate_portfolio_intelligence(
            intent=intent,
            risk_gate=risk_gate,
            snapshot=snapshot,
            policy=self._policy,
        )
        self._store.stage_outcome(record.outcome)
        return self._store.stage_portfolio_intelligence(record)
