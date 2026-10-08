import {
  HistoricalLineChart,
  type HistoricalChartSeries,
} from '@/components/charts/historical-line-chart';
import { CHART_SERIES_COLORS } from '@/components/charts/chart-colors';
import { ResponsiveChartGroup } from '@/components/charts/responsive-chart-group';
import { experimentDetailCopy } from '@/features/experiments/experiment-detail-copy';
import type {
  ExperimentPerformanceSeries,
  HistoricalPerformancePoint,
} from '@/features/experiments/api/types';
import type { PlatformLocale } from '@/platform/i18n';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui';

type ExperimentPerformanceChartsProps = {
  locale: PlatformLocale;
  performanceSeries: ExperimentPerformanceSeries;
};

function formatBalance(value: number, locale: PlatformLocale): string {
  return new Intl.NumberFormat(locale === 'fa' ? 'fa-IR' : 'en-US', {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  }).format(value);
}

function formatPercent(value: number, locale: PlatformLocale): string {
  return new Intl.NumberFormat(locale === 'fa' ? 'fa-IR' : 'en-US', {
    style: 'percent',
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  }).format(value);
}

function formatDate(value: string, locale: PlatformLocale): string {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat(locale === 'fa' ? 'fa-IR' : 'en-US', {
    month: 'short',
    day: 'numeric',
    year: '2-digit',
  }).format(date);
}

function toBalancePoints(points: HistoricalPerformancePoint[]) {
  return points.map((point) => ({
    timestamp: point.timestamp,
    value: Number(point.balance),
  }));
}

function toDrawdownPoints(points: HistoricalPerformancePoint[]) {
  return points.map((point) => ({
    timestamp: point.timestamp,
    value: Number(point.drawdown_fraction),
  }));
}

export function ExperimentPerformanceCharts({
  locale,
  performanceSeries,
}: ExperimentPerformanceChartsProps) {
  const copy = experimentDetailCopy[locale];

  const equitySeries: HistoricalChartSeries[] = [
    {
      label: copy.strategySeries,
      color: CHART_SERIES_COLORS.cyan,
      curve: 'step_after',
      points: toBalancePoints(performanceSeries.strategy.chart_points),
    },
    {
      label: copy.benchmarkSeries,
      color: CHART_SERIES_COLORS.amber,
      curve: 'step_after',
      points: toBalancePoints(performanceSeries.benchmark.chart_points),
    },
  ];

  const drawdownSeries: HistoricalChartSeries[] = [
    {
      label: copy.strategySeries,
      color: CHART_SERIES_COLORS.blue,
      curve: 'step_after',
      points: toDrawdownPoints(performanceSeries.strategy.chart_points),
    },
    {
      label: copy.benchmarkSeries,
      color: CHART_SERIES_COLORS.rose,
      curve: 'step_after',
      points: toDrawdownPoints(performanceSeries.benchmark.chart_points),
    },
  ];

  return (
    <Card>
      <CardHeader>
        <CardTitle>{copy.charts}</CardTitle>
        <CardDescription>{copy.chartsDescription}</CardDescription>
      </CardHeader>

      <CardContent>
        <ResponsiveChartGroup
          selectorLabel={copy.chartMetricSelector}
          items={[
            {
              id: 'equity',
              label: copy.equityChart,
              description: copy.equityChartDescription,
              summary: (
                <dl className="grid grid-cols-2 gap-3">
                  <div>
                    <dt className="text-xs text-app-muted">{copy.strategySeries}</dt>
                    <dd dir="ltr" className="mt-1 text-left font-semibold tabular-nums">
                      {formatBalance(Number(performanceSeries.strategy.ending_balance), locale)}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs text-app-muted">{copy.benchmarkSeries}</dt>
                    <dd dir="ltr" className="mt-1 text-left font-semibold tabular-nums">
                      {formatBalance(Number(performanceSeries.benchmark.ending_balance), locale)}
                    </dd>
                  </div>
                </dl>
              ),
              chart: (
                <HistoricalLineChart
                  ariaLabel={copy.equityChart}
                  emptyLabel={copy.emptyChart}
                  series={equitySeries}
                  minimumDomainSpan={1}
                  formatDate={(value) => formatDate(value, locale)}
                  formatValue={(value) => formatBalance(value, locale)}
                />
              ),
            },
            {
              id: 'drawdown',
              label: copy.drawdownChart,
              description: copy.drawdownChartDescription,
              summary: (
                <dl className="grid grid-cols-2 gap-3">
                  <div>
                    <dt className="text-xs text-app-muted">{copy.strategySeries}</dt>
                    <dd dir="ltr" className="mt-1 text-left font-semibold tabular-nums">
                      {formatPercent(
                        Number(performanceSeries.strategy.max_drawdown_fraction),
                        locale,
                      )}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs text-app-muted">{copy.benchmarkSeries}</dt>
                    <dd dir="ltr" className="mt-1 text-left font-semibold tabular-nums">
                      {formatPercent(
                        Number(performanceSeries.benchmark.max_drawdown_fraction),
                        locale,
                      )}
                    </dd>
                  </div>
                </dl>
              ),
              chart: (
                <HistoricalLineChart
                  ariaLabel={copy.drawdownChart}
                  clampMinimumToZero
                  emptyLabel={copy.emptyChart}
                  series={drawdownSeries}
                  minimumDomainSpan={0.01}
                  formatDate={(value) => formatDate(value, locale)}
                  formatValue={(value) => formatPercent(value, locale)}
                />
              ),
            },
          ]}
        />
      </CardContent>
    </Card>
  );
}
