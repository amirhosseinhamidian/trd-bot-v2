'use client';

import { useRef, useState } from 'react';

import type { DashboardLocale } from '@/components/dashboard/dashboard-copy';
import { getDatasetsCopy } from '@/components/dashboard/datasets-copy';
import {
  Badge,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  CardFooter,
  EmptyState,
  Pagination,
  Spinner,
  ErrorState,
} from '@/components/ui';
import { getDatasets, type DatasetFilters } from '@/lib/api/client';
import type { DatasetSummary, Page } from '@/lib/api/types';
import DatasetFilterPanel, {
  DEFAULT_DATASET_FILTERS,
  type DatasetFilterValues,
} from '@/components/dashboard/dataset-filter-panel';
import Link from 'next/link';

const PAGE_SIZE = 12;

type DatasetCatalogProps = {
  initialPage: Page<DatasetSummary>;
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

function formatShortDate(value: string, locale: DashboardLocale): string {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat(locale === 'fa' ? 'fa-IR' : 'en-US', {
    dateStyle: 'medium',
  }).format(date);
}

function formatNumber(value: number, locale: DashboardLocale): string {
  return new Intl.NumberFormat(locale === 'fa' ? 'fa-IR' : 'en-US').format(value);
}

function toCreatedAtFrom(value: string): string | undefined {
  return value ? `${value}T00:00:00.000Z` : undefined;
}

function toCreatedAtTo(value: string): string | undefined {
  return value ? `${value}T23:59:59.999Z` : undefined;
}

function buildDatasetFilters(filters: DatasetFilterValues): DatasetFilters {
  return {
    source: filters.source.trim() || undefined,
    baseAsset: filters.baseAsset.trim() || undefined,
    quoteAsset: filters.quoteAsset.trim() || undefined,
    timeframe: filters.timeframe === 'all' ? undefined : filters.timeframe,
    createdAtFrom: toCreatedAtFrom(filters.createdAtFrom),
    createdAtTo: toCreatedAtTo(filters.createdAtTo),
    sortBy: filters.sortBy,
    sortDirection: filters.sortDirection,
  };
}

export default function DatasetCatalog({ initialPage, locale }: DatasetCatalogProps) {
  const copy = getDatasetsCopy(locale);

  const [page, setPage] = useState(initialPage);
  const [isLoading, setIsLoading] = useState(false);
  const [hasError, setHasError] = useState(false);
  const [appliedFilters, setAppliedFilters] =
    useState<DatasetFilterValues>(DEFAULT_DATASET_FILTERS);

  const requestSequence = useRef(0);

  async function loadDatasets(
    offset: number,
    filters: DatasetFilterValues = appliedFilters,
  ): Promise<void> {
    const requestId = ++requestSequence.current;

    setIsLoading(true);
    setHasError(false);

    try {
      const result = await getDatasets({
        ...buildDatasetFilters(filters),
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

  function applyFilters(filters: DatasetFilterValues): void {
    setAppliedFilters(filters);
    void loadDatasets(0, filters);
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

          <Badge variant="info">
            {copy.total}: {formatNumber(page.total, locale)}
          </Badge>
        </div>

        <p className="mt-3 max-w-3xl text-sm leading-7 text-slate-400 sm:text-base">
          {copy.description}
        </p>
      </section>

      <DatasetFilterPanel locale={locale} isLoading={isLoading} onApply={applyFilters} />

      <section className="relative min-h-64" aria-busy={isLoading}>
        {isLoading ? (
          <div className="absolute inset-0 z-20 flex items-center justify-center rounded-2xl bg-slate-950/70 backdrop-blur-sm">
            <Spinner size="lg" label={copy.loading} className="text-cyan-400" />
          </div>
        ) : null}

        {hasError ? (
          <ErrorState
            title={copy.errorTitle}
            description={copy.errorDescription}
            retryLabel={copy.retry}
            onRetry={() => void loadDatasets(page.offset)}
          />
        ) : page.items.length === 0 ? (
          <EmptyState title={copy.emptyTitle} description={copy.emptyDescription} />
        ) : (
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {page.items.map((dataset) => (
              <Card key={dataset.dataset_id} className="overflow-hidden">
                <CardHeader className="border-b border-slate-800">
                  <div className="flex items-start justify-between gap-4">
                    <div className="min-w-0">
                      <CardTitle className="truncate">{dataset.name}</CardTitle>

                      <CardDescription
                        dir="ltr"
                        className="mt-2 truncate text-left font-mono text-xs"
                      >
                        {dataset.dataset_id}
                      </CardDescription>
                    </div>

                    <Badge variant="neutral">{dataset.timeframe}</Badge>
                  </div>
                </CardHeader>

                <CardContent className="pt-6">
                  <dl className="space-y-4 text-sm">
                    <div className="flex items-center justify-between gap-4">
                      <dt className="text-slate-500">{copy.fields.pair}</dt>
                      <dd dir="ltr" className="font-medium text-slate-200">
                        {dataset.pair.base_asset}/{dataset.pair.quote_asset}
                      </dd>
                    </div>

                    <div className="flex items-center justify-between gap-4">
                      <dt className="text-slate-500">{copy.fields.marketType}</dt>
                      <dd className="text-slate-300">{dataset.pair.market_type}</dd>
                    </div>

                    <div className="flex items-center justify-between gap-4">
                      <dt className="text-slate-500">{copy.fields.candles}</dt>
                      <dd className="text-slate-300">
                        {formatNumber(dataset.candle_count, locale)}
                      </dd>
                    </div>

                    <div className="flex items-center justify-between gap-4">
                      <dt className="text-slate-500">{copy.fields.source}</dt>
                      <dd className="truncate text-slate-300">{dataset.source}</dd>
                    </div>

                    <div className="border-t border-slate-800 pt-4">
                      <dt className="text-xs text-slate-500">{copy.fields.period}</dt>
                      <dd className="mt-2 text-xs leading-6 text-slate-300">
                        <span>{formatShortDate(dataset.start_time, locale)}</span>
                        <span className="mx-2 text-slate-700">—</span>
                        <span>{formatShortDate(dataset.end_time, locale)}</span>
                      </dd>
                    </div>

                    <div>
                      <dt className="text-xs text-slate-500">{copy.fields.createdAt}</dt>
                      <dd className="mt-2 text-xs text-slate-400">
                        {formatDate(dataset.created_at, locale)}
                      </dd>
                    </div>

                    <div>
                      <dt className="text-xs text-slate-500">{copy.fields.checksum}</dt>
                      <dd
                        dir="ltr"
                        title={dataset.checksum}
                        className="mt-2 truncate text-left font-mono text-xs text-slate-600"
                      >
                        {dataset.checksum}
                      </dd>
                    </div>
                  </dl>
                </CardContent>
                <CardFooter>
                  <Link
                    href={`/${locale}/datasets/${encodeURIComponent(dataset.dataset_id)}`}
                    className="inline-flex min-h-10 w-full items-center justify-center rounded-xl border border-slate-700 bg-slate-900 px-4 py-2.5 text-sm font-semibold text-slate-200 transition hover:border-cyan-400/40 hover:text-cyan-300"
                  >
                    {copy.viewDetails}
                  </Link>
                </CardFooter>
              </Card>
            ))}
          </div>
        )}
      </section>

      {!hasError && page.total > 0 ? (
        <section className="rounded-2xl border border-slate-800 bg-slate-900/40 px-5 py-4">
          <Pagination
            total={page.total}
            limit={page.limit}
            offset={page.offset}
            isLoading={isLoading}
            pageLabel={copy.page}
            previousLabel={copy.previous}
            nextLabel={copy.next}
            onOffsetChange={(offset) => void loadDatasets(offset)}
          />
        </section>
      ) : null}
    </div>
  );
}
