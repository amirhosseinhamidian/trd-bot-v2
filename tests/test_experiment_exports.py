import csv
import hashlib
from datetime import UTC, datetime
from decimal import Decimal
from io import StringIO

from trd_bot.research import (
    EXPERIMENT_REPORT_CSV_COLUMNS,
    EXPERIMENT_REPORT_CSV_SCHEMA_VERSION,
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
    content = ExperimentReportCsvExporter().export(create_csv_report())
    rows = parse_csv(content)

    assert rows[0] == list(EXPERIMENT_REPORT_CSV_COLUMNS)
    assert rows[1] == [
        "metadata",
        "export_schema_version",
        EXPERIMENT_REPORT_CSV_SCHEMA_VERSION,
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


def test_csv_export_neutralizes_untrusted_spreadsheet_formulas() -> None:
    report = create_csv_report()
    experiment = report.report.experiment.model_copy(
        update={
            "parameters": (
                ExperimentParameter(name="formula", value='  =HYPERLINK("https://invalid")'),
                ExperimentParameter(name="negative-number", value="-1"),
            ),
            "net_pnl": Decimal("-125.50"),
        }
    )
    guarded = report.model_copy(
        update={
            "report": report.report.model_copy(update={"experiment": experiment}),
        }
    )

    rows = parse_csv(ExperimentReportCsvExporter().export(guarded))

    assert [
        "strategy_parameter",
        "formula",
        '\'  =HYPERLINK("https://invalid")',
    ] in rows
    assert ["strategy_parameter", "negative-number", "'-1"] in rows
    assert ["performance", "net_pnl", "-125.50"] in rows


def test_csv_v1_golden_contract_does_not_drift() -> None:
    content = ExperimentReportCsvExporter().export(create_csv_report())

    assert hashlib.sha256(content.encode("utf-8")).hexdigest() == (
        "e7c55417a7812ef23fc17c57f33cce0244dcbdcc5f320612f45b03eba069ffe8"
    )
