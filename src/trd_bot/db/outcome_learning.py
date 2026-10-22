from datetime import UTC, datetime
from decimal import Decimal
from typing import TypedDict

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from trd_bot.alerts import AlertOutcomeClassification
from trd_bot.db.models import (
    AlertOutcomeRow,
    AlertSimulationRow,
    CandidateJournalRow,
    DecisionEvaluationIntentRow,
    DecisionStageOutcomeRow,
    SimulatedPortfolioRow,
    SimulatedPositionRow,
)
from trd_bot.decision_intelligence import DecisionDisposition, DecisionStage
from trd_bot.outcome_learning import (
    DecisionStageReview,
    ExitReasonReview,
    OutcomeLearningReview,
    OutcomeLearningReviewPolicy,
    OutcomeLearningSnapshot,
    build_outcome_learning_review,
)
from trd_bot.paper import PositionStatus, SimulationMode
from trd_bot.research.dataset_replay_lifecycle import CandidateReplayLifecycleStatus
from trd_bot.research.position_monitoring import CandidateExitReason


class _AlertSnapshot(TypedDict):
    alert_outcomes: int
    alert_awaiting_outcome: int
    alert_confirmed: int
    alert_neutral: int
    alert_false_positive: int
    alert_drifted: int
    average_alert_directional_return: Decimal


class _CandidateSnapshot(TypedDict):
    candidate_journals: int
    candidate_no_position: int
    candidate_closed: int
    exit_reasons: tuple[ExitReasonReview, ...]


class _DecisionSnapshot(TypedDict):
    decision_evaluations: int
    decision_stages: tuple[DecisionStageReview, ...]


class _PortfolioSnapshot(TypedDict):
    simulated_portfolios: int
    paper_portfolios: int
    shadow_portfolios: int
    closed_positions: int
    profitable_positions: int
    losing_positions: int
    breakeven_positions: int
    net_realized_pnl: Decimal


