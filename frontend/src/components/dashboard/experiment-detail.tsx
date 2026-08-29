import Link from 'next/link';

import {
  experimentDetailCopy,
  type ExperimentDetailLocale,
} from '@/components/dashboard/experiment-detail-copy';
import { Badge, type BadgeVariant } from '@/components/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import type {
  AcceptancePolicyPreset,
  ExperimentPerformanceSeries,
  ExperimentSummary,
} from '@/lib/api/types';
import { ExperimentAcceptancePanel } from '@/components/dashboard/experiment-acceptance-panel';
import { ExperimentPerformanceCharts } from '@/components/dashboard/experiment-performance-charts';
import { buildExperimentRerunHref } from '@/lib/experiments/run-params';

type ExperimentDetailProps = {
  experiment: ExperimentSummary;
  locale: ExperimentDetailLocale;
  acceptancePolicyPresets: AcceptancePolicyPreset[];
  performanceSeries: ExperimentPerformanceSeries;
};

type MetricProps = {
  label: string;
  value: string;
};

function formatInteger(value: number, locale: ExperimentDetailLocale): string {
  return new Intl.NumberFormat(locale === 'fa' ? 'fa-IR' : 'en-US').format(value);
}

function formatDecimal(
  value: string | null,
  locale: ExperimentDetailLocale,
  maximumFractionDigits = 4,
): string {
  if (value === null) {
    return experimentDetailCopy[locale].unavailable;
  }

  const parsedValue = Number(value);

  if (!Number.isFinite(parsedValue)) {
    return value;
  }

  return new Intl.NumberFormat(locale === 'fa' ? 'fa-IR' : 'en-US', {
    maximumFractionDigits,
  }).format(parsedValue);
}

function formatPercent(value: string | null, locale: ExperimentDetailLocale): string {
  if (value === null) {
    return experimentDetailCopy[locale].unavailable;
  }

  const parsedValue = Number(value);

  if (!Number.isFinite(parsedValue)) {
    return value;
  }

  return new Intl.NumberFormat(locale === 'fa' ? 'fa-IR' : 'en-US', {
    style: 'percent',
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  }).format(parsedValue);
}

function formatDate(value: string, locale: ExperimentDetailLocale): string {
  return new Intl.DateTimeFormat(locale === 'fa' ? 'fa-IR' : 'en-US', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value));
}

function Metric({ label, value }: MetricProps) {
  return (
    <div className="rounded-xl border border-app-border bg-app-surface-muted p-4">
      <dt className="text-sm text-app-muted">{label}</dt>
      <dd className="mt-2 text-lg font-semibold text-app-foreground">{value}</dd>
    </div>
  );
}

function comparisonPresentation(
  outcome: ExperimentSummary['comparison_outcome'],
  locale: ExperimentDetailLocale,
): {
  label: string;
  variant: BadgeVariant;
} {
  const copy = experimentDetailCopy[locale];

  if (outcome === 'strategy') {
    return {
      label: copy.strategyWon,
      variant: 'success',
    };
  }

  if (outcome === 'benchmark') {
    return {
      label: copy.benchmarkWon,
      variant: 'warning',
    };
  }

  return {
    label: copy.tie,
    variant: 'neutral',
  };
}

