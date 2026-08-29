'use client';

import Link from 'next/link';
import { useRef, useState } from 'react';

import type { DashboardLocale } from '@/components/dashboard/dashboard-copy';
import { getPortfolioDetailCopy } from '@/components/dashboard/portfolio-detail-copy';
import {
  Badge,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  ErrorState,
  Pagination,
  Spinner,
} from '@/components/ui';
import { getSimulatedPortfolioPositions, getSimulatedPortfolioTimeline } from '@/lib/api/client';
import type {
  Page,
  PortfolioTimelineEvent,
  SimulatedPortfolio,
  SimulatedPosition,
} from '@/lib/api/types';

const RESOURCE_PAGE_SIZE = 10;

type PortfolioDetailProps = {
  portfolio: SimulatedPortfolio;
  initialPositions: Page<SimulatedPosition>;
  initialTimeline: Page<PortfolioTimelineEvent>;
  locale: DashboardLocale;
};

function numberLocale(locale: DashboardLocale): string {
  return locale === 'fa' ? 'fa-IR' : 'en-US';
}

function formatNumber(value: number, locale: DashboardLocale): string {
  return new Intl.NumberFormat(numberLocale(locale)).format(value);
}

function formatDecimal(value: string | null, locale: DashboardLocale): string {
  if (value === null) {
    return '—';
  }

  const parsedValue = Number(value);

  if (!Number.isFinite(parsedValue)) {
    return value;
  }

  return new Intl.NumberFormat(numberLocale(locale), {
    maximumFractionDigits: 8,
  }).format(parsedValue);
}

