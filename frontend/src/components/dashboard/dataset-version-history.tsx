import Link from 'next/link';
import { useState } from 'react';

import type { DashboardLocale } from '@/components/dashboard/dashboard-copy';
import { getDatasetDetailCopy } from '@/components/dashboard/dataset-detail-copy';
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
import { getMarketDataImportVersions, refreshMarketDataImport } from '@/lib/api/client';
import type { MarketDataImportRecord, Page } from '@/lib/api/types';

const VERSION_PAGE_SIZE = 5;

type DatasetVersionHistoryProps = {
  connectionId: string;
  importId: string;
  currentDatasetId: string;
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

export default function DatasetVersionHistory({
  connectionId,
  importId,
  currentDatasetId,
  locale,
}: DatasetVersionHistoryProps) {
  const copy = getDatasetDetailCopy(locale);
  const [page, setPage] = useState<Page<MarketDataImportRecord> | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [loadFailed, setLoadFailed] = useState(false);
  const [refreshFailed, setRefreshFailed] = useState(false);
  const [refreshResult, setRefreshResult] = useState<MarketDataImportRecord | null>(null);

  async function loadVersions(offset: number): Promise<Page<MarketDataImportRecord> | null> {
    setIsLoading(true);
    setLoadFailed(false);

    try {
      const result = await getMarketDataImportVersions(connectionId, importId, {
        limit: VERSION_PAGE_SIZE,
        offset,
      });
      setPage(result);
      return result;
    } catch {
      setLoadFailed(true);
      return null;
    } finally {
      setIsLoading(false);
    }
  }

  async function handleRefresh(): Promise<void> {
    setIsRefreshing(true);
    setRefreshFailed(false);
    setRefreshResult(null);

    try {
      const latestPage = await getMarketDataImportVersions(connectionId, importId, {
        limit: VERSION_PAGE_SIZE,
        offset: 0,
      });
      setPage(latestPage);

      const latestSuccessfulVersion = latestPage.items.find(
        (record) => record.status === 'succeeded' && record.version_number !== null,
      );

      if (!latestSuccessfulVersion) {
        setRefreshFailed(true);
        return;
      }

      const refreshed = await refreshMarketDataImport(
        connectionId,
        latestSuccessfulVersion.import_id,
      );
      setRefreshResult(refreshed);

      const updatedPage = await getMarketDataImportVersions(connectionId, importId, {
        limit: VERSION_PAGE_SIZE,
        offset: 0,
      });
      setPage(updatedPage);
    } catch {
      setRefreshFailed(true);

      try {
        const updatedPage = await getMarketDataImportVersions(connectionId, importId, {
          limit: VERSION_PAGE_SIZE,
          offset: 0,
        });
        setPage(updatedPage);
      } catch {
        // Preserve the refresh error; explicit history reload remains available.
      }
    } finally {
      setIsRefreshing(false);
    }
  }

  return (
    <Card>
      <CardHeader className="flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <CardTitle>{copy.versions.title}</CardTitle>
          <CardDescription>{copy.versions.description}</CardDescription>
        </div>

        <div className="flex flex-wrap gap-2">
          <Button
            size="sm"
            variant="secondary"
            isLoading={isLoading && page === null}
            loadingText={copy.versions.loading}
            onClick={() => void loadVersions(0)}
          >
            {page === null ? copy.versions.load : copy.versions.reload}
          </Button>

          <Button
            size="sm"
            variant="primary"
            isLoading={isRefreshing}
            loadingText={copy.versions.refreshing}
            onClick={() => void handleRefresh()}
          >
            {copy.versions.refresh}
          </Button>
        </div>
      </CardHeader>

      <CardContent className="relative">
        {isLoading && page !== null ? (
          <div className="absolute inset-0 z-10 flex items-center justify-center rounded-xl bg-app-overlay backdrop-blur-sm">
            <Spinner label={copy.versions.loading} className="text-app-accent" />
          </div>
        ) : null}

        {refreshResult ? (
          <div className="mb-5 rounded-xl border border-app-border bg-app-surface-muted p-4">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="success">{copy.versions.succeeded}</Badge>
              <Badge variant={refreshResult.content_changed ? 'info' : 'neutral'}>
                {refreshResult.content_changed
                  ? copy.versions.contentChanged
                  : copy.versions.contentUnchanged}
              </Badge>
            </div>

            {refreshResult.dataset_id && refreshResult.content_changed ? (
              <Link
                href={`/${locale}/datasets/${refreshResult.dataset_id}`}
                className="mt-3 inline-flex text-sm font-semibold text-app-accent hover:underline"
              >
                {copy.versions.openNewSnapshot}
              </Link>
            ) : null}
          </div>
        ) : null}

        {refreshFailed ? (
          <EmptyState
            title={copy.versions.refreshErrorTitle}
            description={copy.versions.refreshErrorDescription}
            className="mb-5 border-red-500/20 bg-red-500/10"
            icon={<span className="font-bold text-red-500">!</span>}
            action={
              <Button size="sm" variant="secondary" onClick={() => void loadVersions(0)}>
                {copy.versions.reload}
              </Button>
            }
          />
        ) : null}

        {loadFailed && page === null ? (
          <EmptyState
            title={copy.versions.errorTitle}
            description={copy.versions.errorDescription}
            icon={<span className="font-bold text-red-500">!</span>}
            action={
              <Button size="sm" variant="secondary" onClick={() => void loadVersions(0)}>
                {copy.versions.retry}
              </Button>
            }
          />
        ) : page === null ? (
          <p className="text-sm leading-7 text-app-muted">{copy.versions.emptyDescription}</p>
        ) : page.items.length === 0 ? (
          <EmptyState
            title={copy.versions.emptyTitle}
            description={copy.versions.emptyDescription}
          />
        ) : (
          <>
            <div className="space-y-3">
              {page.items.map((record) => (
                <article
                  key={record.import_id}
                  className="rounded-xl border border-app-border bg-app-surface-muted p-4"
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        {record.version_number !== null ? (
                          <span className="font-semibold text-app-foreground">
                            {copy.versions.version} {record.version_number}
                          </span>
                        ) : (
                          <span className="font-semibold text-app-foreground">
                            {copy.versions.refreshOperation}
                          </span>
                        )}

                        <Badge variant={record.operation === 'refresh' ? 'info' : 'neutral'}>
                          {record.operation === 'refresh'
                            ? copy.versions.refreshOperation
                            : copy.versions.initialImport}
                        </Badge>

                        {record.dataset_id === currentDatasetId ? (
                          <Badge variant="neutral">{copy.versions.currentSnapshot}</Badge>
                        ) : null}
                      </div>

                      <p className="mt-2 text-xs text-app-muted">
                        {copy.versions.completedAt}: {formatDate(record.completed_at, locale)}
                      </p>
                    </div>

                    <Badge variant={record.status === 'succeeded' ? 'success' : 'danger'}>
                      {record.status === 'succeeded'
                        ? copy.versions.succeeded
                        : copy.versions.failed}
                    </Badge>
                  </div>

                  {record.operation === 'refresh' &&
                  record.status === 'succeeded' &&
                  record.content_changed !== null ? (
                    <div className="mt-3">
                      <Badge variant={record.content_changed ? 'info' : 'neutral'}>
                        {record.content_changed
                          ? copy.versions.contentChanged
                          : copy.versions.contentUnchanged}
                      </Badge>
                    </div>
                  ) : null}

                  {record.status === 'failed' ? (
                    <div className="mt-3 rounded-lg border border-red-500/20 bg-red-500/10 p-3">
                      {record.error_code ? (
                        <p dir="ltr" className="text-left text-xs font-semibold text-red-500">
                          {record.error_code}
                        </p>
                      ) : null}
                      {record.error_message ? (
                        <p className="mt-2 text-sm leading-6 text-app-foreground">
                          {record.error_message}
                        </p>
                      ) : null}
                    </div>
                  ) : null}

                  {record.dataset_id ? (
                    <Link
                      href={`/${locale}/datasets/${record.dataset_id}`}
                      className="mt-3 inline-flex text-sm font-semibold text-app-accent hover:underline"
                    >
                      {copy.versions.openSnapshot}
                    </Link>
                  ) : null}
                </article>
              ))}
            </div>

            <div className="mt-5">
              <Pagination
                total={page.total}
                limit={page.limit}
                offset={page.offset}
                isLoading={isLoading}
                pageLabel={copy.pagination.page}
                previousLabel={copy.pagination.previous}
                nextLabel={copy.pagination.next}
                onOffsetChange={(nextOffset) => void loadVersions(nextOffset)}
              />
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
