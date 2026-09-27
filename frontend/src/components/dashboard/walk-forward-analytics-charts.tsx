import { CategoryBarChart } from '@/components/charts/category-bar-chart';
import type { DashboardLocale } from '@/components/dashboard/dashboard-copy';
import { getWalkForwardDetailCopy } from '@/components/dashboard/walk-forward-detail-copy';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui';
import type { WalkForwardStabilityReport } from '@/lib/api/types';

type WalkForwardAnalyticsChartsProps = {
  locale: DashboardLocale;
  stability: WalkForwardStabilityReport;
};

function formatPercent(value: number, locale: DashboardLocale): string {
  return new Intl.NumberFormat(locale === 'fa' ? 'fa-IR' : 'en-US', {
    style: 'percent',
    maximumFractionDigits: 2,
  }).format(value);
}

function foldLabel(foldNumber: number, locale: DashboardLocale): string {
  const formatted = new Intl.NumberFormat(locale === 'fa' ? 'fa-IR' : 'en-US').format(foldNumber);
  return `Fold ${formatted}`;
}

export function WalkForwardAnalyticsCharts({ locale, stability }: WalkForwardAnalyticsChartsProps) {
  const copy = getWalkForwardDetailCopy(locale);

  return (
    <Card>
      <CardHeader>
        <CardTitle>{copy.analyticsCharts}</CardTitle>
        <CardDescription>{copy.analyticsChartsDescription}</CardDescription>
      </CardHeader>

      <CardContent className="space-y-8">
        <section>
          <h3 className="mb-4 text-base font-semibold text-app-foreground">
            {copy.foldReturnsChart}
          </h3>
          <CategoryBarChart
            ariaLabel={copy.foldReturnsChart}
            emptyLabel={copy.emptyFoldChart}
            minimumDomainSpan={0.01}
            formatValue={(value) => formatPercent(value, locale)}
            series={[
              {
                label: copy.strategySeries,
                color: '#22d3ee',
                points: stability.folds.map((fold) => ({
                  category: foldLabel(fold.fold_number, locale),
                  value: Number(fold.strategy_return),
                })),
              },
              {
                label: copy.benchmarkSeries,
                color: '#f59e0b',
                points: stability.folds.map((fold) => ({
                  category: foldLabel(fold.fold_number, locale),
                  value: Number(fold.benchmark_return),
                })),
              },
            ]}
          />
        </section>

        <section className="border-t border-app-border pt-8">
          <h3 className="mb-4 text-base font-semibold text-app-foreground">
            {copy.foldDrawdownsChart}
          </h3>
          <CategoryBarChart
            ariaLabel={copy.foldDrawdownsChart}
            emptyLabel={copy.emptyFoldChart}
            minimumDomainSpan={0.01}
            formatValue={(value) => formatPercent(value, locale)}
            series={[
              {
                label: copy.strategySeries,
                color: '#38bdf8',
                points: stability.folds.map((fold) => ({
                  category: foldLabel(fold.fold_number, locale),
                  value: Number(fold.max_drawdown_fraction),
                })),
              },
              {
                label: copy.benchmarkSeries,
                color: '#fb7185',
                points: stability.folds.map((fold) => ({
                  category: foldLabel(fold.fold_number, locale),
                  value: Number(fold.benchmark_max_drawdown_fraction),
                })),
              },
            ]}
          />
        </section>
      </CardContent>
    </Card>
  );
}
