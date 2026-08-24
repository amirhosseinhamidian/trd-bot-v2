'use client';

import Link from 'next/link';
import { useRef, useState } from 'react';

import type { DashboardLocale } from '@/components/dashboard/dashboard-copy';
import WalkForwardFilterPanel, {
  DEFAULT_WALK_FORWARD_FILTERS,
  type WalkForwardFilterValues,
} from '@/components/dashboard/walk-forward-filter-panel';
import { getWalkForwardCopy } from '@/components/dashboard/walk-forward-copy';
import {
  Badge,
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  EmptyState,
  Pagination,
  Spinner,
} from '@/components/ui';
import { getWalkForwardRuns, type WalkForwardRunFilters } from '@/lib/api/client';
import type { Page, WalkForwardRunSummary } from '@/lib/api/types';

const PAGE_SIZE = 12;

type WalkForwardCatalogProps = {
  initialPage: Page<WalkForwardRunSummary>;
  locale: DashboardLocale;
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

export default function WalkForwardCatalog({ initialPage, locale }: WalkForwardCatalogProps) {
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
    <div className="space-y-8">
      <section>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-xs font-semibold tracking-[0.25em] text-cyan-400 uppercase">
              {copy.eyebrow}
            </p>

            <h1 className="mt-3 text-3xl font-bold tracking-tight text-white sm:text-4xl">
              {copy.title}
            </h1>
          </div>

          <div className="flex flex-wrap gap-2">
            <Badge variant="warning">{copy.historicalOnly}</Badge>

            <Badge variant="info">
              {copy.total}: {formatNumber(page.total, locale)}
            </Badge>
          </div>
        </div>

        <p className="mt-3 max-w-3xl text-sm leading-7 text-slate-400 sm:text-base">
          {copy.description}
        </p>
      </section>

      <WalkForwardFilterPanel locale={locale} isLoading={isLoading} onApply={applyFilters} />

      <section className="relative min-h-64">
        {isLoading ? (
          <div className="absolute inset-0 z-20 flex items-center justify-center rounded-2xl bg-slate-950/70 backdrop-blur-sm">
            <Spinner size="lg" label={copy.loading} className="text-cyan-400" />
          </div>
        ) : null}

        {hasError ? (
          <EmptyState
            title={copy.errorTitle}
            description={copy.errorDescription}
            className="border-red-400/20 bg-red-400/5"
            icon={<span className="font-bold text-red-300">!</span>}
            action={
              <Button size="sm" variant="danger" onClick={() => void loadRuns(page.offset)}>
                {copy.retry}
              </Button>
            }
          />
        ) : page.items.length === 0 ? (
          <EmptyState title={copy.emptyTitle} description={copy.emptyDescription} />
        ) : (
          <div className="grid gap-4 xl:grid-cols-2">
            {page.items.map((run) => (
              <Card key={run.execution_id} className="overflow-hidden">
                <CardHeader className="border-b border-slate-800">
                  <div className="flex flex-wrap items-start justify-between gap-4">
                    <div className="min-w-0">
                      <CardTitle>{run.strategy_name}</CardTitle>

                      <CardDescription
                        dir="ltr"
                        className="mt-2 truncate text-left font-mono text-xs"
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
                      <dt className="text-xs text-slate-500">{copy.fields.version}</dt>
                      <dd dir="ltr" className="mt-1 text-left text-slate-200">
                        {run.strategy_version}
                      </dd>
                    </div>

                    <div>
                      <dt className="text-xs text-slate-500">{copy.fields.horizon}</dt>
                      <dd className="mt-1 text-slate-200">
                        {formatNumber(run.horizon_candles, locale)}
                      </dd>
                    </div>

                    <div>
                      <dt className="text-xs text-slate-500">{copy.fields.totalFolds}</dt>
                      <dd className="mt-1 text-slate-200">
                        {formatNumber(run.total_folds, locale)}
                      </dd>
                    </div>

                    <div>
                      <dt className="text-xs text-slate-500">{copy.fields.totalSignals}</dt>
                      <dd className="mt-1 text-slate-200">
                        {formatNumber(run.total_signals, locale)}
                      </dd>
                    </div>
                  </dl>

                  <dl className="grid gap-3 sm:grid-cols-2">
                    <div className="rounded-xl border border-slate-800 bg-slate-950/50 p-3">
                      <dt className="text-xs text-slate-500">{copy.fields.strategyReturn}</dt>
                      <dd className="mt-2 font-mono text-sm text-slate-200">
                        {formatPercent(run.average_strategy_return, locale)}
                      </dd>
                    </div>

                    <div className="rounded-xl border border-slate-800 bg-slate-950/50 p-3">
                      <dt className="text-xs text-slate-500">{copy.fields.benchmarkReturn}</dt>
                      <dd className="mt-2 font-mono text-sm text-slate-200">
                        {formatPercent(run.average_benchmark_return, locale)}
                      </dd>
                    </div>

                    <div className="rounded-xl border border-slate-800 bg-slate-950/50 p-3">
                      <dt className="text-xs text-slate-500">{copy.fields.excessReturn}</dt>
                      <dd className="mt-2 font-mono text-sm text-cyan-200">
                        {formatPercent(run.average_excess_return, locale)}
                      </dd>
                    </div>

                    <div className="rounded-xl border border-slate-800 bg-slate-950/50 p-3">
                      <dt className="text-xs text-slate-500">{copy.fields.worstDrawdown}</dt>
                      <dd className="mt-2 font-mono text-sm text-slate-200">
                        {formatPercent(run.worst_max_drawdown_fraction, locale)}
                      </dd>
                    </div>
                  </dl>

                  <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
                    <div>
                      <dt className="text-xs text-slate-500">{copy.fields.strategyWins}</dt>
                      <dd className="mt-1 text-emerald-300">
                        {formatNumber(run.strategy_wins, locale)}
                      </dd>
                    </div>

                    <div>
                      <dt className="text-xs text-slate-500">{copy.fields.benchmarkWins}</dt>
                      <dd className="mt-1 text-amber-300">
                        {formatNumber(run.benchmark_wins, locale)}
                      </dd>
                    </div>

                    <div>
                      <dt className="text-xs text-slate-500">{copy.fields.ties}</dt>
                      <dd className="mt-1 text-slate-300">{formatNumber(run.ties, locale)}</dd>
                    </div>

                    <div>
                      <dt className="text-xs text-slate-500">{copy.fields.foldsWithTrades}</dt>
                      <dd className="mt-1 text-slate-300">
                        {formatNumber(run.folds_with_trades, locale)}
                      </dd>
                    </div>
                  </dl>

                  <div>
                    <p className="text-xs text-slate-500">{copy.fields.parameters}</p>

                    <div className="mt-2 flex flex-wrap gap-2">
                      {run.strategy_parameters.map((parameter) => (
                        <Badge key={parameter.name} variant="neutral">
                          {parameter.name}={parameter.value}
                        </Badge>
                      ))}
                    </div>
                  </div>

                  <div className="grid gap-3 border-t border-slate-800 pt-4 sm:grid-cols-2">
                    <div>
                      <p className="text-xs text-slate-500">{copy.fields.datasetId}</p>
                      <p
                        dir="ltr"
                        title={run.source_dataset_id}
                        className="mt-2 truncate text-left font-mono text-xs text-slate-400"
                      >
                        {run.source_dataset_id}
                      </p>
                    </div>

                    <div>
                      <p className="text-xs text-slate-500">{copy.fields.createdAt}</p>
                      <p className="mt-2 text-xs text-slate-400">
                        {formatDate(run.created_at, locale)}
                      </p>
                    </div>
                  </div>
                  <div className="flex border-t border-slate-800 pt-4">
                    <Link
                      href={`/${locale}/walk-forward/${encodeURIComponent(run.execution_id)}`}
                      className="inline-flex min-h-10 w-full items-center justify-center gap-2 rounded-xl border border-slate-700 bg-slate-900 px-4 py-2.5 text-sm font-semibold text-slate-200 transition hover:border-cyan-400/40 hover:bg-slate-800 hover:text-cyan-200 focus-visible:ring-2 focus-visible:ring-cyan-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950 focus-visible:outline-none"
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

      <section className="rounded-2xl border border-slate-800 bg-slate-900/40 px-5 py-4">
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
    </div>
  );
}
