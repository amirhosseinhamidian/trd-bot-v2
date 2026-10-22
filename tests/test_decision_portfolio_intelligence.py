from collections.abc import Iterator
from datetime import timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from tests.test_decision_risk_gate import ranking_fixture, seed_accepted_ranking
from trd_bot.backtesting import PositionSide
from trd_bot.db import (
    DatabaseBase,
    DecisionPortfolioIntelligenceRow,
    DecisionStageOutcomeRow,
    SqlAlchemyDecisionIntelligenceStore,
    SqlAlchemyDecisionPortfolioIntelligence,
    SqlAlchemyDecisionRiskGate,
    SqlAlchemySimulatedPortfolioRepository,
    create_database_engine,
    create_session_factory,
)
from trd_bot.decision_intelligence import (
    DecisionDisposition,
    DecisionEvaluationIntent,
    DecisionPortfolioIntelligenceRecord,
    DecisionPortfolioPolicyV1,
    DecisionPortfolioSnapshot,
    DecisionRiskGateRecord,
    DecisionStage,
    PortfolioCheckName,
    PortfolioCorrelationStatus,
    PortfolioExitAction,
    PortfolioRecommendation,
    PortfolioSnapshotSource,
    decision_portfolio_policy_v1,
    evaluate_decision_risk,
    evaluate_portfolio_intelligence,
)
from trd_bot.paper import SimulatedPortfolioLedger, SimulationMode


@pytest.fixture
def factory() -> Iterator[sessionmaker[Session]]:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    DatabaseBase.metadata.create_all(engine)
    database_factory = create_session_factory(engine)
    yield database_factory
    engine.dispose()


def accepted_inputs() -> tuple[DecisionEvaluationIntent, DecisionRiskGateRecord]:
    evaluation_intent, _, _, ranking = ranking_fixture()
    return evaluation_intent, evaluate_decision_risk(ranking=ranking)


def test_portfolio_policy_is_frozen_and_tamper_evident() -> None:
    portfolio_policy = decision_portfolio_policy_v1()

    assert portfolio_policy.max_gross_exposure_fraction == Decimal("0.250000")
    assert portfolio_policy.max_asset_concentration_fraction == Decimal("0.200000")
    assert portfolio_policy.max_absolute_correlation == Decimal("0.850000")
    assert portfolio_policy.max_scenario_loss_fraction == Decimal("0.020000")
    assert portfolio_policy.definition_checksum == (
        "99d0169bb685a90fc2ea7398255bee7ba5ff0dfd0f6e30fd20a90cec24f408b0"
    )

    payload = portfolio_policy.model_dump()
    payload["max_gross_exposure_fraction"] = Decimal("0.26")
    with pytest.raises(ValidationError, match="not version one"):
        DecisionPortfolioPolicyV1.model_validate(payload)


def test_empty_shadow_portfolio_accepts_candidate_without_mutation() -> None:
    evaluation_intent, risk_gate = accepted_inputs()
    sizing = risk_gate.assessment.position_sizing
    assert sizing is not None
    snapshot = DecisionPortfolioSnapshot.build_empty(
        mode=evaluation_intent.mode,
        dataset_id=evaluation_intent.dataset.dataset_id,
        equity=sizing.reference_equity,
        as_of=risk_gate.evaluated_at,
    )

    first = evaluate_portfolio_intelligence(
        intent=evaluation_intent,
        risk_gate=risk_gate,
        snapshot=snapshot,
    )
    repeated = evaluate_portfolio_intelligence(
        intent=evaluation_intent,
        risk_gate=risk_gate,
        snapshot=snapshot,
    )

    assert repeated == first
    assert first.outcome.disposition is DecisionDisposition.ACCEPTED
    assert first.recommendation is PortfolioRecommendation.ACCEPT
    assert first.analysis is not None
    assert first.analysis.snapshot.source is PortfolioSnapshotSource.EMPTY_BASELINE
    assert first.analysis.exposure.current_gross_notional == 0
    assert first.analysis.exposure.projected_exposure_fraction == Decimal("0.100000")
    assert first.analysis.exposure.projected_asset_concentration_fraction == Decimal("0.100000")
    assert first.analysis.correlation.status is PortfolioCorrelationStatus.NOT_APPLICABLE
    assert len(first.analysis.scenarios) == 4
    assert max(item.loss_fraction for item in first.analysis.scenarios) == Decimal("0.010000")
    assert all(item.passed for item in first.analysis.checks)
    assert first.analysis.exit_recommendations == ()
    assert first.offline_only is True
    assert first.external_order_submission_allowed is False
    assert DecisionPortfolioIntelligenceRecord.model_validate_json(first.model_dump_json()) == first


