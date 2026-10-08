import { CategoryBarChart } from '@/components/charts/category-bar-chart';
import { CHART_SERIES_COLORS } from '@/components/charts/chart-colors';
import { ResponsiveChartGroup } from '@/components/charts/responsive-chart-group';
import type { PlatformLocale } from '@/platform/i18n';
import type { WalkForwardStabilityReport } from '@/features/walk-forward/api/types';
import { getWalkForwardDetailCopy } from '@/features/walk-forward/walk-forward-detail-copy';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui';

type WalkForwardAnalyticsChartsProps = {
  locale: PlatformLocale;
  stability: WalkForwardStabilityReport;
};

function formatPercent(value: number, locale: PlatformLocale): string {
  return new Intl.NumberFormat(locale === 'fa' ? 'fa-IR' : 'en-US', {
    style: 'percent',
    maximumFractionDigits: 2,
  }).format(value);
}

function foldLabel(foldNumber: number, locale: PlatformLocale): string {
  const formatted = new Intl.NumberFormat(locale === 'fa' ? 'fa-IR' : 'en-US').format(foldNumber);
  return `Fold ${formatted}`;
}

export function WalkForwardAnalyticsCharts({ locale, stability }: WalkForwardAnalyticsChartsProps) {
  const copy = getWalkForwardDetailCopy(locale);
  const benchmarkReturns = stability.folds.map((fold) => Number(fold.benchmark_return));
  const benchmarkDrawdowns = stability.folds.map((fold) =>
    Number(fold.benchmark_max_drawdown_fraction),
  );
  const averageBenchmarkReturn =
    benchmarkReturns.length === 0
      ? null
      : benchmarkReturns.reduce((total, value) => total + value, 0) / benchmarkReturns.length;
  const worstBenchmarkDrawdown =
    benchmarkDrawdowns.length === 0 ? null : Math.max(...benchmarkDrawdowns);
  const displayPercent = (value: number | null): string =>
    value === null ? copy.emptyFoldChart : formatPercent(value, locale);

  return (
    <Card>
      <CardHeader>
        <CardTitle>{copy.analyticsCharts}</CardTitle>
        <CardDescription>{copy.analyticsChartsDescription}</CardDescription>
      </CardHeader>

      <CardContent>
        <ResponsiveChartGroup
          selectorLabel={copy.chartMetricSelector}
          items={[
            {
              id: 'returns',
              label: copy.foldReturnsChart,
              summary: (
                <dl className="grid grid-cols-2 gap-3">
                  <div>
                    <dt className="text-xs text-app-muted">{copy.strategySeries}</dt>
                    <dd dir="ltr" className="mt-1 text-left font-semibold tabular-nums">
                      {formatPercent(Number(stability.average_strategy_return), locale)}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs text-app-muted">{copy.benchmarkSeries}</dt>
                    <dd dir="ltr" className="mt-1 text-left font-semibold tabular-nums">
                      {displayPercent(averageBenchmarkReturn)}
                    </dd>
                  </div>
                </dl>
              ),
              chart: (
                <CategoryBarChart
                  ariaLabel={copy.foldReturnsChart}
                  emptyLabel={copy.emptyFoldChart}
                  minimumDomainSpan={0.01}
                  formatValue={(value) => formatPercent(value, locale)}
                  series={[
                    {
                      label: copy.strategySeries,
                      color: CHART_SERIES_COLORS.cyan,
                      points: stability.folds.map((fold) => ({
                        category: foldLabel(fold.fold_number, locale),
                        value: Number(fold.strategy_return),
                      })),
                    },
                    {
                      label: copy.benchmarkSeries,
                      color: CHART_SERIES_COLORS.amber,
                      points: stability.folds.map((fold) => ({
                        category: foldLabel(fold.fold_number, locale),
                        value: Number(fold.benchmark_return),
                      })),
                    },
                  ]}
                />
              ),
            },
            {
              id: 'drawdowns',
              label: copy.foldDrawdownsChart,
              summary: (
                <dl className="grid grid-cols-2 gap-3">
                  <div>
                    <dt className="text-xs text-app-muted">{copy.strategySeries}</dt>
                    <dd dir="ltr" className="mt-1 text-left font-semibold tabular-nums">
                      {formatPercent(Number(stability.worst_max_drawdown_fraction), locale)}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs text-app-muted">{copy.benchmarkSeries}</dt>
                    <dd dir="ltr" className="mt-1 text-left font-semibold tabular-nums">
                      {displayPercent(worstBenchmarkDrawdown)}
                    </dd>
                  </div>
                </dl>
              ),
              chart: (
                <CategoryBarChart
                  ariaLabel={copy.foldDrawdownsChart}
                  emptyLabel={copy.emptyFoldChart}
                  minimumDomainSpan={0.01}
                  formatValue={(value) => formatPercent(value, locale)}
                  series={[
                    {
                      label: copy.strategySeries,
                      color: CHART_SERIES_COLORS.blue,
                      points: stability.folds.map((fold) => ({
                        category: foldLabel(fold.fold_number, locale),
                        value: Number(fold.max_drawdown_fraction),
                      })),
                    },
                    {
                      label: copy.benchmarkSeries,
                      color: CHART_SERIES_COLORS.rose,
                      points: stability.folds.map((fold) => ({
                        category: foldLabel(fold.fold_number, locale),
                        value: Number(fold.benchmark_max_drawdown_fraction),
                      })),
                    },
                  ]}
                />
              ),
            },
          ]}
        />
      </CardContent>
    </Card>
  );
}
