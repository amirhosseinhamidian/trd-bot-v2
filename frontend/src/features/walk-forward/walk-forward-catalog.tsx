'use client';

import Link from 'next/link';
import { useRef, useState } from 'react';

import type { PlatformLocale } from '@/platform/i18n';
import { getWalkForwardRuns, type WalkForwardRunFilters } from '@/features/walk-forward/api/client';
import type { WalkForwardRunSummary } from '@/features/walk-forward/api/types';
import WalkForwardFilterPanel, {
  DEFAULT_WALK_FORWARD_FILTERS,
  type WalkForwardFilterValues,
} from '@/features/walk-forward/walk-forward-filter-panel';
import { getWalkForwardCopy } from '@/features/walk-forward/walk-forward-copy';
import WalkForwardRunForm from '@/features/walk-forward/walk-forward-run-form';
import {
  Badge,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  EmptyState,
  ErrorState,
  Pagination,
  Spinner,
} from '@/components/ui';
import type { Page } from '@/lib/api/types';
import { formatStrategyParameter, getStrategyDisplayName } from '@/lib/strategies/presentation';
import type { WalkForwardRunInitialValues } from '@/lib/walk-forward/run-params';
import { PageFrame } from '@/components/platform/page-frame';
import { PageHeader } from '@/components/platform/page-header';

const PAGE_SIZE = 12;

type WalkForwardCatalogProps = {
  initialPage: Page<WalkForwardRunSummary>;
  locale: PlatformLocale;
  initialRunValues?: WalkForwardRunInitialValues;
  initialExecutionId?: string;
};

function formatNumber(value: number, locale: PlatformLocale): string {
  return new Intl.NumberFormat(locale === 'fa' ? 'fa-IR' : 'en-US').format(value);
}

function formatPercent(value: string, locale: PlatformLocale): string {
  const parsedValue = Number(value);

  if (!Number.isFinite(parsedValue)) {
    return value;
  }

  return new Intl.NumberFormat(locale === 'fa' ? 'fa-IR' : 'en-US', {
    style: 'percent',
    maximumFractionDigits: 2,
  }).format(parsedValue);
}

function formatDate(value: string, locale: PlatformLocale): string {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat(locale === 'fa' ? 'fa-IR' : 'en-US', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date);
}

function toCreatedAtFrom(value: string): string | undefined {
  return value ? `${value}T00:00:00.000Z` : undefined;
}

function toCreatedAtTo(value: string): string | undefined {
  return value ? `${value}T23:59:59.999Z` : undefined;
}

function buildWalkForwardFilters(filters: WalkForwardFilterValues): WalkForwardRunFilters {
  const parsedHorizon = Number(filters.horizonCandles);

  return {
    sourceDatasetId: filters.sourceDatasetId.trim() || undefined,
    planId: filters.planId.trim() || undefined,
    strategyName: filters.strategyName.trim() || undefined,
    strategyVersion: filters.strategyVersion.trim() || undefined,
    horizonCandles:
      filters.horizonCandles && Number.isInteger(parsedHorizon) && parsedHorizon > 0
        ? parsedHorizon
        : undefined,
    createdAtFrom: toCreatedAtFrom(filters.createdAtFrom),
    createdAtTo: toCreatedAtTo(filters.createdAtTo),
    sortBy: filters.sortBy,
    sortDirection: filters.sortDirection,
  };
}

