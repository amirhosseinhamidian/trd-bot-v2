'use client';

import Link from 'next/link';
import { useRef, useState } from 'react';

import type { PlatformLocale } from '@/platform/i18n';
import { getOptimizationExecutions } from '@/features/optimizations/api/client';
import type {
  OptimizationExecution,
  OptimizationExecutionStatus,
} from '@/features/optimizations/api/types';
import { getOptimizationCopy } from '@/features/optimizations/optimization-copy';
import OptimizationRunForm from '@/features/optimizations/optimization-run-form';
import {
  Badge,
  type BadgeVariant,
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
import type { Page } from '@/lib/api/core/types';
import { getStrategyDisplayName } from '@/lib/strategies/presentation';
import { PageFrame } from '@/components/platform/page-frame';
import { PageHeader } from '@/components/platform/page-header';

const PAGE_SIZE = 12;

type OptimizationCatalogProps = {
  initialPage: Page<OptimizationExecution>;
  locale: PlatformLocale;
  initialExecutionId?: string;
};

function formatNumber(value: number, locale: PlatformLocale): string {
  return new Intl.NumberFormat(locale === 'fa' ? 'fa-IR' : 'en-US').format(value);
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

function statusVariant(status: OptimizationExecutionStatus): BadgeVariant {
  if (status === 'succeeded') {
    return 'success';
  }
  if (status === 'failed') {
    return 'danger';
  }
  if (status === 'running') {
    return 'info';
  }
  return 'neutral';
}

export default function OptimizationCatalog({
  initialPage,
  locale,
  initialExecutionId,
}: OptimizationCatalogProps) {
  const copy = getOptimizationCopy(locale);
  const [page, setPage] = useState(initialPage);
  const [isLoading, setIsLoading] = useState(false);
  const [hasError, setHasError] = useState(false);
  const requestSequence = useRef(0);

  async function loadExecutions(offset: number): Promise<void> {
    const requestId = ++requestSequence.current;
    setIsLoading(true);
    setHasError(false);

    try {
      const result = await getOptimizationExecutions({
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

      <OptimizationRunForm locale={locale} initialExecutionId={initialExecutionId} />

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
            onRetry={() => void loadExecutions(page.offset)}
          />
        ) : page.items.length === 0 ? (
          <EmptyState title={copy.emptyTitle} description={copy.emptyDescription} />
        ) : (
          <div className="grid gap-4 xl:grid-cols-2">
            {page.items.map((execution) => {
              const folds = execution.robustness_plan?.total_folds;

              return (
                <Card key={execution.execution_id} className="overflow-hidden">
                  <CardHeader className="border-b border-app-border">
                    <div className="flex flex-wrap items-start justify-between gap-4">
                      <div className="min-w-0">
                        <CardTitle>
                          {getStrategyDisplayName(execution.strategy_name, locale)}
                        </CardTitle>
                        <CardDescription
                          dir="ltr"
                          className="mt-2 truncate text-left text-xs font-semibold"
                        >
                          {execution.execution_id}
                        </CardDescription>
                      </div>
                      <Badge variant={statusVariant(execution.status)}>
                        {copy.statuses[execution.status]}
                      </Badge>
                    </div>
                  </CardHeader>

                  <CardContent className="space-y-5 pt-6">
                    <dl className="grid grid-cols-2 gap-4 text-sm sm:grid-cols-4">
                      <div>
                        <dt className="text-xs text-app-muted">{copy.fields.objective}</dt>
                        <dd className="mt-1 text-app-foreground">
                          {copy.objectives[execution.objective]}
                        </dd>
                      </div>
                      <div>
                        <dt className="text-xs text-app-muted">{copy.fields.progress}</dt>
                        <dd className="mt-1 text-app-foreground">
                          {formatNumber(execution.completed_trials, locale)}/
                          {formatNumber(execution.total_trials, locale)}
                        </dd>
                      </div>
                      <div>
                        <dt className="text-xs text-app-muted">{copy.fields.folds}</dt>
                        <dd className="mt-1 text-app-foreground">
                          {folds === undefined
                            ? copy.fields.notAvailable
                            : formatNumber(folds, locale)}
                        </dd>
                      </div>
                      <div>
                        <dt className="text-xs text-app-muted">{copy.fields.createdAt}</dt>
                        <dd className="mt-1 text-app-foreground">
                          {formatDate(execution.created_at, locale)}
                        </dd>
                      </div>
                    </dl>

                    <div className="rounded-xl border border-app-border bg-app-surface-muted p-4">
                      <p className="text-xs text-app-muted">{copy.fields.bestExperiment}</p>
                      <p dir="ltr" className="mt-2 text-left text-xs break-all text-app-foreground">
                        {execution.best_experiment_id ?? copy.fields.notAvailable}
                      </p>
                    </div>

                    <Link
                      href={`/${locale}/optimizations/${encodeURIComponent(execution.execution_id)}`}
                      className="inline-flex min-h-10 w-full items-center justify-center rounded-xl border border-app-border bg-app-surface px-4 py-2.5 text-sm font-semibold text-app-foreground transition hover:bg-app-hover focus-visible:ring-2 focus-visible:ring-app-accent focus-visible:ring-offset-2 focus-visible:ring-offset-app-background focus-visible:outline-none sm:w-auto"
                    >
                      {copy.viewDetails}
                    </Link>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        )}

        {!hasError && page.total > 0 ? (
          <div className="mt-6">
            <Pagination
              isLoading={isLoading}
              limit={page.limit}
              offset={page.offset}
              total={page.total}
              pageLabel={copy.pagination}
              previousLabel={copy.previous}
              nextLabel={copy.next}
              onOffsetChange={(offset) => void loadExecutions(offset)}
            />
          </div>
        ) : null}
      </section>
    </PageFrame>
  );
}
