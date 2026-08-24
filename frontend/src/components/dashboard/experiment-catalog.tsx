'use client';

import Link from 'next/link';
import { useRef, useState } from 'react';

import type { DashboardLocale } from '@/components/dashboard/dashboard-copy';
import ExperimentFilterPanel, {
  DEFAULT_EXPERIMENT_FILTERS,
  type ExperimentFilterValues,
} from '@/components/dashboard/experiment-filter-panel';
import { getExperimentsCopy } from '@/components/dashboard/experiments-copy';
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
  Checkbox,
} from '@/components/ui';
import { getExperiments, type ExperimentFilters } from '@/lib/api/client';
import type { ExperimentSummary, Page } from '@/lib/api/types';
import ExperimentComparisonPanel from '@/components/dashboard/experiment-comparison-panel';
import { getExperimentComparisonCopy } from '@/components/dashboard/experiment-comparison-copy';

const PAGE_SIZE = 12;

type ExperimentCatalogProps = {
  initialPage: Page<ExperimentSummary>;
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

function formatNumber(value: number, locale: DashboardLocale): string {
  return new Intl.NumberFormat(locale === 'fa' ? 'fa-IR' : 'en-US').format(value);
}

function formatPercent(value: string | null, locale: DashboardLocale): string {
  if (value === null) {
    return '—';
  }

  const numericValue = Number(value);

  if (!Number.isFinite(numericValue)) {
    return value;
  }

  return new Intl.NumberFormat(locale === 'fa' ? 'fa-IR' : 'en-US', {
    style: 'percent',
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  }).format(numericValue);
}

function formatDecimal(value: string | null, locale: DashboardLocale): string {
  if (value === null) {
    return '—';
  }

  const numericValue = Number(value);

  if (!Number.isFinite(numericValue)) {
    return value;
  }

  return new Intl.NumberFormat(locale === 'fa' ? 'fa-IR' : 'en-US', {
    maximumFractionDigits: 4,
  }).format(numericValue);
}

function toCreatedAtFrom(value: string): string | undefined {
  return value ? `${value}T00:00:00.000Z` : undefined;
}

function toCreatedAtTo(value: string): string | undefined {
  return value ? `${value}T23:59:59.999Z` : undefined;
}

function buildExperimentFilters(filters: ExperimentFilterValues): ExperimentFilters {
  const parsedHorizon = Number(filters.horizonCandles);

  return {
    datasetId: filters.datasetId.trim() || undefined,
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

export default function ExperimentCatalog({ initialPage, locale }: ExperimentCatalogProps) {
  const copy = getExperimentsCopy(locale);

  const [page, setPage] = useState(initialPage);
  const [appliedFilters, setAppliedFilters] = useState<ExperimentFilterValues>(
    DEFAULT_EXPERIMENT_FILTERS,
  );
  const [isLoading, setIsLoading] = useState(false);
  const [hasError, setHasError] = useState(false);
  const [selectedExperiments, setSelectedExperiments] = useState<ExperimentSummary[]>([]);

  const requestSequence = useRef(0);

  const comparisonCopy = getExperimentComparisonCopy(locale);

  function isExperimentSelected(experimentId: string): boolean {
    return selectedExperiments.some((experiment) => experiment.experiment_id === experimentId);
  }

  function isExperimentCompatible(experiment: ExperimentSummary): boolean {
    if (selectedExperiments.length === 0) {
      return true;
    }

    const reference = selectedExperiments[0];

    return (
      experiment.dataset_id === reference.dataset_id &&
      experiment.horizon_candles === reference.horizon_candles
    );
  }

  function toggleExperiment(experiment: ExperimentSummary): void {
    const isSelected = isExperimentSelected(experiment.experiment_id);

    if (isSelected) {
      setSelectedExperiments((current) =>
        current.filter((item) => item.experiment_id !== experiment.experiment_id),
      );

      return;
    }

    if (selectedExperiments.length >= 10 || !isExperimentCompatible(experiment)) {
      return;
    }

    setSelectedExperiments((current) => [...current, experiment]);
  }

  async function loadExperiments(
    offset: number,
    filters: ExperimentFilterValues = appliedFilters,
  ): Promise<void> {
    const requestId = ++requestSequence.current;

    setIsLoading(true);
    setHasError(false);

    try {
      const result = await getExperiments({
        ...buildExperimentFilters(filters),
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

  function applyFilters(filters: ExperimentFilterValues): void {
    setAppliedFilters(filters);
    void loadExperiments(0, filters);
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

      <ExperimentFilterPanel locale={locale} isLoading={isLoading} onApply={applyFilters} />
      <ExperimentComparisonPanel
        key={
          selectedExperiments
            .map((experiment) => experiment.experiment_id)
            .sort()
            .join(':') || 'empty-selection'
        }
        locale={locale}
        selectedExperiments={selectedExperiments}
        onClearSelection={() => setSelectedExperiments([])}
      />
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
              <Button size="sm" variant="danger" onClick={() => void loadExperiments(page.offset)}>
                {copy.retry}
              </Button>
            }
          />
        ) : page.items.length === 0 ? (
          <EmptyState title={copy.emptyTitle} description={copy.emptyDescription} />
        ) : (
          <div className="grid gap-4 lg:grid-cols-2">
            {page.items.map((experiment) => {
              const outcomeVariant =
                experiment.comparison_outcome === 'strategy'
                  ? 'success'
                  : experiment.comparison_outcome === 'benchmark'
                    ? 'warning'
                    : 'neutral';

              const isSelected = isExperimentSelected(experiment.experiment_id);

              const isCompatible = isSelected || isExperimentCompatible(experiment);

              const hasReachedLimit = !isSelected && selectedExperiments.length >= 10;

              const metrics = [
                {
                  label: copy.fields.totalReturn,
                  value: formatPercent(experiment.total_return, locale),
                },
                {
                  label: copy.fields.benchmarkReturn,
                  value: formatPercent(experiment.benchmark_return, locale),
                },
                {
                  label: copy.fields.excessReturn,
                  value: formatPercent(experiment.excess_return, locale),
                },
                {
                  label: copy.fields.winRate,
                  value: formatPercent(experiment.win_rate, locale),
                },
                {
                  label: copy.fields.maxDrawdown,
                  value: formatPercent(experiment.max_drawdown_fraction, locale),
                },
                {
                  label: copy.fields.profitFactor,
                  value: formatDecimal(experiment.profit_factor, locale),
                },
              ];

              return (
                <Card
                  key={experiment.experiment_id}
                  className={[
                    'overflow-hidden',
                    isSelected ? 'border-cyan-400/40 bg-cyan-400/5' : '',
                    !isCompatible || hasReachedLimit ? 'opacity-60' : '',
                  ].join(' ')}
                >
                  <CardHeader className="border-b border-slate-800">
                    <div className="flex flex-wrap items-start justify-between gap-4">
                      <div className="min-w-0">
                        <CardTitle>{experiment.strategy_name}</CardTitle>

                        <CardDescription
                          dir="ltr"
                          className="mt-2 truncate text-left font-mono text-xs"
                        >
                          {experiment.experiment_id}
                        </CardDescription>
                      </div>

                      <div className="flex flex-col items-end gap-3">
                        <Badge variant={outcomeVariant}>
                          {copy.outcomes[experiment.comparison_outcome]}
                        </Badge>

                        <Checkbox
                          label={comparisonCopy.selectExperiment}
                          checked={isSelected}
                          disabled={!isCompatible || hasReachedLimit}
                          description={
                            !isCompatible
                              ? comparisonCopy.incompatibleExperiment
                              : hasReachedLimit
                                ? comparisonCopy.limitReached
                                : undefined
                          }
                          onChange={() => toggleExperiment(experiment)}
                        />
                      </div>
                    </div>
                  </CardHeader>

                  <CardContent className="space-y-6 pt-6">
                    <dl className="grid grid-cols-2 gap-4 text-sm">
                      <div>
                        <dt className="text-xs text-slate-500">{copy.fields.strategyVersion}</dt>
                        <dd dir="ltr" className="mt-1 text-left text-slate-200">
                          {experiment.strategy_version}
                        </dd>
                      </div>

                      <div>
                        <dt className="text-xs text-slate-500">{copy.fields.horizonCandles}</dt>
                        <dd className="mt-1 text-slate-200">
                          {formatNumber(experiment.horizon_candles, locale)}
                        </dd>
                      </div>

                      <div>
                        <dt className="text-xs text-slate-500">{copy.fields.generatedSignals}</dt>
                        <dd className="mt-1 text-slate-200">
                          {formatNumber(experiment.generated_signals, locale)}
                        </dd>
                      </div>

                      <div>
                        <dt className="text-xs text-slate-500">{copy.fields.totalTrades}</dt>
                        <dd className="mt-1 text-slate-200">
                          {formatNumber(experiment.total_trades, locale)}
                        </dd>
                      </div>
                    </dl>

                    <div className="grid gap-3 sm:grid-cols-2">
                      {metrics.map((metric) => (
                        <div
                          key={metric.label}
                          className="rounded-xl border border-slate-800 bg-slate-950/50 p-3"
                        >
                          <p className="text-xs text-slate-500">{metric.label}</p>
                          <p dir="ltr" className="mt-2 text-left font-mono text-sm text-slate-200">
                            {metric.value}
                          </p>
                        </div>
                      ))}
                    </div>

                    <div>
                      <p className="text-xs text-slate-500">{copy.fields.parameters}</p>

                      <div className="mt-2 flex flex-wrap gap-2">
                        {experiment.parameters.map((parameter) => (
                          <Badge key={parameter.name} variant="neutral">
                            {parameter.name}={parameter.value}
                          </Badge>
                        ))}
                      </div>
                    </div>

                    <div className="border-t border-slate-800 pt-4">
                      <p className="text-xs text-slate-500">{copy.fields.datasetId}</p>
                      <p
                        dir="ltr"
                        title={experiment.dataset_id}
                        className="mt-2 truncate text-left font-mono text-xs text-slate-400"
                      >
                        {experiment.dataset_id}
                      </p>

                      <p className="mt-4 text-xs text-slate-500">
                        {copy.fields.createdAt}: {formatDate(experiment.created_at, locale)}
                      </p>
                    </div>
                    <div className="flex border-t border-slate-800 pt-4">
                      <Link
                        href={`/${locale}/experiments/${encodeURIComponent(
                          experiment.experiment_id,
                        )}`}
                        className="inline-flex min-h-10 w-full items-center justify-center gap-2 rounded-xl border border-slate-700 bg-slate-900 px-4 py-2.5 text-sm font-semibold text-slate-200 transition hover:border-cyan-400/40 hover:bg-slate-800 hover:text-cyan-200 focus-visible:ring-2 focus-visible:ring-cyan-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950 focus-visible:outline-none"
                      >
                        <span>{copy.viewDetails}</span>
                        <span aria-hidden="true">{locale === 'fa' ? '←' : '→'}</span>
                      </Link>
                    </div>
                  </CardContent>
                </Card>
              );
            })}
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
          onOffsetChange={(offset) => void loadExperiments(offset)}
        />
      </section>
    </div>
  );
}
