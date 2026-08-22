import csv
from datetime import UTC, datetime
from decimal import Decimal
from io import StringIO

from trd_bot.research import (
    AcceptancePolicyPresetCatalog,
    ExperimentAcceptancePolicy,
    ExperimentParameter,
    ExperimentReportCsvExporter,
    ExperimentResearchReportBuilder,
    PresetExperimentResearchReport,
)
from trd_bot.research.experiments import ExperimentSummary


def create_csv_report() -> PresetExperimentResearchReport:
    experiment = ExperimentSummary.model_construct(
        experiment_id="experiment-0000000000000001",
        created_at=datetime(
            2026,
            8,
            22,
            10,
            tzinfo=UTC,
        ),
        dataset_id="dataset-0000000000000001",
        strategy_name="ema-crossover",
        strategy_version="1.0.0",
        horizon_candles=1,
        parameters=(
            ExperimentParameter(
                name="fast_period",
                value="2",
            ),
            ExperimentParameter(
                name="slow_period",
                value="3",
            ),
        ),
        generated_signals=4,
        total_trades=30,
        net_pnl=Decimal("125.50"),
        total_return=Decimal("0.125"),
        win_rate=Decimal("0.60"),
        max_drawdown_fraction=Decimal("0.08"),
        profit_factor=Decimal("1.75"),
        benchmark_type="buy_and_hold",
        benchmark_return=Decimal("0.07"),
        excess_return=Decimal("0.055"),
        benchmark_max_drawdown_fraction=Decimal("0.12"),
        max_drawdown_fraction_delta=Decimal("-0.04"),
        strategy_has_lower_drawdown=True,
        comparison_outcome="strategy",
    )

    preset = AcceptancePolicyPresetCatalog().get("baseline-v1")

    assert preset is not None

    report = ExperimentResearchReportBuilder().build(
        experiment=experiment,
        policy=ExperimentAcceptancePolicy(),
    )

    return PresetExperimentResearchReport(
        preset=preset,
        report=report,
    )


def parse_csv(content: str) -> list[list[str]]:
    return list(csv.reader(StringIO(content)))


def test_csv_export_has_stable_header_and_core_metrics() -> None:
    rows = parse_csv(ExperimentReportCsvExporter().export(create_csv_report()))

    assert rows[0] == [
        "section",
        "metric",
        "value",
    ]

    assert [
        "metadata",
        "experiment_id",
        "experiment-0000000000000001",
    ] in rows

    assert [
        "performance",
        "net_pnl",
        "125.50",
    ] in rows

    assert [
        "benchmark",
        "excess_return",
        "0.055",
    ] in rows

    assert [
        "policy_preset",
        "preset_id",
        "baseline-v1",
    ] in rows


def test_csv_export_contains_parameters_and_acceptance_checks() -> None:
    rows = parse_csv(ExperimentReportCsvExporter().export(create_csv_report()))

    assert [
        "strategy_parameter",
        "fast_period",
        "2",
    ] in rows

    assert [
        "acceptance",
        "outcome",
        "accepted",
    ] in rows

    assert [
        "acceptance_check",
        "minimum_total_trades.passed",
        "true",
    ] in rows

    assert [
        "acceptance_check",
        "minimum_total_trades.threshold",
        "20",
    ] in rows


def test_csv_export_is_deterministic() -> None:
    report = create_csv_report()
    exporter = ExperimentReportCsvExporter()

    assert exporter.export(report) == exporter.export(report)
