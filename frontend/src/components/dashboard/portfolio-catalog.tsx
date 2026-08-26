'use client';

import Link from 'next/link';
import { useRef, useState } from 'react';

import type { DashboardLocale } from '@/components/dashboard/dashboard-copy';
import { getPortfolioCopy } from '@/components/dashboard/portfolio-copy';
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
import { getSimulatedPortfolios } from '@/lib/api/client';
import type { Page, SimulatedPortfolioSummary } from '@/lib/api/types';

const PAGE_SIZE = 12;

type PortfolioCatalogProps = {
  initialPage: Page<SimulatedPortfolioSummary>;
  locale: DashboardLocale;
};

function numberLocale(locale: DashboardLocale): string {
  return locale === 'fa' ? 'fa-IR' : 'en-US';
}

function formatNumber(value: number, locale: DashboardLocale): string {
  return new Intl.NumberFormat(numberLocale(locale)).format(value);
}

function formatDecimal(value: string, locale: DashboardLocale): string {
  const parsedValue = Number(value);

  if (!Number.isFinite(parsedValue)) {
    return value;
  }

  return new Intl.NumberFormat(numberLocale(locale), {
    maximumFractionDigits: 8,
  }).format(parsedValue);
}

function formatDate(value: string, locale: DashboardLocale): string {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat(numberLocale(locale), {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date);
}

function pnlClassName(value: string): string {
  const parsedValue = Number(value);

  if (parsedValue > 0) {
    return 'text-emerald-300';
  }

  if (parsedValue < 0) {
    return 'text-red-300';
  }

  return 'text-slate-200';
}

export default function PortfolioCatalog({ initialPage, locale }: PortfolioCatalogProps) {
  const copy = getPortfolioCopy(locale);
  const [page, setPage] = useState(initialPage);
  const [isLoading, setIsLoading] = useState(false);
  const [hasError, setHasError] = useState(false);
  const requestSequence = useRef(0);

  async function loadPortfolios(offset: number): Promise<void> {
    const requestId = ++requestSequence.current;

    setIsLoading(true);
    setHasError(false);

    try {
      const result = await getSimulatedPortfolios({
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
            <Badge variant="warning">{copy.readOnly}</Badge>

            <Badge variant="info">
              {copy.total}: {formatNumber(page.total, locale)}
            </Badge>
          </div>
        </div>

        <p className="mt-3 max-w-3xl text-sm leading-7 text-slate-400 sm:text-base">
          {copy.description}
        </p>
      </section>

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
            onRetry={() => void loadPortfolios(page.offset)}
          />
        ) : page.items.length === 0 ? (
          <EmptyState title={copy.emptyTitle} description={copy.emptyDescription} />
        ) : (
          <div className="grid gap-4 xl:grid-cols-2">
            {page.items.map((portfolio) => (
              <Card key={portfolio.portfolio_id} className="overflow-hidden">
                <CardHeader className="border-b border-slate-800">
                  <div className="flex flex-wrap items-start justify-between gap-4">
                    <div className="min-w-0">
                      <CardTitle>{copy.modes[portfolio.mode]}</CardTitle>

                      <CardDescription
                        dir="ltr"
                        title={portfolio.portfolio_id}
                        className="mt-2 truncate text-left font-mono text-xs"
                      >
                        {portfolio.portfolio_id}
                      </CardDescription>
                    </div>

                    <Badge variant={portfolio.status === 'completed' ? 'success' : 'info'}>
                      {copy.statuses[portfolio.status]}
                    </Badge>
                  </div>
                </CardHeader>

                <CardContent className="space-y-6 pt-6">
                  <dl className="grid gap-3 sm:grid-cols-3">
                    <div className="rounded-xl border border-slate-800 bg-slate-950/50 p-3">
                      <dt className="text-xs text-slate-500">{copy.fields.startingCash}</dt>
                      <dd dir="ltr" className="mt-2 text-left font-mono text-sm text-slate-200">
                        {formatDecimal(portfolio.starting_cash, locale)}
                      </dd>
                    </div>

                    <div className="rounded-xl border border-slate-800 bg-slate-950/50 p-3">
                      <dt className="text-xs text-slate-500">{copy.fields.cash}</dt>
                      <dd dir="ltr" className="mt-2 text-left font-mono text-sm text-slate-200">
                        {formatDecimal(portfolio.cash, locale)}
                      </dd>
                    </div>

                    <div className="rounded-xl border border-slate-800 bg-slate-950/50 p-3">
                      <dt className="text-xs text-slate-500">{copy.fields.equity}</dt>
                      <dd dir="ltr" className="mt-2 text-left font-mono text-sm text-cyan-200">
                        {formatDecimal(portfolio.equity, locale)}
                      </dd>
                    </div>
                  </dl>

                  <dl className="grid gap-3 sm:grid-cols-3">
                    <div>
                      <dt className="text-xs text-slate-500">{copy.fields.realizedPnl}</dt>
                      <dd
                        dir="ltr"
                        className={`mt-1 text-left font-mono text-sm ${pnlClassName(portfolio.realized_pnl)}`}
                      >
                        {formatDecimal(portfolio.realized_pnl, locale)}
                      </dd>
                    </div>

                    <div>
                      <dt className="text-xs text-slate-500">{copy.fields.unrealizedPnl}</dt>
                      <dd
                        dir="ltr"
                        className={`mt-1 text-left font-mono text-sm ${pnlClassName(portfolio.unrealized_pnl)}`}
                      >
                        {formatDecimal(portfolio.unrealized_pnl, locale)}
                      </dd>
                    </div>

                    <div>
                      <dt className="text-xs text-slate-500">{copy.fields.feesPaid}</dt>
                      <dd dir="ltr" className="mt-1 text-left font-mono text-sm text-slate-200">
                        {formatDecimal(portfolio.fees_paid, locale)}
                      </dd>
                    </div>
                  </dl>

                  <dl className="grid grid-cols-2 gap-4 text-sm">
                    <div>
                      <dt className="text-xs text-slate-500">{copy.fields.positions}</dt>
                      <dd className="mt-1 text-slate-200">
                        {formatNumber(portfolio.position_count, locale)}
                      </dd>
                    </div>

                    <div>
                      <dt className="text-xs text-slate-500">{copy.fields.timelineEvents}</dt>
                      <dd className="mt-1 text-slate-200">
                        {formatNumber(portfolio.event_count, locale)}
                      </dd>
                    </div>
                  </dl>

                  <div className="grid gap-3 border-t border-slate-800 pt-4 sm:grid-cols-2">
                    <div>
                      <p className="text-xs text-slate-500">{copy.fields.datasetId}</p>
                      <p
                        dir="ltr"
                        title={portfolio.dataset_id}
                        className="mt-2 truncate text-left font-mono text-xs text-slate-400"
                      >
                        {portfolio.dataset_id}
                      </p>
                    </div>

                    <div>
                      <p className="text-xs text-slate-500">{copy.fields.updatedAt}</p>
                      <p className="mt-2 text-xs text-slate-400">
                        {formatDate(portfolio.updated_at, locale)}
                      </p>
                    </div>
                  </div>

                  <div className="flex border-t border-slate-800 pt-4">
                    <Link
                      href={`/${locale}/portfolios/${encodeURIComponent(portfolio.portfolio_id)}`}
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
            onOffsetChange={(offset) => void loadPortfolios(offset)}
          />
        </section>
      ) : null}
    </div>
  );
}
