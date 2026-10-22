from datetime import UTC, datetime
from decimal import Decimal

from tests.test_candidate_journal import build_closed_lifecycle
from tests.test_candidate_replay_lifecycle import (
    EVALUATED_AT,
    candidate,
    lifecycle_dataset,
    simulated_portfolio,
)
from trd_bot.research.candidate_journal import (
    CandidateJournalBuilder,
    CandidateJournalEntry,
)
from trd_bot.research.candidate_ranking import CandidateRanker
from trd_bot.research.dataset_replay import CandidateDatasetReplayRunner
from trd_bot.research.dataset_replay_lifecycle import CandidateReplayLifecycleRunner
from trd_bot.research.dataset_replay_orchestration import CandidateDatasetReplayOrchestrator
from trd_bot.research.risk_dashboard import RiskDashboardBuilder
from trd_bot.research.risk_policy import (
    CandidateRiskCheckName,
    CandidateRiskDecision,
    CandidateRiskEvaluator,
    CandidateRiskPolicy,
)


def build_rejected_journal(
    *,
    evaluated_at: datetime = datetime(2026, 8, 26, 13, tzinfo=UTC),
) -> CandidateJournalEntry:
    dataset = lifecycle_dataset()
    entries = (
        CandidateRanker()
        .rank(
            candidates=(
                candidate(
                    dataset_id=dataset.dataset_id,
                    experiment_id="experiment-5555555555555555",
                    confidence="0.90",
                    entry_low="130",
                    entry_high="132",
                    invalidation="127",
                    target="142",
                ),
            ),
            at=evaluated_at,
        )
        .entries
    )
    evaluator = CandidateRiskEvaluator(
        policy=CandidateRiskPolicy(
            min_ranking_score=Decimal("0.99"),
            min_reward_risk_ratio=Decimal("100"),
        )
    )
    lifecycle = CandidateReplayLifecycleRunner(
        replay_orchestrator=CandidateDatasetReplayOrchestrator(
            replay_runner=CandidateDatasetReplayRunner(risk_evaluator=evaluator),
        )
    ).run(
        entries=entries,
        portfolio=simulated_portfolio(dataset_id=dataset.dataset_id),
        dataset=dataset,
        evaluated_at=evaluated_at,
    )
    return CandidateJournalBuilder.from_lifecycle(lifecycle)


def test_dashboard_reconciles_decisions_primary_reasons_and_risk_budget() -> None:
    closed = CandidateJournalBuilder.from_lifecycle(build_closed_lifecycle())
    rejected = build_rejected_journal()

    report = RiskDashboardBuilder().build(
        journals=(closed, rejected),
        portfolios=(closed.lifecycle.portfolio,),
        generated_at=datetime(2026, 8, 27, tzinfo=UTC),
    )

    assert report.decisions.evaluated_count == 3
    assert report.decisions.approved_count == 2
    assert report.decisions.rejected_count == 1
    assert report.decisions.approval_rate == Decimal("0.666667")

    reason_counts = {reason.name: reason.rejected_decisions for reason in report.rejection_reasons}
    assert tuple(reason_counts) == tuple(CandidateRiskCheckName)
    assert sum(reason_counts.values()) == report.decisions.rejected_count
    assert reason_counts[CandidateRiskCheckName.RANKING_SCORE] == 1

    rejected_event = next(
        event
        for event in report.decision_events
        if event.decision is CandidateRiskDecision.REJECTED
    )
    assert rejected_event.primary_rejection_reason is CandidateRiskCheckName.RANKING_SCORE
    assert rejected_event.failed_check_names == (
        CandidateRiskCheckName.RANKING_SCORE,
        CandidateRiskCheckName.REWARD_RISK,
    )

    assert report.budget.opened_decisions == 1
    assert report.budget.allocated_risk_budget > 0
    assert Decimal("0") < report.budget.consumed_risk <= report.budget.allocated_risk_budget
    assert report.budget.consumption_fraction is not None


def test_dashboard_uses_attempted_decisions_as_the_filtered_denominator() -> None:
    closed = CandidateJournalBuilder.from_lifecycle(build_closed_lifecycle())
    rejected = build_rejected_journal()

    report = RiskDashboardBuilder().build(
        journals=(closed, rejected),
        portfolios=(closed.lifecycle.portfolio,),
        generated_at=datetime(2026, 8, 27, tzinfo=UTC),
        from_time=datetime(2026, 8, 26, 13, tzinfo=UTC),
        to_time=datetime(2026, 8, 26, 14, tzinfo=UTC),
        portfolio_id=closed.portfolio_id,
    )

    assert report.decisions.evaluated_count == 1
    assert report.decisions.approved_count == 0
    assert report.decisions.rejected_count == 1
    assert report.decisions.approval_rate == Decimal("0.000000")
    assert len(report.decision_events) == 1
    assert report.decision_events[0].evaluated_at == datetime(
        2026,
        8,
        26,
        13,
        tzinfo=UTC,
    )


def test_dashboard_projects_exposure_concentration_and_drawdown_from_timeline() -> None:
    lifecycle = build_closed_lifecycle()
    journal = CandidateJournalBuilder.from_lifecycle(lifecycle)

    report = RiskDashboardBuilder().build(
        journals=(journal,),
        portfolios=(lifecycle.replay.portfolio,),
        generated_at=datetime(2026, 8, 27, tzinfo=UTC),
    )
    snapshot = report.portfolio_risk

    assert snapshot.portfolio_count == 1
    assert snapshot.open_position_count == 1
    assert snapshot.simulated_exposure > 0
    assert snapshot.exposure_fraction is not None
    assert snapshot.exposure_limit_fraction == Decimal("0.25")
    assert snapshot.largest_pair is not None
    assert snapshot.concentration_exposure == snapshot.simulated_exposure
    assert snapshot.concentration_fraction == snapshot.exposure_fraction
    assert snapshot.max_drawdown_fraction is not None
    assert snapshot.drawdown_limit_fraction == Decimal("0.01")


def test_dashboard_returns_explicit_empty_metrics_without_false_rates() -> None:
    report = RiskDashboardBuilder().build(
        journals=(),
        portfolios=(),
        generated_at=EVALUATED_AT,
    )

    assert report.decisions.evaluated_count == 0
    assert report.decisions.approval_rate is None
    assert all(reason.rejected_decisions == 0 for reason in report.rejection_reasons)
    assert report.budget.consumption_fraction is None
    assert report.portfolio_risk.portfolio_count == 0
    assert report.portfolio_risk.exposure_fraction is None
    assert report.portfolio_risk.max_drawdown_fraction is None
    assert report.decision_events == ()
