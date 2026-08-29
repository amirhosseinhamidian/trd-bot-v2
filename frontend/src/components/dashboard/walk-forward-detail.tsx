import Link from 'next/link';

import type { DashboardLocale } from '@/components/dashboard/dashboard-copy';
import { getWalkForwardDetailCopy } from '@/components/dashboard/walk-forward-detail-copy';
import {
  Badge,
  type BadgeVariant,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui';
import type {
  HistoricalFoldReturnDirection,
  WalkForwardRunSummary,
  WalkForwardStabilityReport,
} from '@/lib/api/types';

type WalkForwardDetailProps = {
  locale: DashboardLocale;
  run: WalkForwardRunSummary;
  stability: WalkForwardStabilityReport;
};

type MetricProps = {
  label: string;
  value: string;
};

function formatNumber(value: number, locale: DashboardLocale): string {
  return new Intl.NumberFormat(locale === 'fa' ? 'fa-IR' : 'en-US').format(value);
}

function formatPercent(value: string, locale: DashboardLocale): string {
  const parsedValue = Number(value);

  if (!Number.isFinite(parsedValue)) {
    return value;
  }

  return new Intl.NumberFormat(locale === 'fa' ? 'fa-IR' : 'en-US', {
    style: 'percent',
    maximumFractionDigits: 2,
  }).format(parsedValue);
}

function formatDate(value: string, locale: DashboardLocale): string {
  return new Intl.DateTimeFormat(locale === 'fa' ? 'fa-IR' : 'en-US', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value));
}

function directionVariant(direction: HistoricalFoldReturnDirection): BadgeVariant {
  if (direction === 'positive') {
    return 'success';
  }

  if (direction === 'negative') {
    return 'danger';
  }

  return 'neutral';
}

function Metric({ label, value }: MetricProps) {
  return (
    <div className="rounded-xl border border-app-border bg-app-surface-muted p-4">
      <dt className="text-xs text-app-muted">{label}</dt>
      <dd className="mt-2 text-lg font-semibold text-app-foreground">{value}</dd>
    </div>
  );
}

