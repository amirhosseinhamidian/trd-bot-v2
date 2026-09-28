import Link from 'next/link';

import type { DashboardLocale } from '@/components/dashboard/dashboard-copy';
import { getSignalsCopy } from '@/components/dashboard/signals-copy';
import { Badge, Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui';
import type { ExperimentSummary, SignalDirection, StrategySignal } from '@/lib/api/types';
import { getStrategyDisplayName } from '@/lib/strategies/presentation';

type SignalDetailProps = {
  experiment: ExperimentSummary;
  locale: DashboardLocale;
  signal: StrategySignal;
};

function formatDate(value: string, locale: DashboardLocale): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat(locale === 'fa' ? 'fa-IR' : 'en-US', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date);
}

function formatDecimal(value: string, locale: DashboardLocale): string {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) {
    return value;
  }
  return new Intl.NumberFormat(locale === 'fa' ? 'fa-IR' : 'en-US', {
    maximumFractionDigits: 6,
  }).format(numeric);
}

function directionVariant(direction: SignalDirection): 'success' | 'danger' | 'neutral' {
  if (direction === 'long') {
    return 'success';
  }
  if (direction === 'short') {
    return 'danger';
  }
  return 'neutral';
}

export default function SignalDetail({ experiment, locale, signal }: SignalDetailProps) {
  const copy = getSignalsCopy(locale);
  const back = locale === 'fa' ? 'بازگشت به سیگنال‌ها' : 'Back to signals';
  const sourceTitle = locale === 'fa' ? 'منابع lineage' : 'Lineage sources';
  const viewDataset = locale === 'fa' ? 'مشاهده Dataset' : 'View dataset';
  const viewExperiment = locale === 'fa' ? 'مشاهده Experiment' : 'View experiment';

  return (
    <div className="space-y-8">
      <section>
        <Link
          href={`/${locale}/signals`}
          className="text-sm font-semibold text-app-accent hover:opacity-80"
        >
          {locale === 'fa' ? '→' : '←'} {back}
        </Link>

        <div className="mt-5 flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-xs font-semibold tracking-[0.25em] text-app-accent uppercase">
              {copy.eyebrow}
            </p>
            <h1 className="mt-3 text-3xl font-bold text-app-foreground">
              {getStrategyDisplayName(signal.strategy_name, locale)}
            </h1>
            <p dir="ltr" className="mt-2 text-left text-xs font-semibold text-app-muted">
              {signal.signal_id}
            </p>
          </div>
          <div className="flex gap-2">
            <Badge variant="warning">{copy.historicalOnly}</Badge>
            <Badge variant={directionVariant(signal.direction)}>
              {copy.directions[signal.direction]}
            </Badge>
          </div>
        </div>
      </section>

      <Card>
        <CardHeader>
          <CardTitle>
            {signal.pair.base_asset}/{signal.pair.quote_asset}
          </CardTitle>
          <CardDescription>{signal.strategy_version}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <dl className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <div>
              <dt className="text-xs text-app-muted">{copy.fields.score}</dt>
              <dd dir="ltr" className="mt-1 text-left font-semibold text-app-foreground">
                {formatDecimal(signal.score, locale)}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-app-muted">{copy.fields.timeframe}</dt>
              <dd className="mt-1 text-app-foreground">{signal.timeframe}</dd>
            </div>
            <div>
              <dt className="text-xs text-app-muted">{copy.fields.candleClose}</dt>
              <dd className="mt-1 text-app-foreground">
                {formatDate(signal.candle_close_time, locale)}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-app-muted">{copy.fields.generatedAt}</dt>
              <dd className="mt-1 text-app-foreground">
                {formatDate(signal.generated_at, locale)}
              </dd>
            </div>
          </dl>

          <div className="rounded-xl border border-app-border bg-app-surface-muted p-4">
            <p className="text-xs text-app-muted">{copy.fields.reason}</p>
            <p className="mt-2 text-sm leading-7 text-app-foreground">{signal.reason}</p>
          </div>

          <div>
            <p className="text-xs text-app-muted">{copy.fields.features}</p>
            <div className="mt-3 flex flex-wrap gap-2">
              {signal.features.map((feature) => (
                <Badge key={feature.name} variant="neutral">
                  {feature.name}={formatDecimal(feature.value, locale)}
                </Badge>
              ))}
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{sourceTitle}</CardTitle>
          <CardDescription dir="ltr">{experiment.experiment_id}</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-3">
          <Link
            href={`/${locale}/datasets/${encodeURIComponent(signal.dataset_id)}`}
            className="rounded-xl border border-app-border px-4 py-2 text-sm font-semibold text-app-accent hover:bg-app-hover"
          >
            {viewDataset}
          </Link>
          <Link
            href={`/${locale}/experiments/${encodeURIComponent(experiment.experiment_id)}`}
            className="rounded-xl border border-app-border px-4 py-2 text-sm font-semibold text-app-accent hover:bg-app-hover"
          >
            {viewExperiment}
          </Link>
        </CardContent>
      </Card>
    </div>
  );
}
