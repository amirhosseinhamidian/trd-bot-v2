'use client';

import { useRef, useState } from 'react';

import type { DashboardLocale } from '@/components/dashboard/dashboard-copy';
import SignalFilterPanel, {
  type SignalFilterValues,
} from '@/components/dashboard/signal-filter-panel';
import { getSignalsCopy } from '@/components/dashboard/signals-copy';
import {
  Badge,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  EmptyState,
  Pagination,
  Spinner,
  BadgeVariant,
  ErrorState,
} from '@/components/ui';
import { getExperimentSignals, type ExperimentSignalFilters } from '@/lib/api/client';
import type { ExperimentSummary, Page, SignalDirection, StrategySignal } from '@/lib/api/types';
import { getStrategyDisplayName } from '@/lib/strategies/presentation';

const PAGE_SIZE = 20;

type SignalCatalogProps = {
  experiments: ExperimentSummary[];
  initialExperimentId: string;
  initialPage: Page<StrategySignal>;
  locale: DashboardLocale;
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
  const parsedValue = Number(value);

  if (!Number.isFinite(parsedValue)) {
    return value;
  }

  return new Intl.NumberFormat(locale === 'fa' ? 'fa-IR' : 'en-US', {
    maximumFractionDigits: 6,
  }).format(parsedValue);
}

function startOfUtcDay(value: string): string | undefined {
  if (!value) {
    return undefined;
  }

  return new Date(`${value}T00:00:00.000Z`).toISOString();
}

function endOfUtcDay(value: string): string | undefined {
  if (!value) {
    return undefined;
  }

  return new Date(`${value}T23:59:59.999Z`).toISOString();
}

function buildApiFilters(filters: SignalFilterValues): ExperimentSignalFilters {
  return {
    direction: filters.direction === 'all' ? undefined : filters.direction,
    candleCloseTimeFrom: startOfUtcDay(filters.candleCloseTimeFrom),
    candleCloseTimeTo: endOfUtcDay(filters.candleCloseTimeTo),
    sortDirection: filters.sortDirection,
  };
}

function directionVariant(direction: SignalDirection): BadgeVariant {
  if (direction === 'long') {
    return 'success';
  }

  if (direction === 'short') {
    return 'danger';
  }

  return 'neutral';
}