export function WalkForwardDetail({ locale, run, stability }: WalkForwardDetailProps) {
  const copy = getWalkForwardDetailCopy(locale);
  const direction = locale === 'fa' ? 'rtl' : 'ltr';

  return (
    <div dir={direction} className="space-y-6">
      <section>
        <Link
          href={`/${locale}/walk-forward`}
          className="text-sm font-medium text-app-accent transition hover:text-app-accent"
        >
          <span aria-hidden="true">{locale === 'fa' ? '→' : '←'}</span> {copy.back}
        </Link>

        <div className="mt-5 flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-sm font-medium text-app-accent">{copy.eyebrow}</p>

            <h1 className="mt-2 text-2xl font-bold text-app-foreground sm:text-3xl">
              {run.strategy_name}
            </h1>

            <p dir="ltr" className="mt-2 text-sm font-semibold break-all text-app-muted">
              {run.execution_id}
            </p>
          </div>

          <Badge variant="warning">{copy.historicalOnly}</Badge>
        </div>
      </section>

      <Card className="border-app-warning-border bg-app-warning-soft">
        <CardContent className="pt-6">
          <p className="text-sm leading-7 text-app-warning">{copy.disclaimer}</p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{copy.summary}</CardTitle>
          <CardDescription>{copy.summaryDescription}</CardDescription>
        </CardHeader>

        <CardContent>
          <dl className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Metric label={copy.fields.strategy} value={run.strategy_name} />

            <Metric label={copy.fields.version} value={run.strategy_version} />

            <Metric label={copy.fields.horizon} value={formatNumber(run.horizon_candles, locale)} />

            <Metric label={copy.fields.createdAt} value={formatDate(run.created_at, locale)} />

            <Metric label={copy.fields.totalFolds} value={formatNumber(run.total_folds, locale)} />

            <Metric
              label={copy.fields.totalSignals}
              value={formatNumber(run.total_signals, locale)}
            />

            <Metric
              label={copy.fields.foldsWithTrades}
              value={formatNumber(run.folds_with_trades, locale)}
            />

            <Metric label={copy.fields.mode} value={copy.modes[run.walk_forward_config.mode]} />
          </dl>

          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <div className="rounded-xl border border-app-border bg-app-surface-muted p-4">
              <p className="text-xs text-app-muted">{copy.fields.datasetId}</p>
              <p dir="ltr" className="mt-2 text-xs font-semibold break-all text-app-foreground">
                {run.source_dataset_id}
              </p>
            </div>

            <div className="rounded-xl border border-app-border bg-app-surface-muted p-4">
              <p className="text-xs text-app-muted">{copy.fields.planId}</p>
              <p dir="ltr" className="mt-2 text-xs font-semibold break-all text-app-foreground">
                {run.plan_id}
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{copy.stability}</CardTitle>
          <CardDescription>{copy.stabilityDescription}</CardDescription>
        </CardHeader>

        <CardContent>
          <dl className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Metric
              label={copy.fields.positiveFraction}
              value={formatPercent(stability.positive_return_fraction, locale)}
            />

            <Metric
              label={copy.fields.averageReturn}
              value={formatPercent(stability.average_strategy_return, locale)}
            />

            <Metric
              label={copy.fields.medianReturn}
              value={formatPercent(stability.median_strategy_return, locale)}
            />

            <Metric
              label={copy.fields.averageExcessReturn}
              value={formatPercent(stability.average_excess_return, locale)}
            />

            <Metric
              label={copy.fields.bestReturn}
              value={formatPercent(stability.best_strategy_return, locale)}
            />

            <Metric
              label={copy.fields.worstReturn}
              value={formatPercent(stability.worst_strategy_return, locale)}
            />

            <Metric
              label={copy.fields.returnRange}
              value={formatPercent(stability.strategy_return_range, locale)}
            />

            <Metric
              label={copy.fields.meanAbsoluteDeviation}
              value={formatPercent(stability.strategy_return_mean_absolute_deviation, locale)}
            />

            <Metric
              label={copy.fields.medianExcessReturn}
              value={formatPercent(stability.median_excess_return, locale)}
            />

            <Metric
              label={copy.fields.worstDrawdown}
              value={formatPercent(stability.worst_max_drawdown_fraction, locale)}
            />

            <Metric
              label={copy.fields.outperformingFolds}
              value={formatNumber(stability.outperforming_benchmark_folds, locale)}
            />

            <Metric
              label={copy.fields.underperformingFolds}
              value={formatNumber(stability.underperforming_benchmark_folds, locale)}
            />
          </dl>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{copy.folds}</CardTitle>
          <CardDescription>{copy.foldsDescription}</CardDescription>
        </CardHeader>

        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{copy.fields.foldNumber}</TableHead>
                <TableHead>{copy.fields.trades}</TableHead>
                <TableHead>{copy.fields.strategyReturn}</TableHead>
                <TableHead>{copy.fields.benchmarkReturn}</TableHead>
                <TableHead>{copy.fields.excessReturn}</TableHead>
                <TableHead>{copy.fields.drawdown}</TableHead>
                <TableHead>{copy.fields.direction}</TableHead>
              </TableRow>
            </TableHeader>

            <TableBody>
              {stability.folds.map((fold) => (
                <TableRow key={fold.fold_number}>
                  <TableCell>{formatNumber(fold.fold_number, locale)}</TableCell>

                  <TableCell>{formatNumber(fold.total_trades, locale)}</TableCell>

                  <TableCell dir="ltr">{formatPercent(fold.strategy_return, locale)}</TableCell>

                  <TableCell dir="ltr">{formatPercent(fold.benchmark_return, locale)}</TableCell>

                  <TableCell dir="ltr">{formatPercent(fold.excess_return, locale)}</TableCell>

                  <TableCell dir="ltr">
                    {formatPercent(fold.max_drawdown_fraction, locale)}
                  </TableCell>

                  <TableCell>
                    <Badge variant={directionVariant(fold.return_direction)}>
                      {copy.directions[fold.return_direction]}
                    </Badge>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{copy.configuration}</CardTitle>
          <CardDescription>{copy.configurationDescription}</CardDescription>
        </CardHeader>

        <CardContent className="space-y-5">
          <dl className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Metric
              label={copy.fields.trainCandles}
              value={formatNumber(run.walk_forward_config.train_candles, locale)}
            />

            <Metric
              label={copy.fields.testCandles}
              value={formatNumber(run.walk_forward_config.test_candles, locale)}
            />

            <Metric
              label={copy.fields.stepCandles}
              value={formatNumber(run.walk_forward_config.step_candles, locale)}
            />

            <Metric
              label={copy.fields.gapCandles}
              value={formatNumber(run.walk_forward_config.gap_candles, locale)}
            />
          </dl>

          <div>
            <p className="text-xs text-app-muted">{copy.fields.parameters}</p>

            <div className="mt-3 flex flex-wrap gap-2">
              {run.strategy_parameters.map((parameter) => (
                <Badge key={parameter.name} variant="neutral">
                  {parameter.name}={parameter.value}
                </Badge>
              ))}
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