export default function WalkForwardCatalog({
  initialPage,
  locale,
  initialRunValues,
  initialExecutionId,
}: WalkForwardCatalogProps) {
  const copy = getWalkForwardCopy(locale);

  const [page, setPage] = useState(initialPage);
  const [isLoading, setIsLoading] = useState(false);
  const [hasError, setHasError] = useState(false);
  const [appliedFilters, setAppliedFilters] = useState<WalkForwardFilterValues>(
    DEFAULT_WALK_FORWARD_FILTERS,
  );

  const requestSequence = useRef(0);

  async function loadRuns(
    offset: number,
    filters: WalkForwardFilterValues = appliedFilters,
  ): Promise<void> {
    const requestId = ++requestSequence.current;

    setIsLoading(true);
    setHasError(false);

    try {
      const result = await getWalkForwardRuns({
        ...buildWalkForwardFilters(filters),
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

  function applyFilters(filters: WalkForwardFilterValues): void {
    setAppliedFilters(filters);
    void loadRuns(0, filters);
  }

  return (
    <PageFrame>
      <PageHeader
        eyebrow={copy.eyebrow}
        title={copy.title}
        description={copy.description}
        actions={
          <>
            <Badge variant="warning">{copy.historicalOnly}</Badge>
            <Badge variant="info">
              {copy.total}: {formatNumber(page.total, locale)}
            </Badge>
          </>
        }
      />

      <WalkForwardRunForm
        locale={locale}
        initialValues={initialRunValues}
        initialExecutionId={initialExecutionId}
      />

      <WalkForwardFilterPanel locale={locale} isLoading={isLoading} onApply={applyFilters} />

      <section className="relative min-h-64" aria-busy={isLoading}>
        {isLoading ? (
          <div className="absolute inset-0 z-20 flex items-center justify-center rounded-2xl bg-app-overlay backdrop-blur-sm">
            <Spinner size="lg" label={copy.loading} className="text-app-accent" />
          </div>
        ) : null}

        {hasError ? (
          <ErrorState
            title={copy.errorTitle}
            description={copy.errorDescription}
            retryLabel={copy.retry}
            onRetry={() => void loadRuns(page.offset)}
          />
        ) : page.items.length === 0 ? (
          <EmptyState title={copy.emptyTitle} description={copy.emptyDescription} />
        ) : (
          <div className="grid gap-4 xl:grid-cols-2">
            {page.items.map((run) => (
              <Card key={run.execution_id} className="overflow-hidden">
                <CardHeader className="border-b border-app-border">
                  <div className="flex flex-wrap items-start justify-between gap-4">
                    <div className="min-w-0">
                      <CardTitle title={run.strategy_name}>
                        {getStrategyDisplayName(run.strategy_name, locale)}
                      </CardTitle>

                      <CardDescription
                        dir="ltr"
                        className="mt-2 truncate text-left text-xs font-semibold"
                      >
                        {run.execution_id}
                      </CardDescription>
                    </div>

                    <Badge variant="info">{copy.modes[run.walk_forward_config.mode]}</Badge>
                  </div>
                </CardHeader>

                <CardContent className="space-y-6 pt-6">
                  <dl className="grid grid-cols-2 gap-4 text-sm sm:grid-cols-4">
                    <div>
                      <dt className="text-xs text-app-muted">{copy.fields.version}</dt>
                      <dd dir="ltr" className="mt-1 text-left text-app-foreground">
                        {run.strategy_version}
                      </dd>
                    </div>

                    <div>
                      <dt className="text-xs text-app-muted">{copy.fields.horizon}</dt>
                      <dd className="mt-1 text-app-foreground">
                        {formatNumber(run.horizon_candles, locale)}
                      </dd>
                    </div>

                    <div>
                      <dt className="text-xs text-app-muted">{copy.fields.totalFolds}</dt>
                      <dd className="mt-1 text-app-foreground">
                        {formatNumber(run.total_folds, locale)}
                      </dd>
                    </div>

                    <div>
                      <dt className="text-xs text-app-muted">{copy.fields.totalSignals}</dt>
                      <dd className="mt-1 text-app-foreground">
                        {formatNumber(run.total_signals, locale)}
                      </dd>
                    </div>
                  </dl>

                  <dl className="grid gap-3 sm:grid-cols-2">
                    <div className="rounded-xl border border-app-border bg-app-surface-muted p-3">
                      <dt className="text-xs text-app-muted">{copy.fields.strategyReturn}</dt>
                      <dd className="mt-2 text-sm font-semibold text-app-foreground">
                        {formatPercent(run.average_strategy_return, locale)}
                      </dd>
                    </div>

                    <div className="rounded-xl border border-app-border bg-app-surface-muted p-3">
                      <dt className="text-xs text-app-muted">{copy.fields.benchmarkReturn}</dt>
                      <dd className="mt-2 text-sm font-semibold text-app-foreground">
                        {formatPercent(run.average_benchmark_return, locale)}
                      </dd>
                    </div>

                    <div className="rounded-xl border border-app-border bg-app-surface-muted p-3">
                      <dt className="text-xs text-app-muted">{copy.fields.excessReturn}</dt>
                      <dd className="mt-2 text-sm font-semibold text-app-accent">
                        {formatPercent(run.average_excess_return, locale)}
                      </dd>
                    </div>

                    <div className="rounded-xl border border-app-border bg-app-surface-muted p-3">
                      <dt className="text-xs text-app-muted">{copy.fields.worstDrawdown}</dt>
                      <dd className="mt-2 text-sm font-semibold text-app-foreground">
                        {formatPercent(run.worst_max_drawdown_fraction, locale)}
                      </dd>
                    </div>
                  </dl>

                  <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
                    <div>
                      <dt className="text-xs text-app-muted">{copy.fields.strategyWins}</dt>
                      <dd className="mt-1 text-app-success">
                        {formatNumber(run.strategy_wins, locale)}
                      </dd>
                    </div>

                    <div>
                      <dt className="text-xs text-app-muted">{copy.fields.benchmarkWins}</dt>
                      <dd className="mt-1 text-app-warning">
                        {formatNumber(run.benchmark_wins, locale)}
                      </dd>
                    </div>

                    <div>
                      <dt className="text-xs text-app-muted">{copy.fields.ties}</dt>
                      <dd className="mt-1 text-app-foreground">{formatNumber(run.ties, locale)}</dd>
                    </div>

                    <div>
                      <dt className="text-xs text-app-muted">{copy.fields.foldsWithTrades}</dt>
                      <dd className="mt-1 text-app-foreground">
                        {formatNumber(run.folds_with_trades, locale)}
                      </dd>
                    </div>
                  </dl>

                  <div>
                    <p className="text-xs text-app-muted">{copy.fields.parameters}</p>

                    <div className="mt-2 flex flex-wrap gap-2">
                      {run.strategy_parameters.map((parameter) => (
                        <Badge key={parameter.name} variant="neutral">
                          {formatStrategyParameter(parameter, locale)}
                        </Badge>
                      ))}
                    </div>
                  </div>

                  <div className="grid gap-3 border-t border-app-border pt-4 sm:grid-cols-2">
                    <div>
                      <p className="text-xs text-app-muted">{copy.fields.datasetId}</p>
                      <p
                        dir="ltr"
                        title={run.source_dataset_id}
                        className="mt-2 truncate text-left text-xs font-semibold text-app-muted"
                      >
                        {run.source_dataset_id}
                      </p>
                    </div>

                    <div>
                      <p className="text-xs text-app-muted">{copy.fields.createdAt}</p>
                      <p className="mt-2 text-xs text-app-muted">
                        {formatDate(run.created_at, locale)}
                      </p>
                    </div>
                  </div>
                  <div className="flex border-t border-app-border pt-4">
                    <Link
                      href={`/${locale}/walk-forward/${encodeURIComponent(run.execution_id)}`}
                      className="inline-flex min-h-10 w-full items-center justify-center gap-2 rounded-xl border border-app-border bg-app-surface px-4 py-2.5 text-sm font-semibold text-app-foreground transition hover:border-app-accent-border hover:bg-app-hover hover:text-app-accent focus-visible:ring-2 focus-visible:ring-app-accent focus-visible:ring-offset-2 focus-visible:ring-offset-app-background focus-visible:outline-none"
                    >
                      <span>{copy.viewDetails}</span>

                      <span aria-hidden="true">{locale === 'fa' ? '←' : '→'}</span>
                    </Link>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </section>

      {!hasError && page.total > 0 ? (
        <section className="rounded-2xl border border-app-border bg-app-surface px-5 py-4">
          <Pagination
            total={page.total}
            limit={page.limit}
            offset={page.offset}
            isLoading={isLoading}
            pageLabel={copy.page}
            previousLabel={copy.previous}
            nextLabel={copy.next}
            onOffsetChange={(offset) => void loadRuns(offset)}
          />
        </section>
      ) : null}
    </PageFrame>
  );
}
