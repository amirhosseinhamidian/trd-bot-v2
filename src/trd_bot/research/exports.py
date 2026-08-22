import csv
from datetime import datetime
from decimal import Decimal
from enum import Enum
from io import StringIO

from trd_bot.research.policy_presets import (
    PresetExperimentResearchReport,
)


class ExperimentReportCsvExporter:
    """Export one versioned historical experiment report as flat CSV rows."""

    def export(
        self,
        report: PresetExperimentResearchReport,
    ) -> str:
        output = StringIO(newline="")
        writer = csv.writer(output, lineterminator="\n")
        writer.writerow(("section", "metric", "value"))

        experiment = report.report.experiment
        benchmark = report.report.benchmark_context
        acceptance = report.report.acceptance
        preset = report.preset

        rows: list[tuple[str, str, object]] = [
            (
                "metadata",
                "interpretation",
                report.interpretation,
            ),
            (
                "metadata",
                "experiment_id",
                experiment.experiment_id,
            ),
            (
                "metadata",
                "created_at",
                experiment.created_at,
            ),
            (
                "metadata",
                "dataset_id",
                experiment.dataset_id,
            ),
            (
                "strategy",
                "name",
                experiment.strategy_name,
            ),
            (
                "strategy",
                "version",
                experiment.strategy_version,
            ),
            (
                "strategy",
                "horizon_candles",
                experiment.horizon_candles,
            ),
            (
                "performance",
                "generated_signals",
                experiment.generated_signals,
            ),
            (
                "performance",
                "total_trades",
                experiment.total_trades,
            ),
            (
                "performance",
                "net_pnl",
                experiment.net_pnl,
            ),
            (
                "performance",
                "total_return",
                experiment.total_return,
            ),
            (
                "performance",
                "win_rate",
                experiment.win_rate,
            ),
            (
                "performance",
                "max_drawdown_fraction",
                experiment.max_drawdown_fraction,
            ),
            (
                "performance",
                "profit_factor",
                experiment.profit_factor,
            ),
            (
                "benchmark",
                "type",
                benchmark.benchmark_type,
            ),
            (
                "benchmark",
                "return",
                benchmark.benchmark_return,
            ),
            (
                "benchmark",
                "excess_return",
                benchmark.excess_return,
            ),
            (
                "benchmark",
                "comparison_outcome",
                benchmark.comparison_outcome,
            ),
            (
                "benchmark",
                "strategy_max_drawdown_fraction",
                benchmark.strategy_max_drawdown_fraction,
            ),
            (
                "benchmark",
                "benchmark_max_drawdown_fraction",
                benchmark.benchmark_max_drawdown_fraction,
            ),
            (
                "benchmark",
                "drawdown_comparison",
                benchmark.drawdown_comparison,
            ),
            (
                "acceptance",
                "outcome",
                acceptance.outcome,
            ),
            (
                "acceptance",
                "passed_checks",
                report.report.passed_checks,
            ),
            (
                "acceptance",
                "failed_checks",
                report.report.failed_checks,
            ),
            (
                "acceptance_policy",
                "minimum_total_trades",
                acceptance.policy.minimum_total_trades,
            ),
            (
                "acceptance_policy",
                "minimum_excess_return",
                acceptance.policy.minimum_excess_return,
            ),
            (
                "acceptance_policy",
                "maximum_drawdown_fraction",
                acceptance.policy.maximum_drawdown_fraction,
            ),
            (
                "policy_preset",
                "preset_id",
                preset.preset_id,
            ),
            (
                "policy_preset",
                "name",
                preset.name,
            ),
            (
                "policy_preset",
                "version",
                preset.version,
            ),
        ]

        rows.extend(
            (
                "strategy_parameter",
                parameter.name,
                parameter.value,
            )
            for parameter in experiment.parameters
        )

        for check in acceptance.checks:
            prefix = check.name.value

            rows.extend(
                (
                    (
                        "acceptance_check",
                        f"{prefix}.passed",
                        check.passed,
                    ),
                    (
                        "acceptance_check",
                        f"{prefix}.actual",
                        check.actual_value,
                    ),
                    (
                        "acceptance_check",
                        f"{prefix}.threshold",
                        check.threshold_value,
                    ),
                    (
                        "acceptance_check",
                        f"{prefix}.comparison",
                        check.comparison,
                    ),
                )
            )

        writer.writerows(
            (
                section,
                metric,
                self._stringify(value),
            )
            for section, metric, value in rows
        )

        return output.getvalue()

    @staticmethod
    def _stringify(value: object) -> str:
        if value is None:
            return ""

        if isinstance(value, bool):
            return str(value).lower()

        if isinstance(value, datetime):
            return value.isoformat()

        if isinstance(value, Decimal):
            return format(value, "f")

        if isinstance(value, Enum):
            return str(value.value)

        return str(value)
