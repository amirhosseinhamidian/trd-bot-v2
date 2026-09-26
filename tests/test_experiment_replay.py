from datetime import UTC, datetime, timedelta
from decimal import Decimal

from trd_bot.domain.market_data import OHLCVCandle, Timeframe, TradingPair
from trd_bot.research import (
    DatasetBuilder,
    DatasetSnapshot,
    ExperimentBuilder,
    ExperimentParameter,
    ExperimentReplayCode,
    ExperimentReplayStatus,
    ExperimentReplayVerifier,
    InMemoryDatasetRepository,
    ResearchExperiment,
    ResearchPipeline,
)
from trd_bot.strategies import EMACrossoverStrategy

CHECKED_AT = datetime(2026, 9, 26, 12, tzinfo=UTC)


def build_dataset() -> DatasetSnapshot:
    start = datetime(2026, 8, 20, 10, tzinfo=UTC)
    prices = ("5", "4", "3", "4", "6", "8", "9")
    candles = tuple(
        OHLCVCandle(
            source="test-exchange",
            pair=TradingPair(base_asset="BTC", quote_asset="USDT"),
            timeframe=Timeframe.HOUR_1,
            open_time=start + timedelta(hours=index),
            close_time=start + timedelta(hours=index + 1),
            received_at=start,
            open_price=Decimal(price),
            high_price=Decimal(price) + Decimal("1"),
            low_price=Decimal(price) - Decimal("1"),
            close_price=Decimal(price),
            volume=Decimal("1000"),
            is_closed=True,
        )
        for index, price in enumerate(prices)
    )
    return DatasetBuilder().build(name="Replay dataset", candles=candles)


def build_experiment() -> tuple[DatasetSnapshot, ResearchExperiment]:
    dataset = build_dataset()
    result = ResearchPipeline().run(
        dataset=dataset,
        strategy=EMACrossoverStrategy(fast_period=2, slow_period=3),
        horizon_candles=1,
    )
    experiment = ExperimentBuilder().build(
        result=result,
        parameters=(
            ExperimentParameter(name="fast_period", value="2"),
            ExperimentParameter(name="slow_period", value="3"),
        ),
        created_at=CHECKED_AT,
    )
    return dataset, experiment


def test_verifies_an_exact_deterministic_replay() -> None:
    dataset, experiment = build_experiment()
    datasets = InMemoryDatasetRepository()
    datasets.save(dataset)

    verification = ExperimentReplayVerifier(datasets=datasets).verify(
        experiment,
        checked_at=CHECKED_AT,
    )

    assert verification.status is ExperimentReplayStatus.VERIFIED
    assert verification.code is ExperimentReplayCode.VERIFIED
    assert verification.recorded_result_checksum == verification.replayed_result_checksum
    assert verification.recorded_strategy_fingerprint == verification.current_strategy_fingerprint
    assert verification.mismatch_fields == ()


def test_rejects_a_legacy_experiment_without_guessing_its_fingerprint() -> None:
    dataset, experiment = build_experiment()
    datasets = InMemoryDatasetRepository()
    datasets.save(dataset)
    legacy = experiment.model_copy(update={"strategy_fingerprint": None})

    verification = ExperimentReplayVerifier(datasets=datasets).verify(
        legacy,
        checked_at=CHECKED_AT,
    )

    assert verification.status is ExperimentReplayStatus.UNVERIFIABLE
    assert verification.code is ExperimentReplayCode.LEGACY_FINGERPRINT_MISSING
    assert verification.replayed_result_checksum is None


def test_fails_closed_when_the_registered_behavior_fingerprint_changed() -> None:
    dataset, experiment = build_experiment()
    datasets = InMemoryDatasetRepository()
    datasets.save(dataset)
    changed = experiment.model_copy(
        update={"strategy_fingerprint": f"sha256:{'f' * 64}"},
    )

    verification = ExperimentReplayVerifier(datasets=datasets).verify(
        changed,
        checked_at=CHECKED_AT,
    )

    assert verification.status is ExperimentReplayStatus.MISMATCH
    assert verification.code is ExperimentReplayCode.STRATEGY_FINGERPRINT_MISMATCH
    assert verification.replayed_result_checksum is None


def test_reports_an_unavailable_immutable_dataset_without_running() -> None:
    _, experiment = build_experiment()

    verification = ExperimentReplayVerifier(
        datasets=InMemoryDatasetRepository(),
    ).verify(experiment, checked_at=CHECKED_AT)

    assert verification.status is ExperimentReplayStatus.UNVERIFIABLE
    assert verification.code is ExperimentReplayCode.DATASET_NOT_FOUND
    assert verification.replayed_result_checksum is None


def test_detects_dataset_content_that_no_longer_matches_its_checksum() -> None:
    dataset, experiment = build_experiment()
    first_candle = dataset.candles[0].model_copy(update={"close_price": Decimal("999")})
    tampered = dataset.model_copy(update={"candles": (first_candle, *dataset.candles[1:])})
    datasets = InMemoryDatasetRepository()
    datasets.save(tampered)

    verification = ExperimentReplayVerifier(datasets=datasets).verify(
        experiment,
        checked_at=CHECKED_AT,
    )

    assert verification.status is ExperimentReplayStatus.MISMATCH
    assert verification.code is ExperimentReplayCode.DATASET_INTEGRITY_MISMATCH
    assert verification.replayed_result_checksum is None


def test_reports_changed_result_fields_without_overwriting_the_record() -> None:
    dataset, experiment = build_experiment()
    datasets = InMemoryDatasetRepository()
    datasets.save(dataset)
    changed_result = experiment.result.model_copy(update={"generated_signals": 999})
    changed = experiment.model_copy(update={"result": changed_result})

    verification = ExperimentReplayVerifier(datasets=datasets).verify(
        changed,
        checked_at=CHECKED_AT,
    )

    assert verification.status is ExperimentReplayStatus.MISMATCH
    assert verification.code is ExperimentReplayCode.RESULT_MISMATCH
    assert verification.recorded_result_checksum != verification.replayed_result_checksum
    assert verification.mismatch_fields == ("generated_signals",)
    assert changed.result.generated_signals == 999


def test_rejects_noncanonical_or_missing_strategy_parameters() -> None:
    dataset, experiment = build_experiment()
    datasets = InMemoryDatasetRepository()
    datasets.save(dataset)
    invalid = experiment.model_copy(
        update={"parameters": (ExperimentParameter(name="fast_period", value="02"),)},
    )

    verification = ExperimentReplayVerifier(datasets=datasets).verify(
        invalid,
        checked_at=CHECKED_AT,
    )

    assert verification.status is ExperimentReplayStatus.UNVERIFIABLE
    assert verification.code is ExperimentReplayCode.INVALID_STRATEGY_PARAMETERS
    assert verification.replayed_result_checksum is None
