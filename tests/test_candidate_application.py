from decimal import Decimal

import pytest

from tests.test_experiment_replay import build_experiment
from trd_bot.paper import SimulationMode
from trd_bot.research.candidate_application import (
    CandidateApplicationOrchestrator,
    CandidateApplicationStatus,
)
from trd_bot.research.candidate_generation import CandidateGenerator
from trd_bot.research.candidate_journal import (
    CandidateJournalBuilder,
    CandidateJournalEntry,
)
from trd_bot.research.candidates import ResearchCandidate
from trd_bot.research.dataset_replay_lifecycle import (
    CandidateReplayLifecycleResult,
    CandidateReplayLifecycleStatus,
)
from trd_bot.research.datasets import DatasetSnapshot
from trd_bot.research.experiment_executions import (
    EMACrossoverExecutionParameters,
)
from trd_bot.research.experiments import ResearchExperiment


class RecordingLifecycleRecorder:
    def __init__(self) -> None:
        self.recorded: CandidateReplayLifecycleResult | None = None

    def record(
        self,
        lifecycle: CandidateReplayLifecycleResult,
    ) -> CandidateJournalEntry:
        self.recorded = lifecycle
        return CandidateJournalBuilder.from_lifecycle(lifecycle)


def build_execution_parameters() -> EMACrossoverExecutionParameters:
    return EMACrossoverExecutionParameters(
        fast_period=2,
        slow_period=3,
        horizon_candles=1,
        starting_balance=Decimal("10000"),
        allocation_fraction=Decimal("0.10"),
        fee_rate=Decimal("0.001"),
        slippage_rate=Decimal("0.0005"),
    )


def test_runs_experiment_candidates_through_ranking_risk_and_persistence() -> None:
    dataset, experiment = build_experiment()
    parameters = build_execution_parameters()
    recorder = RecordingLifecycleRecorder()

    result = CandidateApplicationOrchestrator(
        recorder=recorder,
    ).run(
        experiment=experiment,
        dataset=dataset,
        parameters=parameters,
    )

    source_signal = experiment.result.signals[0]

    assert result.status is CandidateApplicationStatus.NO_POSITION
    assert result.experiment_id == experiment.experiment_id
    assert result.dataset_id == dataset.dataset_id

    assert result.generated_candidate_count == 1
    assert result.evaluated_at == source_signal.generated_at

    assert result.ranking is not None
    assert result.ranking.ranked_at == result.evaluated_at
    assert result.ranking.total_candidates == 1
    assert result.ranking.eligible_count == 1

    assert result.lifecycle is not None
    assert result.lifecycle.status is CandidateReplayLifecycleStatus.NO_POSITION

    assert result.lifecycle.portfolio.mode is SimulationMode.PAPER
    assert result.lifecycle.portfolio.dataset_id == dataset.dataset_id
    assert result.lifecycle.portfolio.starting_cash == Decimal("10000")
    assert result.lifecycle.portfolio.fee_rate == Decimal("0.001")

    assert recorder.recorded == result.lifecycle

    assert result.journal is not None
    assert result.journal.lifecycle == result.lifecycle
    assert result.journal.selected_candidate_id is None
    assert result.journal.position_id is None


class EmptyCandidateGenerator(CandidateGenerator):
    def generate(
        self,
        *,
        experiment: ResearchExperiment,
        dataset: DatasetSnapshot,
    ) -> tuple[ResearchCandidate, ...]:
        del experiment, dataset
        return ()


def test_returns_no_candidates_without_creating_lifecycle_or_journal() -> None:
    dataset, experiment = build_experiment()
    parameters = build_execution_parameters()
    recorder = RecordingLifecycleRecorder()

    result = CandidateApplicationOrchestrator(
        recorder=recorder,
        generator=EmptyCandidateGenerator(),
    ).run(
        experiment=experiment,
        dataset=dataset,
        parameters=parameters,
    )

    assert result.status is CandidateApplicationStatus.NO_CANDIDATES
    assert result.experiment_id == experiment.experiment_id
    assert result.dataset_id == dataset.dataset_id

    assert result.generated_candidate_count == 0
    assert result.evaluated_at is None

    assert result.ranking is None
    assert result.lifecycle is None
    assert result.journal is None

    assert recorder.recorded is None


def test_rejects_experiment_from_another_dataset() -> None:
    dataset, experiment = build_experiment()

    mismatched_experiment = experiment.model_copy(
        update={
            "dataset_id": "dataset-0000000000000000",
        }
    )

    with pytest.raises(
        ValueError,
        match="candidate application experiment and dataset lineage must match",
    ):
        CandidateApplicationOrchestrator(
            recorder=RecordingLifecycleRecorder(),
        ).run(
            experiment=mismatched_experiment,
            dataset=dataset,
            parameters=build_execution_parameters(),
        )