def test_existing_same_pair_position_rejects_candidate_and_proposes_regime_exit() -> None:
    evaluation_intent, risk_gate = accepted_inputs()
    created_at = risk_gate.evaluated_at - timedelta(hours=2)
    ledger = SimulatedPortfolioLedger()
    portfolio = ledger.create(
        mode=SimulationMode.SHADOW,
        dataset_id=evaluation_intent.dataset.dataset_id,
        starting_cash=Decimal("10000"),
        created_at=created_at,
    )
    opened = ledger.open_position(
        portfolio,
        pair=evaluation_intent.dataset.pair,
        side=PositionSide.SHORT,
        price=Decimal("100"),
        quantity=Decimal("10"),
        occurred_at=created_at + timedelta(hours=1),
    )
    before = opened.model_dump_json()
    snapshot = DecisionPortfolioSnapshot.from_portfolio(opened)

    record = evaluate_portfolio_intelligence(
        intent=evaluation_intent,
        risk_gate=risk_gate,
        snapshot=snapshot,
    )

    assert record.outcome.disposition is DecisionDisposition.REJECTED
    assert record.recommendation is PortfolioRecommendation.REJECT
    assert record.analysis is not None
    assert record.analysis.correlation.status is PortfolioCorrelationStatus.AVAILABLE
    assert record.analysis.correlation.maximum_absolute_correlation == Decimal("1")
    failed = {item.name for item in record.analysis.checks if not item.passed}
    assert PortfolioCheckName.CAPACITY in failed
    assert PortfolioCheckName.CORRELATION in failed
    assert record.analysis.exit_recommendations[0].action is PortfolioExitAction.EXIT_REGIME
    assert opened.model_dump_json() == before


def test_excessive_existing_exposure_proposes_risk_exit() -> None:
    evaluation_intent, risk_gate = accepted_inputs()
    created_at = risk_gate.evaluated_at - timedelta(hours=2)
    ledger = SimulatedPortfolioLedger()
    opened = ledger.open_position(
        ledger.create(
            mode=SimulationMode.SHADOW,
            dataset_id=evaluation_intent.dataset.dataset_id,
            starting_cash=Decimal("10000"),
            created_at=created_at,
        ),
        pair=evaluation_intent.dataset.pair,
        side=PositionSide.LONG,
        price=Decimal("100"),
        quantity=Decimal("30"),
        occurred_at=created_at + timedelta(hours=1),
    )

    record = evaluate_portfolio_intelligence(
        intent=evaluation_intent,
        risk_gate=risk_gate,
        snapshot=DecisionPortfolioSnapshot.from_portfolio(opened),
    )

    assert record.analysis is not None
    assert record.analysis.exposure.current_exposure_fraction == Decimal("0.300000")
    assert record.analysis.exit_recommendations[0].action is PortfolioExitAction.EXIT_RISK
    assert record.analysis.exit_recommendations[0].reason_codes == ("risk_limit",)


def test_payload_tampering_is_detected() -> None:
    evaluation_intent, risk_gate = accepted_inputs()
    sizing = risk_gate.assessment.position_sizing
    assert sizing is not None
    record = evaluate_portfolio_intelligence(
        intent=evaluation_intent,
        risk_gate=risk_gate,
        snapshot=DecisionPortfolioSnapshot.build_empty(
            mode=evaluation_intent.mode,
            dataset_id=evaluation_intent.dataset.dataset_id,
            equity=sizing.reference_equity,
            as_of=risk_gate.evaluated_at,
        ),
    )
    payload = record.model_dump()
    payload["record_checksum"] = "0" * 64
    with pytest.raises(ValidationError, match="record checksum is inconsistent"):
        DecisionPortfolioIntelligenceRecord.model_validate(payload)