export default function SignalCatalog({
  experiments,
  initialExperimentId,
  initialPage,
  locale,
}: SignalCatalogProps) {
  const copy = getSignalsCopy(locale);

  const [page, setPage] = useState(initialPage);
  const [appliedFilters, setAppliedFilters] = useState<SignalFilterValues>({
    experimentId: initialExperimentId,
    direction: 'all',
    candleCloseTimeFrom: '',
    candleCloseTimeTo: '',
    sortDirection: 'desc',
  });
  const [isLoading, setIsLoading] = useState(false);
  const [hasError, setHasError] = useState(false);

  const requestSequence = useRef(0);

  async function loadSignals(
    offset: number,
    filters: SignalFilterValues = appliedFilters,
  ): Promise<void> {
    if (!filters.experimentId) {
      return;
    }

    const requestId = ++requestSequence.current;

    setIsLoading(true);
    setHasError(false);

    try {
      const result = await getExperimentSignals(filters.experimentId, {
        ...buildApiFilters(filters),
        limit: PAGE_SIZE,
        offset,
      });

      if (requestId === requestSequence.current) {
        setPage(result);
      }
    } catch {
      if (requestId === requestSequence.current) {
        setHasError(true);
      }
    } finally {
      if (requestId === requestSequence.current) {
        setIsLoading(false);
      }
    }
  }

  function applyFilters(filters: SignalFilterValues): void {
    setAppliedFilters(filters);
    void loadSignals(0, filters);
  }

  return (
    <div className="space-y-8">
      <section>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-xs font-semibold tracking-[0.25em] text-app-accent uppercase">
              {copy.eyebrow}
            </p>

            <h1 className="mt-3 text-3xl font-bold tracking-tight text-app-foreground sm:text-4xl">
              {copy.title}
            </h1>
          </div>

          <div className="flex flex-wrap gap-2">
            <Badge variant="warning">{copy.historicalOnly}</Badge>

            <Badge variant="info">
              {copy.total}: {page.total}
            </Badge>
          </div>
        </div>

        <p className="mt-3 max-w-3xl text-sm leading-7 text-app-muted sm:text-base">
          {copy.description}
        </p>

        <p className="mt-5 rounded-2xl border border-app-warning-border bg-app-warning-soft p-4 text-sm leading-7 text-app-warning">
          {copy.disclaimer}
        </p>
      </section>

      <SignalFilterPanel
        experiments={experiments}
        initialExperimentId={initialExperimentId}
        isLoading={isLoading}
        locale={locale}
        onApply={applyFilters}
      />

      <section className="relative min-h-64" aria-busy={isLoading}>
        {isLoading ? (
          <div className="absolute inset-0 z-20 flex items-center justify-center rounded-2xl bg-app-overlay backdrop-blur-sm">
            <Spinner size="lg" label={copy.loading} className="text-app-accent" />
          </div>
        ) : null}

        {experiments.length === 0 ? (
          <EmptyState
            title={copy.emptyExperimentsTitle}
            description={copy.emptyExperimentsDescription}
          />
        ) : hasError ? (
          <ErrorState
            title={copy.errorTitle}
            description={copy.errorDescription}
            retryLabel={copy.retry}
            onRetry={() => void loadSignals(page.offset)}
          />
        ) : page.items.length === 0 ? (
          <EmptyState title={copy.emptySignalsTitle} description={copy.emptySignalsDescription} />
        ) : (
          <div className="grid gap-4 lg:grid-cols-2">
            {page.items.map((signal) => (
              <Card key={signal.signal_id} className="overflow-hidden">
                <CardHeader className="border-b border-app-border">
                  <div className="flex flex-wrap items-start justify-between gap-4">
                    <div className="min-w-0">
                      <CardTitle title={signal.strategy_name}>
                        {getStrategyDisplayName(signal.strategy_name, locale)}
                      </CardTitle>

                      <CardDescription
                        dir="ltr"
                        className="mt-2 truncate text-left text-xs font-semibold"
                      >
                        {signal.signal_id}
                      </CardDescription>
                    </div>

                    <Badge variant={directionVariant(signal.direction)}>
                      {copy.directions[signal.direction]}
                    </Badge>
                  </div>
                </CardHeader>

                <CardContent className="space-y-6 pt-6">
                  <div className="grid gap-3 sm:grid-cols-3">
                    <div className="rounded-xl border border-app-border bg-app-surface-muted p-4">
                      <p className="text-xs text-app-muted">{copy.fields.score}</p>
                      <p dir="ltr" className="mt-2 text-left text-xl font-bold text-app-foreground">
                        {formatDecimal(signal.score, locale)}
                      </p>
                    </div>

                    <div className="rounded-xl border border-app-border bg-app-surface-muted p-4">
                      <p className="text-xs text-app-muted">{copy.fields.pair}</p>
                      <p dir="ltr" className="mt-2 text-left font-semibold text-app-foreground">
                        {signal.pair.base_asset}/{signal.pair.quote_asset}
                      </p>
                    </div>

                    <div className="rounded-xl border border-app-border bg-app-surface-muted p-4">
                      <p className="text-xs text-app-muted">{copy.fields.timeframe}</p>
                      <p dir="ltr" className="mt-2 text-left font-semibold text-app-foreground">
                        {signal.timeframe}
                      </p>
                    </div>
                  </div>

                  <dl className="grid gap-4 text-sm sm:grid-cols-2">
                    <div>
                      <dt className="text-xs text-app-muted">{copy.fields.candleOpen}</dt>
                      <dd className="mt-1 text-app-foreground">
                        {formatDate(signal.candle_open_time, locale)}
                      </dd>
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

                    <div>
                      <dt className="text-xs text-app-muted">{copy.fields.strategy}</dt>
                      <dd dir="ltr" className="mt-1 text-left text-app-foreground">
                        {getStrategyDisplayName(signal.strategy_name, locale)} v
                        {signal.strategy_version}
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

                  <div className="border-t border-app-border pt-4">
                    <p className="text-xs text-app-muted">{copy.fields.dataset}</p>
                    <p
                      dir="ltr"
                      title={signal.dataset_id}
                      className="mt-2 truncate text-left text-xs font-semibold text-app-muted"
                    >
                      {signal.dataset_id}
                    </p>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </section>

      {experiments.length > 0 && !hasError && page.total > 0 ? (
        <section className="rounded-2xl border border-app-border bg-app-surface px-5 py-4">
          <Pagination
            total={page.total}
            limit={page.limit}
            offset={page.offset}
            isLoading={isLoading}
            pageLabel={copy.page}
            previousLabel={copy.previous}
            nextLabel={copy.next}
            onOffsetChange={(offset) => void loadSignals(offset)}
          />
        </section>
      ) : null}
    </div>
  );
}