def test_rejects_execution_horizon_that_does_not_match_experiment() -> None:
    dataset, experiment = build_experiment()

    mismatched_parameters = build_execution_parameters().model_copy(
        update={
            "horizon_candles": experiment.horizon_candles + 1,
        }
    )

    with pytest.raises(
        ValueError,
        match="candidate application execution horizon must match experiment",
    ):
        CandidateApplicationOrchestrator(
            recorder=RecordingLifecycleRecorder(),
        ).run(
            experiment=experiment,
            dataset=dataset,
            parameters=mismatched_parameters,
        )


from trd_bot.research.experiment_executions import (  # noqa: E402
    SMACrossoverExecutionParameters,
)


class VersionMismatchExecutionParameters(EMACrossoverExecutionParameters):
    @property
    def strategy_version(self) -> str:
        return "9.9.9"


def test_rejects_execution_strategy_name_that_does_not_match_experiment() -> None:
    dataset, experiment = build_experiment()

    mismatched_parameters = SMACrossoverExecutionParameters(
        fast_period=2,
        slow_period=3,
        horizon_candles=1,
        starting_balance=Decimal("10000"),
        allocation_fraction=Decimal("0.10"),
        fee_rate=Decimal("0.001"),
        slippage_rate=Decimal("0.0005"),
    )

    with pytest.raises(
        ValueError,
        match="candidate application execution strategy must match experiment",
    ):
        CandidateApplicationOrchestrator(
            recorder=RecordingLifecycleRecorder(),
        ).run(
            experiment=experiment,
            dataset=dataset,
            parameters=mismatched_parameters,
        )


def test_rejects_execution_strategy_version_that_does_not_match_experiment() -> None:
    dataset, experiment = build_experiment()

    mismatched_parameters = VersionMismatchExecutionParameters(
        fast_period=2,
        slow_period=3,
        horizon_candles=1,
        starting_balance=Decimal("10000"),
        allocation_fraction=Decimal("0.10"),
        fee_rate=Decimal("0.001"),
        slippage_rate=Decimal("0.0005"),
    )

    with pytest.raises(
        ValueError,
        match="candidate application execution strategy version must match experiment",
    ):
        CandidateApplicationOrchestrator(
            recorder=RecordingLifecycleRecorder(),
        ).run(
            experiment=experiment,
            dataset=dataset,
            parameters=mismatched_parameters,
        )


def test_rejects_execution_strategy_parameters_that_do_not_match_experiment() -> None:
    dataset, experiment = build_experiment()

    mismatched_parameters = EMACrossoverExecutionParameters(
        fast_period=1,
        slow_period=3,
        horizon_candles=1,
        starting_balance=Decimal("10000"),
        allocation_fraction=Decimal("0.10"),
        fee_rate=Decimal("0.001"),
        slippage_rate=Decimal("0.0005"),
    )

    with pytest.raises(
        ValueError,
        match="candidate application execution strategy parameters must match experiment",
    ):
        CandidateApplicationOrchestrator(
            recorder=RecordingLifecycleRecorder(),
        ).run(
            experiment=experiment,
            dataset=dataset,
            parameters=mismatched_parameters,
        )


from pydantic import ValidationError  # noqa: E402

from trd_bot.research.candidate_application import (  # noqa: E402
    CandidateApplicationResult,
)


def test_no_candidates_result_rejects_decision_artifacts() -> None:
    dataset, experiment = build_experiment()
    parameters = build_execution_parameters()
    recorder = RecordingLifecycleRecorder()

    no_candidates = CandidateApplicationOrchestrator(
        recorder=recorder,
        generator=EmptyCandidateGenerator(),
    ).run(
        experiment=experiment,
        dataset=dataset,
        parameters=parameters,
    )

    with pytest.raises(
        ValidationError,
        match="no-candidates application result cannot contain decision artifacts",
    ):
        CandidateApplicationResult(
            status=CandidateApplicationStatus.NO_CANDIDATES,
            experiment_id=no_candidates.experiment_id,
            dataset_id=no_candidates.dataset_id,
            generated_candidate_count=0,
            evaluated_at=experiment.created_at,
            ranking=None,
            lifecycle=None,
            journal=None,
        )


def test_no_position_result_requires_ranking_lifecycle_and_journal() -> None:
    dataset, experiment = build_experiment()

    with pytest.raises(
        ValidationError,
        match="evaluated candidate application result requires decision artifacts",
    ):
        CandidateApplicationResult(
            status=CandidateApplicationStatus.NO_POSITION,
            experiment_id=experiment.experiment_id,
            dataset_id=dataset.dataset_id,
            generated_candidate_count=1,
            evaluated_at=experiment.created_at,
            ranking=None,
            lifecycle=None,
            journal=None,
        )


