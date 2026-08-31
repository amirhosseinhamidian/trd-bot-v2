'use client';

import Link from 'next/link';
import { useCallback, useEffect, useRef, useState } from 'react';

import type { DashboardLocale } from '@/components/dashboard/dashboard-copy';
import { getImportHistoryCopy } from '@/components/dashboard/import-history-copy';
import { Badge, Button, EmptyState, ErrorState, Pagination, Spinner } from '@/components/ui';
import { getMarketDataImportHistory } from '@/lib/api/client';
import type { MarketDataImportRecord, MarketDataImportStatus, Page } from '@/lib/api/types';

const PAGE_SIZE = 5;
type StatusFilter = 'all' | MarketDataImportStatus;

type MarketDataImportHistoryProps = {
  connectionId: string;
  locale: DashboardLocale;
  refreshVersion?: number;
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

export default function MarketDataImportHistory({
  connectionId,
  locale,
  refreshVersion = 0,
}: MarketDataImportHistoryProps) {
  const copy = getImportHistoryCopy(locale);
  const [isOpen, setIsOpen] = useState(false);
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all');
  const [page, setPage] = useState<Page<MarketDataImportRecord> | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [hasError, setHasError] = useState(false);
  const lastRefreshVersion = useRef(refreshVersion);

  const loadHistory = useCallback(
    async (offset: number, status: StatusFilter): Promise<void> => {
      setIsLoading(true);
      setHasError(false);

      try {
        setPage(
          await getMarketDataImportHistory(connectionId, {
            status: status === 'all' ? undefined : status,
            limit: PAGE_SIZE,
            offset,
          }),
        );
      } catch {
        setHasError(true);
      } finally {
        setIsLoading(false);
      }
    },
    [connectionId],
  );

  function handleToggle(): void {
    const nextIsOpen = !isOpen;
    setIsOpen(nextIsOpen);

    if (nextIsOpen) {
      void loadHistory(0, statusFilter);
    }
  }

  function handleStatusChange(status: StatusFilter): void {
    setStatusFilter(status);
    void loadHistory(0, status);
  }

  useEffect(() => {
    if (refreshVersion === lastRefreshVersion.current) {
      return;
    }

    lastRefreshVersion.current = refreshVersion;

    if (!isOpen) {
      return;
    }

    let isCurrent = true;

    async function refreshHistory(): Promise<void> {
      try {
        const refreshedPage = await getMarketDataImportHistory(connectionId, {
          status: statusFilter === 'all' ? undefined : statusFilter,
          limit: PAGE_SIZE,
          offset: 0,
        });

        if (isCurrent) {
          setPage(refreshedPage);
          setHasError(false);
        }
      } catch {
        if (isCurrent) {
          setHasError(true);
        }
      }
    }

    void refreshHistory();

    return () => {
      isCurrent = false;
    };
  }, [connectionId, isOpen, refreshVersion, statusFilter]);

  return (
    <section className="mt-6 border-t border-app-border pt-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-base font-semibold text-app-foreground">{copy.title}</h3>
          <p className="mt-1 text-sm leading-6 text-app-muted">{copy.description}</p>
        </div>
        <Button variant="secondary" size="sm" aria-expanded={isOpen} onClick={handleToggle}>
          {isOpen ? copy.hide : copy.show}
        </Button>
      </div>

      {isOpen ? (
        <div className="mt-5" aria-busy={isLoading}>
          <div className="mb-4 flex flex-wrap gap-2" aria-label={copy.title}>
            <Button
              size="sm"
              variant={statusFilter === 'all' ? 'primary' : 'secondary'}
              aria-pressed={statusFilter === 'all'}
              onClick={() => handleStatusChange('all')}
            >
              {copy.all}
            </Button>
            {(['succeeded', 'failed'] as const).map((status) => (
              <Button
                key={status}
                size="sm"
                variant={statusFilter === status ? 'primary' : 'secondary'}
                aria-pressed={statusFilter === status}
                onClick={() => handleStatusChange(status)}
              >
                {copy.filters[status]}
              </Button>
            ))}
          </div>

          {hasError ? (
            <ErrorState
              title={copy.errorTitle}
              description={copy.errorDescription}
              retryLabel={copy.retry}
              onRetry={() => void loadHistory(page?.offset ?? 0, statusFilter)}
            />
          ) : isLoading && page === null ? (
            <div className="flex min-h-36 items-center justify-center rounded-xl border border-app-border bg-app-surface-muted">
              <Spinner label={copy.loading} className="text-app-accent" />
            </div>
          ) : page && page.items.length === 0 ? (
            <EmptyState title={copy.emptyTitle} description={copy.emptyDescription} />
          ) : page ? (
            <div className="relative">
              {isLoading ? (
                <div className="absolute inset-0 z-10 flex items-center justify-center rounded-xl bg-app-overlay backdrop-blur-sm">
                  <Spinner label={copy.loading} className="text-app-accent" />
                </div>
              ) : null}

              <div className="space-y-3">
                {page.items.map((record) => (
                  <article
                    key={record.import_id}
                    className="rounded-xl border border-app-border bg-app-surface-muted p-4"
                  >
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="font-semibold text-app-foreground">{record.dataset_name}</p>
                        <p
                          dir="ltr"
                          className="mt-1 text-left text-xs font-semibold break-all text-app-subtle"
                        >
                          {record.import_id}
                        </p>
                      </div>
                      <Badge variant={record.status === 'succeeded' ? 'success' : 'danger'}>
                        {copy.statuses[record.status]}
                      </Badge>
                    </div>

                    <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2">
                      <div>
                        <dt className="text-app-muted">{copy.pair}</dt>
                        <dd dir="ltr" className="mt-1 text-left text-app-foreground">
                          {record.pair.base_asset}/{record.pair.quote_asset}
                        </dd>
                      </div>
                      <div>
                        <dt className="text-app-muted">{copy.timeframe}</dt>
                        <dd dir="ltr" className="mt-1 text-left text-app-foreground">
                          {record.timeframe}
                        </dd>
                      </div>
                      <div className="sm:col-span-2">
                        <dt className="text-app-muted">{copy.requestedRange}</dt>
                        <dd className="mt-1 text-app-foreground">
                          {formatDate(record.requested_start_time, locale)} —{' '}
                          {formatDate(record.requested_end_time, locale)}
                        </dd>
                      </div>
                      <div>
                        <dt className="text-app-muted">{copy.completedAt}</dt>
                        <dd className="mt-1 text-app-foreground">
                          {formatDate(record.completed_at, locale)}
                        </dd>
                      </div>
                      <div>
                        <dt className="text-app-muted">{copy.candles}</dt>
                        <dd className="mt-1 text-app-foreground">
                          {formatNumber(record.candle_count, locale)}
                        </dd>
                      </div>
                    </dl>

                    {record.status === 'succeeded' && record.dataset_id ? (
                      <div className="mt-4 rounded-xl border border-emerald-500/20 bg-emerald-500/10 p-3">
                        <p className="text-xs font-semibold text-emerald-500">{copy.datasetId}</p>
                        <p
                          dir="ltr"
                          className="mt-1 text-left text-xs font-semibold break-all text-app-foreground"
                        >
                          {record.dataset_id}
                        </p>
                        <Link
                          href={`/${locale}/datasets/${encodeURIComponent(record.dataset_id)}`}
                          className="mt-3 inline-flex min-h-9 items-center justify-center rounded-lg border border-app-border bg-app-surface px-3 py-2 text-xs font-semibold text-app-foreground transition hover:border-app-accent-border hover:text-app-accent focus-visible:ring-2 focus-visible:ring-app-accent focus-visible:ring-offset-2 focus-visible:ring-offset-app-background focus-visible:outline-none"
                        >
                          {copy.viewDataset}
                        </Link>
                      </div>
                    ) : null}

                    {record.status === 'failed' ? (
                      <div className="mt-4 rounded-xl border border-red-500/20 bg-red-500/10 p-3 text-sm text-red-500">
                        {record.error_code ? (
                          <p>
                            <span className="font-semibold">{copy.errorCode}: </span>
                            <span dir="ltr">{record.error_code}</span>
                          </p>
                        ) : null}
                        {record.error_message ? (
                          <p className="mt-1">{record.error_message}</p>
                        ) : null}
                      </div>
                    ) : null}
                  </article>
                ))}
              </div>

              {page.total > 0 ? (
                <div className="mt-4 rounded-xl border border-app-border bg-app-surface px-4 py-3">
                  <Pagination
                    total={page.total}
                    limit={page.limit}
                    offset={page.offset}
                    isLoading={isLoading}
                    pageLabel={copy.page}
                    previousLabel={copy.previous}
                    nextLabel={copy.next}
                    onOffsetChange={(offset) => void loadHistory(offset, statusFilter)}
                  />
                </div>
              ) : null}
            </div>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