class SqlAlchemyOutcomeLearningReviewReader:
    """Build a bounded aggregate review without loading row payloads."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def read(
        self,
        *,
        environment_label: str,
        commit_sha: str,
        generated_at: datetime | None = None,
        policy: OutcomeLearningReviewPolicy | None = None,
    ) -> OutcomeLearningReview:
        timestamp = _timestamp(generated_at or datetime.now(UTC))
        alerts = self._alert_snapshot(timestamp)
        candidates = self._candidate_snapshot()
        decisions = self._decision_snapshot()
        portfolios = self._portfolio_snapshot()
        snapshot = OutcomeLearningSnapshot(
            alert_outcomes=alerts["alert_outcomes"],
            alert_awaiting_outcome=alerts["alert_awaiting_outcome"],
            alert_confirmed=alerts["alert_confirmed"],
            alert_neutral=alerts["alert_neutral"],
            alert_false_positive=alerts["alert_false_positive"],
            alert_drifted=alerts["alert_drifted"],
            average_alert_directional_return=alerts["average_alert_directional_return"],
            candidate_journals=candidates["candidate_journals"],
            candidate_no_position=candidates["candidate_no_position"],
            candidate_closed=candidates["candidate_closed"],
            exit_reasons=candidates["exit_reasons"],
            decision_evaluations=decisions["decision_evaluations"],
            decision_stages=decisions["decision_stages"],
            simulated_portfolios=portfolios["simulated_portfolios"],
            paper_portfolios=portfolios["paper_portfolios"],
            shadow_portfolios=portfolios["shadow_portfolios"],
            closed_positions=portfolios["closed_positions"],
            profitable_positions=portfolios["profitable_positions"],
            losing_positions=portfolios["losing_positions"],
            breakeven_positions=portfolios["breakeven_positions"],
            net_realized_pnl=portfolios["net_realized_pnl"],
        )
        return build_outcome_learning_review(
            environment_label=environment_label,
            commit_sha=commit_sha,
            generated_at=timestamp,
            snapshot=snapshot,
            policy=policy,
        )

    def _alert_snapshot(self, generated_at: datetime) -> _AlertSnapshot:
        grouped: dict[str, int] = {
            classification: int(count)
            for classification, count in self._session.execute(
                select(AlertOutcomeRow.classification, func.count())
                .group_by(AlertOutcomeRow.classification)
                .order_by(AlertOutcomeRow.classification)
            ).all()
        }
        completed = sum(int(value) for value in grouped.values())
        drifted = int(
            self._session.scalar(
                select(func.count())
                .select_from(AlertOutcomeRow)
                .where(AlertOutcomeRow.drifted.is_(True))
            )
            or 0
        )
        awaiting = int(
            self._session.scalar(
                select(func.count())
                .select_from(AlertSimulationRow)
                .outerjoin(
                    AlertOutcomeRow,
                    AlertOutcomeRow.simulation_id == AlertSimulationRow.simulation_id,
                )
                .where(
                    AlertSimulationRow.ends_at <= generated_at,
                    AlertOutcomeRow.outcome_id.is_(None),
                )
            )
            or 0
        )
        average = self._session.scalar(select(func.avg(AlertOutcomeRow.directional_return)))
        return {
            "alert_outcomes": completed,
            "alert_awaiting_outcome": awaiting,
            "alert_confirmed": int(grouped.get(AlertOutcomeClassification.CONFIRMED.value, 0)),
            "alert_neutral": int(grouped.get(AlertOutcomeClassification.NEUTRAL.value, 0)),
            "alert_false_positive": int(
                grouped.get(AlertOutcomeClassification.FALSE_POSITIVE.value, 0)
            ),
            "alert_drifted": drifted,
            "average_alert_directional_return": _decimal(average),
        }

    def _candidate_snapshot(self) -> _CandidateSnapshot:
        grouped: dict[str, int] = {
            status: int(count)
            for status, count in self._session.execute(
                select(CandidateJournalRow.status, func.count())
                .group_by(CandidateJournalRow.status)
                .order_by(CandidateJournalRow.status)
            ).all()
        }
        exit_grouped: dict[str | None, int] = {
            reason: int(count)
            for reason, count in self._session.execute(
                select(CandidateJournalRow.exit_reason, func.count())
                .where(CandidateJournalRow.status == CandidateReplayLifecycleStatus.CLOSED.value)
                .group_by(CandidateJournalRow.exit_reason)
                .order_by(CandidateJournalRow.exit_reason)
            ).all()
        }
        no_position = int(grouped.get(CandidateReplayLifecycleStatus.NO_POSITION.value, 0))
        closed = int(grouped.get(CandidateReplayLifecycleStatus.CLOSED.value, 0))
        return {
            "candidate_journals": no_position + closed,
            "candidate_no_position": no_position,
            "candidate_closed": closed,
            "exit_reasons": tuple(
                ExitReasonReview(reason=reason, count=int(exit_grouped.get(reason.value, 0)))
                for reason in CandidateExitReason
            ),
        }

    def _decision_snapshot(self) -> _DecisionSnapshot:
        evaluation_count = int(
            self._session.scalar(select(func.count()).select_from(DecisionEvaluationIntentRow)) or 0
        )
        grouped = {
            (str(stage), str(disposition)): int(count)
            for stage, disposition, count in self._session.execute(
                select(
                    DecisionStageOutcomeRow.stage,
                    DecisionStageOutcomeRow.disposition,
                    func.count(),
                )
                .group_by(
                    DecisionStageOutcomeRow.stage,
                    DecisionStageOutcomeRow.disposition,
                )
                .order_by(
                    DecisionStageOutcomeRow.stage,
                    DecisionStageOutcomeRow.disposition,
                )
            ).all()
        }
        return {
            "decision_evaluations": evaluation_count,
            "decision_stages": tuple(
                DecisionStageReview(
                    stage=stage,
                    accepted=grouped.get((stage.value, DecisionDisposition.ACCEPTED.value), 0),
                    rejected=grouped.get((stage.value, DecisionDisposition.REJECTED.value), 0),
                    deferred=grouped.get((stage.value, DecisionDisposition.DEFERRED.value), 0),
                    unavailable=grouped.get(
                        (stage.value, DecisionDisposition.UNAVAILABLE.value), 0
                    ),
                )
                for stage in DecisionStage
            ),
        }

    def _portfolio_snapshot(self) -> _PortfolioSnapshot:
        portfolio_grouped: dict[str, int] = {
            mode: int(count)
            for mode, count in self._session.execute(
                select(SimulatedPortfolioRow.mode, func.count())
                .group_by(SimulatedPortfolioRow.mode)
                .order_by(SimulatedPortfolioRow.mode)
            ).all()
        }
        paper = int(portfolio_grouped.get(SimulationMode.PAPER.value, 0))
        shadow = int(portfolio_grouped.get(SimulationMode.SHADOW.value, 0))
        row = self._session.execute(
            select(
                func.count(),
                func.coalesce(
                    func.sum(case((SimulatedPositionRow.realized_pnl > 0, 1), else_=0)),
                    0,
                ),
                func.coalesce(
                    func.sum(case((SimulatedPositionRow.realized_pnl < 0, 1), else_=0)),
                    0,
                ),
                func.coalesce(
                    func.sum(case((SimulatedPositionRow.realized_pnl == 0, 1), else_=0)),
                    0,
                ),
                func.coalesce(func.sum(SimulatedPositionRow.realized_pnl), 0),
            ).where(SimulatedPositionRow.status == PositionStatus.CLOSED.value)
        ).one()
        return {
            "simulated_portfolios": paper + shadow,
            "paper_portfolios": paper,
            "shadow_portfolios": shadow,
            "closed_positions": int(row[0]),
            "profitable_positions": int(row[1]),
            "losing_positions": int(row[2]),
            "breakeven_positions": int(row[3]),
            "net_realized_pnl": _decimal(row[4]),
        }


def _timestamp(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("outcome learning timestamp must include timezone")
    return value.astimezone(UTC)


def _decimal(value: object) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal("0.00000001"))