def test_application_status_must_match_lifecycle_status() -> None:
    dataset, experiment = build_experiment()
    parameters = build_execution_parameters()
    recorder = RecordingLifecycleRecorder()

    result = CandidateApplicationOrchestrator(
        recorder=recorder,
    ).run(
        experiment=experiment,
        dataset=dataset,
        parameters=parameters,
    )

    assert result.status is CandidateApplicationStatus.NO_POSITION
    assert result.lifecycle is not None
    assert result.lifecycle.status is CandidateReplayLifecycleStatus.NO_POSITION

    with pytest.raises(
        ValidationError,
        match="candidate application status must match lifecycle status",
    ):
        CandidateApplicationResult(
            status=CandidateApplicationStatus.CLOSED,
            experiment_id=result.experiment_id,
            dataset_id=result.dataset_id,
            generated_candidate_count=result.generated_candidate_count,
            evaluated_at=result.evaluated_at,
            ranking=result.ranking,
            lifecycle=result.lifecycle,
            journal=result.journal,
        )


def test_application_evaluation_time_must_match_ranking_and_lifecycle() -> None:
    from datetime import timedelta

    dataset, experiment = build_experiment()
    result = CandidateApplicationOrchestrator(
        recorder=RecordingLifecycleRecorder(),
    ).run(
        experiment=experiment,
        dataset=dataset,
        parameters=build_execution_parameters(),
    )

    assert result.evaluated_at is not None
    assert result.ranking is not None
    assert result.lifecycle is not None

    mismatched_ranking = result.ranking.model_copy(
        update={
            "ranked_at": result.evaluated_at + timedelta(seconds=1),
        }
    )

    with pytest.raises(
        ValidationError,
        match="candidate application evaluation time must match ranking and lifecycle",
    ):
        CandidateApplicationResult(
            status=result.status,
            experiment_id=result.experiment_id,
            dataset_id=result.dataset_id,
            generated_candidate_count=result.generated_candidate_count,
            evaluated_at=result.evaluated_at,
            ranking=mismatched_ranking,
            lifecycle=result.lifecycle,
            journal=result.journal,
        )


def test_ranking_candidate_batch_must_match_lifecycle_replay_batch() -> None:
    dataset, experiment = build_experiment()

    result = CandidateApplicationOrchestrator(
        recorder=RecordingLifecycleRecorder(),
    ).run(
        experiment=experiment,
        dataset=dataset,
        parameters=build_execution_parameters(),
    )

    assert result.ranking is not None
    assert result.lifecycle is not None
    assert result.ranking.total_candidates > 0
    assert result.lifecycle.replay.total_candidates > 0

    mismatched_ranking = type(result.ranking)(
        ranked_at=result.ranking.ranked_at,
        policy=result.ranking.policy,
        total_candidates=result.ranking.total_candidates,
        eligible_count=0,
        excluded_count=result.ranking.total_candidates,
        entries=(),
    )

    with pytest.raises(
        ValidationError,
        match="candidate application ranking and lifecycle candidate batches must match",
    ):
        CandidateApplicationResult(
            status=result.status,
            experiment_id=result.experiment_id,
            dataset_id=result.dataset_id,
            generated_candidate_count=result.generated_candidate_count,
            evaluated_at=result.evaluated_at,
            ranking=mismatched_ranking,
            lifecycle=result.lifecycle,
            journal=result.journal,
        )


def test_journal_must_match_application_lifecycle() -> None:
    from tests.test_candidate_journal import build_no_position_lifecycle

    dataset, experiment = build_experiment()

    result = CandidateApplicationOrchestrator(
        recorder=RecordingLifecycleRecorder(),
    ).run(
        experiment=experiment,
        dataset=dataset,
        parameters=build_execution_parameters(),
    )

    assert result.lifecycle is not None
    assert result.journal is not None

    mismatched_journal = CandidateJournalBuilder.from_lifecycle(build_no_position_lifecycle())

    assert mismatched_journal != result.journal

    with pytest.raises(
        ValidationError,
        match="candidate application journal must match lifecycle",
    ):
        CandidateApplicationResult(
            status=result.status,
            experiment_id=result.experiment_id,
            dataset_id=result.dataset_id,
            generated_candidate_count=result.generated_candidate_count,
            evaluated_at=result.evaluated_at,
            ranking=result.ranking,
            lifecycle=result.lifecycle,
            journal=mismatched_journal,
        )
