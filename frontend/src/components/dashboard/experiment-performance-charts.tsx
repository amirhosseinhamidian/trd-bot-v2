import {
  HistoricalLineChart,
  type HistoricalChartSeries,
} from '@/components/charts/historical-line-chart';
import {
  experimentDetailCopy,
  type ExperimentDetailLocale,
} from '@/components/dashboard/experiment-detail-copy';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui';
import type { ExperimentPerformanceSeries, HistoricalEquityPoint } from '@/lib/api/types';

type ExperimentPerformanceChartsProps = {
  locale: ExperimentDetailLocale;
  performanceSeries: ExperimentPerformanceSeries;
};

function formatBalance(value: number, locale: ExperimentDetailLocale): string {
  return new Intl.NumberFormat(locale === 'fa' ? 'fa-IR' : 'en-US', {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  }).format(value);
}

function formatPercent(value: number, locale: ExperimentDetailLocale): string {
  return new Intl.NumberFormat(locale === 'fa' ? 'fa-IR' : 'en-US', {
    style: 'percent',
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  }).format(value);
}

function formatDate(value: string, locale: ExperimentDetailLocale): string {
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

function toBalancePoints(points: HistoricalEquityPoint[]) {
  return points.map((point) => ({
    timestamp: point.timestamp,
    value: Number(point.balance),
  }));
}

function toDrawdownPoints(points: HistoricalEquityPoint[]) {
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
      color: '#22d3ee',
      points: toBalancePoints(performanceSeries.strategy.points),
    },
    {
      label: copy.benchmarkSeries,
      color: '#f59e0b',
      points: toBalancePoints(performanceSeries.benchmark.points),
    },
  ];

  const drawdownSeries: HistoricalChartSeries[] = [
    {
      label: copy.strategySeries,
      color: '#38bdf8',
      points: toDrawdownPoints(performanceSeries.strategy.points),
    },
    {
      label: copy.benchmarkSeries,
      color: '#fb7185',
      points: toDrawdownPoints(performanceSeries.benchmark.points),
    },
  ];

  return (
    <Card>
      <CardHeader>
        <CardTitle>{copy.charts}</CardTitle>
        <CardDescription>{copy.chartsDescription}</CardDescription>
      </CardHeader>

      <CardContent className="space-y-8">
        <section>
          <div className="mb-4">
            <h3 className="text-base font-semibold text-app-foreground">{copy.equityChart}</h3>

            <p className="mt-1 text-sm leading-6 text-app-muted">{copy.equityChartDescription}</p>
          </div>

          <HistoricalLineChart
            ariaLabel={copy.equityChart}
            emptyLabel={copy.emptyChart}
            series={equitySeries}
            minimumDomainSpan={1}
            formatDate={(value) => formatDate(value, locale)}
            formatValue={(value) => formatBalance(value, locale)}
          />
        </section>

        <section className="border-t border-app-border pt-8">
          <div className="mb-4">
            <h3 className="text-base font-semibold text-app-foreground">{copy.drawdownChart}</h3>

            <p className="mt-1 text-sm leading-6 text-app-muted">{copy.drawdownChartDescription}</p>
          </div>

          <HistoricalLineChart
            ariaLabel={copy.drawdownChart}
            clampMinimumToZero
            emptyLabel={copy.emptyChart}
            series={drawdownSeries}
            minimumDomainSpan={0.01}
            formatDate={(value) => formatDate(value, locale)}
            formatValue={(value) => formatPercent(value, locale)}
          />
        </section>
      </CardContent>
    </Card>
  );
}