export function ExperimentDetail({
  acceptancePolicyPresets,
  experiment,
  locale,
  performanceSeries,
}: ExperimentDetailProps) {
  const copy = experimentDetailCopy[locale];
  const direction = locale === 'fa' ? 'rtl' : 'ltr';
  const comparison = comparisonPresentation(experiment.comparison_outcome, locale);
  const rerunHref = buildExperimentRerunHref(experiment, locale);

  return (
    <main dir={direction} className="mx-auto w-full max-w-7xl space-y-6 px-4 py-6 sm:px-6 lg:px-8">
      <div className="flex flex-col gap-5 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <Link
            href={`/${locale}/experiments`}
            className="text-sm font-medium text-app-accent transition hover:text-app-accent"
          >
            ← {copy.back}
          </Link>

          <p className="mt-5 text-sm font-medium text-app-accent">{copy.eyebrow}</p>

          <h1 className="mt-2 text-2xl font-bold text-app-foreground sm:text-3xl">
            {experiment.strategy_name}
          </h1>

          <p dir="ltr" className="mt-2 text-sm font-semibold break-all text-app-muted">
            {experiment.experiment_id}
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <Badge variant="info">{copy.historicalOnly}</Badge>

          <Link
            href={rerunHref}
            className="inline-flex min-h-10 items-center justify-center rounded-xl border border-app-accent-border bg-app-accent-soft px-4 py-2.5 text-sm font-semibold text-app-accent transition hover:border-app-accent-border hover:bg-app-hover hover:text-app-accent focus-visible:ring-2 focus-visible:ring-app-accent focus-visible:outline-none"
          >
            {copy.runAgain}
          </Link>
        </div>
      </div>

      <Card className="border-app-warning-border bg-app-warning-soft">
        <CardContent className="pt-6">
          <p className="text-sm leading-7 text-app-warning">{copy.disclaimer}</p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{copy.strategyInformation}</CardTitle>
          <CardDescription>{copy.strategyDescription}</CardDescription>
        </CardHeader>

        <CardContent>
          <dl className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            <Metric label={copy.strategy} value={experiment.strategy_name} />

            <Metric label={copy.version} value={experiment.strategy_version} />

            <Metric
              label={copy.horizon}
              value={`${formatInteger(experiment.horizon_candles, locale)} ${copy.horizonUnit}`}
            />

            <Metric label={copy.createdAt} value={formatDate(experiment.created_at, locale)} />

            <div className="rounded-xl border border-app-border bg-app-surface-muted p-4 sm:col-span-2">
              <dt className="text-sm text-app-muted">{copy.datasetId}</dt>
              <dd dir="ltr" className="mt-2 text-sm font-semibold break-all text-app-foreground">
                {experiment.dataset_id}
              </dd>
            </div>
          </dl>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{copy.performance}</CardTitle>
          <CardDescription>{copy.performanceDescription}</CardDescription>
        </CardHeader>

        <CardContent>
          <dl className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Metric
              label={copy.totalReturn}
              value={formatPercent(experiment.total_return, locale)}
            />

            <Metric
              label={copy.excessReturn}
              value={formatPercent(experiment.excess_return, locale)}
            />

            <Metric
              label={copy.maxDrawdown}
              value={formatPercent(experiment.max_drawdown_fraction, locale)}
            />

            <Metric label={copy.winRate} value={formatPercent(experiment.win_rate, locale)} />

            <Metric label={copy.netPnl} value={formatDecimal(experiment.net_pnl, locale)} />

            <Metric
              label={copy.profitFactor}
              value={formatDecimal(experiment.profit_factor, locale)}
            />

            <Metric
              label={copy.totalTrades}
              value={formatInteger(experiment.total_trades, locale)}
            />

            <Metric
              label={copy.generatedSignals}
              value={formatInteger(experiment.generated_signals, locale)}
            />
          </dl>
        </CardContent>
      </Card>

      <ExperimentPerformanceCharts locale={locale} performanceSeries={performanceSeries} />

      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <CardTitle>{copy.comparison}</CardTitle>
              <CardDescription className="mt-1.5">{copy.comparisonDescription}</CardDescription>
            </div>

            <Badge variant={comparison.variant}>{comparison.label}</Badge>
          </div>
        </CardHeader>

        <CardContent>
          <dl className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Metric label={copy.benchmark} value={copy.buyAndHold} />

            <Metric
              label={copy.benchmarkReturn}
              value={formatPercent(experiment.benchmark_return, locale)}
            />

            <Metric
              label={copy.drawdownDelta}
              value={formatPercent(experiment.max_drawdown_fraction_delta, locale)}
            />

            <Metric
              label={copy.lowerDrawdown}
              value={experiment.strategy_has_lower_drawdown ? copy.yes : copy.no}
            />
          </dl>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{copy.parameters}</CardTitle>
          <CardDescription>{copy.parametersDescription}</CardDescription>
        </CardHeader>

        <CardContent>
          {experiment.parameters.length > 0 ? (
            <dl className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {experiment.parameters.map((parameter) => (
                <div
                  key={parameter.name}
                  className="rounded-xl border border-app-border bg-app-surface-muted p-4"
                >
                  <dt dir="ltr" className="text-xs font-semibold break-all text-app-muted">
                    {parameter.name}
                  </dt>

                  <dd dir="ltr" className="mt-2 text-sm font-semibold break-all text-app-accent">
                    {parameter.value}
                  </dd>
                </div>
              ))}
            </dl>
          ) : (
            <p className="text-sm text-app-muted">{copy.unavailable}</p>
          )}
        </CardContent>
      </Card>
      <ExperimentAcceptancePanel
        experimentId={experiment.experiment_id}
        locale={locale}
        presets={acceptancePolicyPresets}
      />
    </main>
  );
}
