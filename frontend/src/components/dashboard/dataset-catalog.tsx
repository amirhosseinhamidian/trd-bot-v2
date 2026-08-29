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
import DatasetImportForm from './dataset-import-form';

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
  const [filterResetVersion, setFilterResetVersion] = useState(0);

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

  async function handleDatasetImported(): Promise<void> {
    setAppliedFilters(DEFAULT_DATASET_FILTERS);
    setFilterResetVersion((currentVersion) => currentVersion + 1);

    await loadDatasets(0, DEFAULT_DATASET_FILTERS);
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

          <Badge variant="info">
            {copy.total}: {formatNumber(page.total, locale)}
          </Badge>
        </div>

        <p className="mt-3 max-w-3xl text-sm leading-7 text-app-muted sm:text-base">
          {copy.description}
        </p>
      </section>
      <DatasetImportForm locale={locale} onImported={handleDatasetImported} />
      <DatasetFilterPanel
        key={filterResetVersion}
        locale={locale}
        isLoading={isLoading}
        onApply={applyFilters}
      />

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
            onRetry={() => void loadDatasets(page.offset)}
          />
        ) : page.items.length === 0 ? (
          <EmptyState title={copy.emptyTitle} description={copy.emptyDescription} />
        ) : (
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {page.items.map((dataset) => (
              <Card key={dataset.dataset_id} className="overflow-hidden">
                <CardHeader className="border-b border-app-border">
                  <div className="flex items-start justify-between gap-4">
                    <div className="min-w-0">
                      <CardTitle className="truncate">{dataset.name}</CardTitle>

                      <CardDescription
                        dir="ltr"
                        className="mt-2 truncate text-left text-xs font-semibold"
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
                      <dt className="text-app-muted">{copy.fields.pair}</dt>
                      <dd dir="ltr" className="font-medium text-app-foreground">
                        {dataset.pair.base_asset}/{dataset.pair.quote_asset}
                      </dd>
                    </div>

                    <div className="flex items-center justify-between gap-4">
                      <dt className="text-app-muted">{copy.fields.marketType}</dt>
                      <dd className="text-app-foreground">{dataset.pair.market_type}</dd>
                    </div>

                    <div className="flex items-center justify-between gap-4">
                      <dt className="text-app-muted">{copy.fields.candles}</dt>
                      <dd className="text-app-foreground">
                        {formatNumber(dataset.candle_count, locale)}
                      </dd>
                    </div>

                    <div className="flex items-center justify-between gap-4">
                      <dt className="text-app-muted">{copy.fields.source}</dt>
                      <dd className="truncate text-app-foreground">{dataset.source}</dd>
                    </div>

                    <div className="border-t border-app-border pt-4">
                      <dt className="text-xs text-app-muted">{copy.fields.period}</dt>
                      <dd className="mt-2 text-xs leading-6 text-app-foreground">
                        <span>{formatShortDate(dataset.start_time, locale)}</span>
                        <span className="mx-2 text-app-subtle">—</span>
                        <span>{formatShortDate(dataset.end_time, locale)}</span>
                      </dd>
                    </div>

                    <div>
                      <dt className="text-xs text-app-muted">{copy.fields.createdAt}</dt>
                      <dd className="mt-2 text-xs text-app-muted">
                        {formatDate(dataset.created_at, locale)}
                      </dd>
                    </div>

                    <div>
                      <dt className="text-xs text-app-muted">{copy.fields.checksum}</dt>
                      <dd
                        dir="ltr"
                        title={dataset.checksum}
                        className="mt-2 truncate text-left text-xs font-semibold text-app-subtle"
                      >
                        {dataset.checksum}
                      </dd>
                    </div>
                  </dl>
                </CardContent>
                <CardFooter>
                  <Link
                    href={`/${locale}/datasets/${encodeURIComponent(dataset.dataset_id)}`}
                    className="inline-flex min-h-10 w-full items-center justify-center rounded-xl border border-app-border bg-app-surface px-4 py-2.5 text-sm font-semibold text-app-foreground transition hover:border-app-accent-border hover:text-app-accent"
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
        <section className="rounded-2xl border border-app-border bg-app-surface px-5 py-4">
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