function formatDate(value: string | null, locale: DashboardLocale): string {
  if (value === null) {
    return '—';
  }

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat(numberLocale(locale), {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date);
}

function pnlClassName(value: string | null): string {
  const parsedValue = Number(value ?? '0');

  if (parsedValue > 0) {
    return 'text-emerald-300';
  }

  if (parsedValue < 0) {
    return 'text-red-300';
  }

  return 'text-app-foreground';
}

export default function PortfolioDetail({
  portfolio,
  initialPositions,
  initialTimeline,
  locale,
}: PortfolioDetailProps) {
  const copy = getPortfolioDetailCopy(locale);
  const [positions, setPositions] = useState(initialPositions);
  const [timeline, setTimeline] = useState(initialTimeline);
  const [positionsLoading, setPositionsLoading] = useState(false);
  const [timelineLoading, setTimelineLoading] = useState(false);
  const [positionsError, setPositionsError] = useState(false);
  const [timelineError, setTimelineError] = useState(false);
  const positionsRequestSequence = useRef(0);
  const timelineRequestSequence = useRef(0);

  async function loadPositions(offset: number): Promise<void> {
    const requestId = ++positionsRequestSequence.current;
    setPositionsLoading(true);
    setPositionsError(false);

    try {
      const result = await getSimulatedPortfolioPositions(portfolio.portfolio_id, {
        limit: RESOURCE_PAGE_SIZE,
        offset,
      });

      if (requestId === positionsRequestSequence.current) {
        setPositions(result);
      }
    } catch {
      if (requestId === positionsRequestSequence.current) {
        setPositionsError(true);
      }
    } finally {
      if (requestId === positionsRequestSequence.current) {
        setPositionsLoading(false);
      }
    }
  }

  async function loadTimeline(offset: number): Promise<void> {
    const requestId = ++timelineRequestSequence.current;
    setTimelineLoading(true);
    setTimelineError(false);

    try {
      const result = await getSimulatedPortfolioTimeline(portfolio.portfolio_id, {
        limit: RESOURCE_PAGE_SIZE,
        offset,
      });

      if (requestId === timelineRequestSequence.current) {
        setTimeline(result);
      }
    } catch {
      if (requestId === timelineRequestSequence.current) {
        setTimelineError(true);
      }
    } finally {
      if (requestId === timelineRequestSequence.current) {
        setTimelineLoading(false);
      }
    }
  }

  return (
    <div className="space-y-8">
      <section>
        <Link
          href={`/${locale}/portfolios`}
          className="text-sm font-medium text-app-accent transition hover:opacity-80"
        >
          {locale === 'fa' ? '→' : '←'} {copy.back}
        </Link>

        <div className="mt-5 flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-xs font-semibold tracking-[0.25em] text-app-accent uppercase">
              {copy.eyebrow}
            </p>
            <h1 className="mt-3 text-3xl font-bold tracking-tight text-app-foreground sm:text-4xl">
              {copy.title}
            </h1>
            <p dir="ltr" className="mt-2 text-xs font-semibold text-app-muted">
              {portfolio.portfolio_id}
            </p>
          </div>

          <div className="flex flex-wrap gap-2">
            <Badge variant="warning">{copy.readOnly}</Badge>
            <Badge variant="info">{copy.modes[portfolio.mode]}</Badge>
            <Badge variant={portfolio.status === 'completed' ? 'success' : 'info'}>
              {copy.portfolioStatuses[portfolio.status]}
            </Badge>
          </div>
        </div>

        <p className="mt-3 max-w-3xl text-sm leading-7 text-app-muted sm:text-base">
          {copy.description}
        </p>
      </section>

      <Card>
        <CardHeader>
          <CardTitle>{copy.fields.portfolioId}</CardTitle>
          <CardDescription dir="ltr" className="text-xs font-semibold break-all">
            {portfolio.portfolio_id}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <dl className="grid gap-3 sm:grid-cols-3">
            {[
              [copy.fields.startingCash, portfolio.starting_cash],
              [copy.fields.cash, portfolio.cash],
              [copy.fields.equity, portfolio.equity],
            ].map(([label, value]) => (
              <div
                key={label}
                className="rounded-xl border border-app-border bg-app-surface-muted p-3"
              >
                <dt className="text-xs text-app-muted">{label}</dt>
                <dd dir="ltr" className="mt-2 text-left text-sm font-semibold text-app-foreground">
                  {formatDecimal(value, locale)}
                </dd>
              </div>
            ))}
          </dl>

          <dl className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <div>
              <dt className="text-xs text-app-muted">{copy.fields.realizedPnl}</dt>
              <dd
                dir="ltr"
                className={`mt-1 text-left text-sm font-semibold ${pnlClassName(portfolio.realized_pnl)}`}
              >
                {formatDecimal(portfolio.realized_pnl, locale)}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-app-muted">{copy.fields.unrealizedPnl}</dt>
              <dd
                dir="ltr"
                className={`mt-1 text-left text-sm font-semibold ${pnlClassName(portfolio.unrealized_pnl)}`}
              >
                {formatDecimal(portfolio.unrealized_pnl, locale)}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-app-muted">{copy.fields.feesPaid}</dt>
              <dd dir="ltr" className="mt-1 text-left text-sm font-semibold text-app-foreground">
                {formatDecimal(portfolio.fees_paid, locale)}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-app-muted">{copy.fields.feeRate}</dt>
              <dd dir="ltr" className="mt-1 text-left text-sm font-semibold text-app-foreground">
                {formatDecimal(portfolio.fee_rate, locale)}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-app-muted">{copy.fields.datasetId}</dt>
              <dd
                dir="ltr"
                className="mt-1 text-left text-xs font-semibold break-all text-app-foreground"
              >
                {portfolio.dataset_id}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-app-muted">{copy.fields.createdAt}</dt>
              <dd className="mt-1 text-sm text-app-foreground">
                {formatDate(portfolio.created_at, locale)}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-app-muted">{copy.fields.updatedAt}</dt>
              <dd className="mt-1 text-sm text-app-foreground">
                {formatDate(portfolio.updated_at, locale)}
              </dd>
            </div>
          </dl>
        </CardContent>
      </Card>

      <section className="space-y-4">
        <div>
          <h2 className="text-xl font-semibold text-app-foreground">{copy.positionsTitle}</h2>
          <p className="mt-1 text-sm text-app-muted">{copy.positionsDescription}</p>
        </div>

        <div className="relative min-h-40" aria-busy={positionsLoading}>
          {positionsLoading ? (
            <div className="absolute inset-0 z-20 flex items-center justify-center rounded-2xl bg-app-overlay backdrop-blur-sm">
              <Spinner label={copy.loading} className="text-app-accent" />
            </div>
          ) : null}

          {positionsError ? (
            <ErrorState
              title={copy.positionsError}
              description={copy.positionsError}
              retryLabel={copy.retry}
              onRetry={() => void loadPositions(positions.offset)}
            />
          ) : positions.items.length === 0 ? (
            <Card>
              <CardContent className="py-8 text-sm text-app-muted">
                {copy.positionsEmpty}
              </CardContent>
            </Card>
          ) : (
            <div className="grid gap-4 xl:grid-cols-2">
              {positions.items.map((position) => (
                <Card key={position.position_id}>
                  <CardHeader>
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <CardTitle>
                          {position.pair.base_asset}/{position.pair.quote_asset}
                        </CardTitle>
                        <CardDescription dir="ltr" className="mt-2 text-xs font-semibold">
                          {position.position_id}
                        </CardDescription>
                      </div>
                      <div className="flex gap-2">
                        <Badge variant={position.side === 'long' ? 'info' : 'warning'}>
                          {copy.positionSides[position.side]}
                        </Badge>
                        <Badge variant={position.status === 'closed' ? 'success' : 'info'}>
                          {copy.positionStatuses[position.status]}
                        </Badge>
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <dl className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                      <div>
                        <dt className="text-xs text-app-muted">{copy.fields.quantity}</dt>
                        <dd
                          dir="ltr"
                          className="mt-1 text-left text-sm font-semibold text-app-foreground"
                        >
                          {formatDecimal(position.quantity, locale)}
                        </dd>
                      </div>
                      <div>
                        <dt className="text-xs text-app-muted">{copy.fields.entryPrice}</dt>
                        <dd
                          dir="ltr"
                          className="mt-1 text-left text-sm font-semibold text-app-foreground"
                        >
                          {formatDecimal(position.entry_price, locale)}
                        </dd>
                      </div>
                      <div>
                        <dt className="text-xs text-app-muted">{copy.fields.currentPrice}</dt>
                        <dd
                          dir="ltr"
                          className="mt-1 text-left text-sm font-semibold text-app-foreground"
                        >
                          {formatDecimal(position.current_price, locale)}
                        </dd>
                      </div>
                      <div>
                        <dt className="text-xs text-app-muted">{copy.fields.exitPrice}</dt>
                        <dd
                          dir="ltr"
                          className="mt-1 text-left text-sm font-semibold text-app-foreground"
                        >
                          {formatDecimal(position.exit_price, locale)}
                        </dd>
                      </div>
                      <div>
                        <dt className="text-xs text-app-muted">{copy.fields.unrealizedPnl}</dt>
                        <dd
                          dir="ltr"
                          className={`mt-1 text-left text-sm font-semibold ${pnlClassName(position.unrealized_pnl)}`}
                        >
                          {formatDecimal(position.unrealized_pnl, locale)}
                        </dd>
                      </div>
                      <div>
                        <dt className="text-xs text-app-muted">{copy.fields.realizedPnl}</dt>
                        <dd
                          dir="ltr"
                          className={`mt-1 text-left text-sm font-semibold ${pnlClassName(position.realized_pnl)}`}
                        >
                          {formatDecimal(position.realized_pnl, locale)}
                        </dd>
                      </div>
                      <div>
                        <dt className="text-xs text-app-muted">{copy.fields.openedAt}</dt>
                        <dd className="mt-1 text-sm text-app-foreground">
                          {formatDate(position.opened_at, locale)}
                        </dd>
                      </div>
                      <div>
                        <dt className="text-xs text-app-muted">{copy.fields.closedAt}</dt>
                        <dd className="mt-1 text-sm text-app-foreground">
                          {formatDate(position.closed_at, locale)}
                        </dd>
                      </div>
                    </dl>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </div>

        {!positionsError && positions.total > 0 ? (
          <Pagination
            total={positions.total}
            limit={positions.limit}
            offset={positions.offset}
            isLoading={positionsLoading}
            pageLabel={copy.positionsPage}
            previousLabel={copy.previous}
            nextLabel={copy.next}
            onOffsetChange={(offset) => void loadPositions(offset)}
          />
        ) : null}
      </section>

      <section className="space-y-4">
        <div>
          <h2 className="text-xl font-semibold text-app-foreground">{copy.timelineTitle}</h2>
          <p className="mt-1 text-sm text-app-muted">{copy.timelineDescription}</p>
        </div>

        <div className="relative min-h-40" aria-busy={timelineLoading}>
          {timelineLoading ? (
            <div className="absolute inset-0 z-20 flex items-center justify-center rounded-2xl bg-app-overlay backdrop-blur-sm">
              <Spinner label={copy.loading} className="text-app-accent" />
            </div>
          ) : null}

          {timelineError ? (
            <ErrorState
              title={copy.timelineError}
              description={copy.timelineError}
              retryLabel={copy.retry}
              onRetry={() => void loadTimeline(timeline.offset)}
            />
          ) : timeline.items.length === 0 ? (
            <Card>
              <CardContent className="py-8 text-sm text-app-muted">
                {copy.timelineEmpty}
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-3">
              {timeline.items.map((event) => (
                <Card key={event.event_id}>
                  <CardContent className="grid gap-4 py-5 sm:grid-cols-2 lg:grid-cols-5">
                    <div>
                      <p className="text-xs text-app-muted">{copy.fields.eventNumber}</p>
                      <p className="mt-1 text-sm text-app-foreground">
                        {formatNumber(event.sequence_number, locale)}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-app-muted">
                        {copy.timelineEvents[event.event_type]}
                      </p>
                      <p className="mt-1 text-sm text-app-foreground">
                        {formatDate(event.occurred_at, locale)}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-app-muted">{copy.fields.eventEquity}</p>
                      <p
                        dir="ltr"
                        className="mt-1 text-left text-sm font-semibold text-app-foreground"
                      >
                        {formatDecimal(event.equity, locale)}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-app-muted">{copy.fields.eventPrice}</p>
                      <p
                        dir="ltr"
                        className="mt-1 text-left text-sm font-semibold text-app-foreground"
                      >
                        {formatDecimal(event.price, locale)}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-app-muted">{copy.fields.eventRealizedPnl}</p>
                      <p
                        dir="ltr"
                        className={`mt-1 text-left text-sm font-semibold ${pnlClassName(event.realized_pnl)}`}
                      >
                        {formatDecimal(event.realized_pnl, locale)}
                      </p>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </div>

        {!timelineError && timeline.total > 0 ? (
          <Pagination
            total={timeline.total}
            limit={timeline.limit}
            offset={timeline.offset}
            isLoading={timelineLoading}
            pageLabel={copy.timelinePage}
            previousLabel={copy.previous}
            nextLabel={copy.next}
            onOffsetChange={(offset) => void loadTimeline(offset)}
          />
        ) : null}
      </section>
    </div>
  );
}