def test_sqlalchemy_stage_is_atomic_and_idempotent(
    factory: sessionmaker[Session],
) -> None:
    evaluation_id = seed_accepted_ranking(factory)
    with factory.begin() as session:
        SqlAlchemyDecisionRiskGate(session).evaluate(evaluation_id)
        service = SqlAlchemyDecisionPortfolioIntelligence(session)
        first, created = service.evaluate(evaluation_id)
        repeated, repeated_created = service.evaluate(evaluation_id)

        assert created is True
        assert repeated_created is False
        assert repeated == first
        assert first.recommendation is PortfolioRecommendation.ACCEPT
        assert first.analysis is not None
        assert first.analysis.snapshot.source is PortfolioSnapshotSource.EMPTY_BASELINE
        assert (
            session.scalar(select(func.count()).select_from(DecisionPortfolioIntelligenceRow)) == 1
        )
        assert (
            session.scalar(
                select(func.count())
                .select_from(DecisionStageOutcomeRow)
                .where(DecisionStageOutcomeRow.evaluation_id == evaluation_id)
            )
            == 4
        )

    with factory() as session:
        stored = SqlAlchemyDecisionIntelligenceStore(session).get_portfolio_intelligence(
            evaluation_id
        )
        assert stored == first


def test_sqlalchemy_uses_matching_persisted_snapshot_without_mutation(
    factory: sessionmaker[Session],
) -> None:
    evaluation_id = seed_accepted_ranking(factory)
    with factory.begin() as session:
        risk_gate, _ = SqlAlchemyDecisionRiskGate(session).evaluate(evaluation_id)
        evaluation_intent = SqlAlchemyDecisionIntelligenceStore(session).get_evaluation_intent(
            evaluation_id
        )
        assert evaluation_intent is not None
        created_at = risk_gate.evaluated_at - timedelta(hours=2)
        portfolio = SimulatedPortfolioLedger().create(
            mode=SimulationMode.SHADOW,
            dataset_id=evaluation_intent.dataset.dataset_id,
            starting_cash=Decimal("10000"),
            created_at=created_at,
        )
        SqlAlchemySimulatedPortfolioRepository(session).save(portfolio, commit=False)
        before = portfolio.model_dump_json()
        record, _ = SqlAlchemyDecisionPortfolioIntelligence(session).evaluate(evaluation_id)

        assert record.analysis is not None
        assert record.analysis.snapshot.portfolio_id == portfolio.portfolio_id
        assert record.recommendation is PortfolioRecommendation.ACCEPT
        persisted = SqlAlchemySimulatedPortfolioRepository(session).get(portfolio.portfolio_id)
        assert persisted is not None
        assert persisted.model_dump_json() == before


def test_multiple_matching_portfolios_fail_closed_as_unavailable(
    factory: sessionmaker[Session],
) -> None:
    evaluation_id = seed_accepted_ranking(factory)
    with factory.begin() as session:
        risk_gate, _ = SqlAlchemyDecisionRiskGate(session).evaluate(evaluation_id)
        evaluation_intent = SqlAlchemyDecisionIntelligenceStore(session).get_evaluation_intent(
            evaluation_id
        )
        assert evaluation_intent is not None
        ledger = SimulatedPortfolioLedger()
        repository = SqlAlchemySimulatedPortfolioRepository(session)
        for offset in (3, 2):
            repository.save(
                ledger.create(
                    mode=SimulationMode.SHADOW,
                    dataset_id=evaluation_intent.dataset.dataset_id,
                    starting_cash=Decimal("10000"),
                    created_at=risk_gate.evaluated_at - timedelta(hours=offset),
                ),
                commit=False,
            )

        record, _ = SqlAlchemyDecisionPortfolioIntelligence(session).evaluate(evaluation_id)

        assert record.recommendation is PortfolioRecommendation.UNAVAILABLE
        assert record.analysis is None
        assert record.outcome.disposition is DecisionDisposition.UNAVAILABLE


def test_stage_rolls_back_with_caller_transaction(factory: sessionmaker[Session]) -> None:
    evaluation_id = seed_accepted_ranking(factory)
    with pytest.raises(RuntimeError, match="cancelled"), factory.begin() as session:
        SqlAlchemyDecisionRiskGate(session).evaluate(evaluation_id)
        SqlAlchemyDecisionPortfolioIntelligence(session).evaluate(evaluation_id)
        raise RuntimeError("cancelled")

    with factory() as session:
        assert session.get(DecisionPortfolioIntelligenceRow, evaluation_id) is None
        assert (
            SqlAlchemyDecisionIntelligenceStore(session).get_stage_outcome(
                evaluation_id,
                stage=DecisionStage.PORTFOLIO_SIMULATION,
            )
            is None
        )
