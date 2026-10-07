'use client';

import Link from 'next/link';
import { type FormEvent, useRef, useState } from 'react';

import type { DashboardLocale } from '@/components/dashboard/dashboard-copy';
import { getRiskCopy } from '@/components/dashboard/risk-copy';
import {
  Badge,
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  EmptyState,
  ErrorState,
  Input,
  Select,
  SelectOption,
  Spinner,
} from '@/components/ui';
import { getRiskDashboard, type RiskDashboardFilters } from '@/lib/api/client';
import type { RiskDashboardReport, SimulatedPortfolioSummary } from '@/lib/api/types';

const ALL_PORTFOLIOS = '__all_portfolios__';

type RiskDashboardProps = {
  initialReport: RiskDashboardReport;
  locale: DashboardLocale;
  portfolios: SimulatedPortfolioSummary[];
};

type RiskGaugeProps = {
  fraction: string | null;
  label: string;
  limit: string;
  limitLabel: string;
  locale: DashboardLocale;
  noDataLabel: string;
  overLimitLabel: string;
  withinLimit: boolean | null;
  withinLimitLabel: string;
};

function numberLocale(locale: DashboardLocale): string {
  return locale === 'fa' ? 'fa-IR' : 'en-US';
}

function formatNumber(value: number, locale: DashboardLocale): string {
  return new Intl.NumberFormat(numberLocale(locale)).format(value);
}

function formatDecimal(value: string, locale: DashboardLocale): string {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    return value;
  }
  return new Intl.NumberFormat(numberLocale(locale), {
    maximumFractionDigits: 8,
  }).format(parsed);
}

function formatPercent(value: string | null, locale: DashboardLocale): string {
  if (value === null) {
    return '—';
  }
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    return value;
  }
  return new Intl.NumberFormat(numberLocale(locale), {
    style: 'percent',
    maximumFractionDigits: 2,
  }).format(parsed);
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

function toUtcIso(value: string): string | undefined {
  if (!value) {
    return undefined;
  }
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? undefined : date.toISOString();
}

function RiskGauge({
  fraction,
  label,
  limit,
  limitLabel,
  locale,
  noDataLabel,
  overLimitLabel,
  withinLimit,
  withinLimitLabel,
}: RiskGaugeProps) {
  const parsedFraction = fraction === null ? Number.NaN : Number(fraction);
  const parsedLimit = Number(limit);
  const barPercent =
    Number.isFinite(parsedFraction) && Number.isFinite(parsedLimit) && parsedLimit > 0
      ? Math.min(Math.max((parsedFraction / parsedLimit) * 100, 0), 100)
      : 0;

  return (
    <div className="rounded-xl border border-app-border bg-app-surface-muted p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs text-app-muted">{label}</p>
          <p dir="ltr" className="mt-2 text-left text-xl font-bold text-app-foreground">
            {formatPercent(fraction, locale)}
          </p>
        </div>

        {withinLimit === null ? (
          <Badge variant="neutral">{noDataLabel}</Badge>
        ) : (
          <Badge variant={withinLimit ? 'success' : 'danger'}>
            {withinLimit ? withinLimitLabel : overLimitLabel}
          </Badge>
        )}
      </div>

      <div
        role="progressbar"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(barPercent)}
        className="mt-4 h-2 overflow-hidden rounded-full bg-app-border"
      >
        <div
          className={`h-full rounded-full ${
            withinLimit === false ? 'bg-app-danger' : 'bg-app-accent'
          }`}
          style={{ width: `${barPercent}%` }}
        />
      </div>

      <p className="mt-2 text-xs text-app-muted">
        {limitLabel}: <span dir="ltr">{formatPercent(limit, locale)}</span>
      </p>
    </div>
  );
}

export default function RiskDashboard({ initialReport, locale, portfolios }: RiskDashboardProps) {
  const copy = getRiskCopy(locale);
  const [report, setReport] = useState(initialReport);
  const [fromTime, setFromTime] = useState('');
  const [toTime, setToTime] = useState('');
  const [portfolioId, setPortfolioId] = useState(ALL_PORTFOLIOS);
  const [rangeError, setRangeError] = useState<string | null>(null);
  const [hasError, setHasError] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const lastFilters = useRef<RiskDashboardFilters>({});
  const requestSequence = useRef(0);

  async function loadReport(filters: RiskDashboardFilters): Promise<void> {
    const requestId = ++requestSequence.current;
    lastFilters.current = filters;
    setHasError(false);
    setIsLoading(true);

    try {
      const nextReport = await getRiskDashboard(filters);
      if (requestId === requestSequence.current) {
        setReport(nextReport);
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

  function handleSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();

    const parsedFrom = fromTime ? new Date(fromTime).getTime() : null;
    const parsedTo = toTime ? new Date(toTime).getTime() : null;
    if (parsedFrom !== null && parsedTo !== null && parsedTo < parsedFrom) {
      setRangeError(copy.filters.invalidRange);
      return;
    }

    setRangeError(null);
    void loadReport({
      fromTime: toUtcIso(fromTime),
      toTime: toUtcIso(toTime),
      portfolioId: portfolioId === ALL_PORTFOLIOS ? undefined : portfolioId,
    });
  }

  function clearFilters(): void {
    setFromTime('');
    setToTime('');
    setPortfolioId(ALL_PORTFOLIOS);
    setRangeError(null);
    void loadReport({});
  }

  const risk = report.portfolio_risk;
  const rejectionEvents = report.decision_events.filter(
    (event) => event.primary_rejection_reason !== null,
  );
  const decisionMetrics = [
    {
      label: copy.decisions.evaluated,
      value: formatNumber(report.decisions.evaluated_count, locale),
    },
    {
      label: copy.decisions.approved,
      value: formatNumber(report.decisions.approved_count, locale),
    },
    {
      label: copy.decisions.rejected,
      value: formatNumber(report.decisions.rejected_count, locale),
    },
    {
      label: copy.decisions.approvalRate,
      value:
        report.decisions.approval_rate === null
          ? copy.decisions.noRate
          : formatPercent(report.decisions.approval_rate, locale),
    },
  ];

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

          <div className="flex flex-wrap gap-2">
            <Badge variant="warning">{copy.readOnly}</Badge>
            <Badge variant="info">{copy.historicalOnly}</Badge>
          </div>
        </div>

        <p className="mt-3 max-w-3xl text-sm leading-7 text-app-muted sm:text-base">
          {copy.description}
        </p>
      </section>

      <Card>
        <CardHeader>
          <CardTitle>{copy.filters.title}</CardTitle>
          <CardDescription>{copy.filters.description}</CardDescription>
        </CardHeader>
        <CardContent>
          <form className="grid gap-4 lg:grid-cols-4" onSubmit={handleSubmit}>
            <Input
              type="datetime-local"
              label={copy.filters.fromTime}
              value={fromTime}
              onChange={(event) => setFromTime(event.target.value)}
            />
            <Input
              type="datetime-local"
              label={copy.filters.toTime}
              value={toTime}
              error={rangeError ?? undefined}
              onChange={(event) => setToTime(event.target.value)}
            />
            <Select
              label={copy.filters.portfolio}
              value={portfolioId}
              onValueChange={setPortfolioId}
            >
              <SelectOption value={ALL_PORTFOLIOS}>{copy.filters.allPortfolios}</SelectOption>
              {portfolios.map((portfolio) => (
                <SelectOption key={portfolio.portfolio_id} value={portfolio.portfolio_id}>
                  {portfolio.portfolio_id}
                </SelectOption>
              ))}
            </Select>
            <div className="flex items-end gap-2">
              <Button
                type="submit"
                fullWidth
                isLoading={isLoading}
                loadingText={copy.filters.applying}
              >
                {copy.filters.apply}
              </Button>
              <Button type="button" variant="secondary" onClick={clearFilters}>
                {copy.filters.reset}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      {hasError ? (
        <ErrorState
          title={copy.errorTitle}
          description={copy.errorDescription}
          retryLabel={copy.retry}
          onRetry={() => void loadReport(lastFilters.current)}
        />
      ) : (
        <div className="relative space-y-8" aria-busy={isLoading}>
          {isLoading ? (
            <div className="absolute inset-0 z-20 flex items-start justify-center rounded-2xl bg-app-overlay pt-24 backdrop-blur-sm">
              <Spinner size="lg" label={copy.filters.applying} className="text-app-accent" />
            </div>
          ) : null}

          <section>
            <div>
              <h2 className="text-xl font-semibold text-app-foreground">{copy.decisions.title}</h2>
              <p className="mt-2 text-sm text-app-muted">{copy.decisions.description}</p>
            </div>

            <dl className="mt-5 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
              {decisionMetrics.map(({ label, value }) => (
                <div
                  key={label}
                  className="rounded-2xl border border-app-border bg-app-surface p-5"
                >
                  <dt className="text-xs text-app-muted">{label}</dt>
                  <dd className="mt-3 text-2xl font-bold text-app-foreground">{value}</dd>
                </div>
              ))}
            </dl>
          </section>

          {report.decisions.evaluated_count === 0 ? (
            <EmptyState title={copy.emptyTitle} description={copy.emptyDescription} />
          ) : null}

          <section className="grid gap-6 xl:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>{copy.budget.title}</CardTitle>
                <CardDescription>{copy.budget.description}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <dl className="grid gap-3 sm:grid-cols-3">
                  <div className="rounded-xl border border-app-border bg-app-surface-muted p-4">
                    <dt className="text-xs text-app-muted">{copy.budget.openedDecisions}</dt>
                    <dd className="mt-2 text-lg font-semibold text-app-foreground">
                      {formatNumber(report.budget.opened_decisions, locale)}
                    </dd>
                  </div>
                  <div className="rounded-xl border border-app-border bg-app-surface-muted p-4">
                    <dt className="text-xs text-app-muted">{copy.budget.allocated}</dt>
                    <dd dir="ltr" className="mt-2 text-left text-sm font-semibold">
                      {formatDecimal(report.budget.allocated_risk_budget, locale)}
                    </dd>
                  </div>
                  <div className="rounded-xl border border-app-border bg-app-surface-muted p-4">
                    <dt className="text-xs text-app-muted">{copy.budget.consumed}</dt>
                    <dd dir="ltr" className="mt-2 text-left text-sm font-semibold">
                      {formatDecimal(report.budget.consumed_risk, locale)}
                    </dd>
                  </div>
                </dl>

                <div className="rounded-xl border border-app-border bg-app-surface-muted p-4">
                  <p className="text-xs text-app-muted">{copy.budget.utilization}</p>
                  <p dir="ltr" className="mt-2 text-left text-xl font-bold text-app-foreground">
                    {report.budget.consumption_fraction === null
                      ? '—'
                      : formatPercent(report.budget.consumption_fraction, locale)}
                  </p>
                  {report.budget.consumption_fraction === null ? (
                    <p className="mt-2 text-xs text-app-muted">{copy.budget.noUtilization}</p>
                  ) : null}
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>{copy.portfolioRisk.title}</CardTitle>
                <CardDescription>{copy.portfolioRisk.description}</CardDescription>
              </CardHeader>
              <CardContent>
                {risk.portfolio_count === 0 ? (
                  <EmptyState title={copy.portfolioRisk.noData} className="min-h-44" />
                ) : (
                  <dl className="grid gap-3 sm:grid-cols-2">
                    <div>
                      <dt className="text-xs text-app-muted">{copy.portfolioRisk.portfolios}</dt>
                      <dd className="mt-1 text-sm font-semibold">
                        {formatNumber(risk.portfolio_count, locale)}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-xs text-app-muted">{copy.portfolioRisk.openPositions}</dt>
                      <dd className="mt-1 text-sm font-semibold">
                        {formatNumber(risk.open_position_count, locale)}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-xs text-app-muted">{copy.portfolioRisk.equity}</dt>
                      <dd dir="ltr" className="mt-1 text-left text-sm font-semibold">
                        {formatDecimal(risk.total_equity, locale)}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-xs text-app-muted">{copy.portfolioRisk.largestPair}</dt>
                      <dd dir="ltr" className="mt-1 text-left text-sm font-semibold">
                        {risk.largest_pair
                          ? `${risk.largest_pair.base_asset}/${risk.largest_pair.quote_asset}`
                          : '—'}
                      </dd>
                    </div>
                    <div className="sm:col-span-2">
                      <dt className="text-xs text-app-muted">{copy.portfolioRisk.asOf}</dt>
                      <dd className="mt-1 text-sm font-semibold">
                        {risk.latest_event_at ? formatDate(risk.latest_event_at, locale) : '—'}
                      </dd>
                    </div>
                  </dl>
                )}
              </CardContent>
            </Card>
          </section>

          <section className="grid gap-4 lg:grid-cols-3">
            <RiskGauge
              label={copy.portfolioRisk.exposure}
              fraction={risk.exposure_fraction}
              limit={risk.exposure_limit_fraction}
              withinLimit={risk.exposure_within_limit}
              locale={locale}
              limitLabel={copy.portfolioRisk.limit}
              withinLimitLabel={copy.portfolioRisk.withinLimit}
              overLimitLabel={copy.portfolioRisk.overLimit}
              noDataLabel={copy.portfolioRisk.noData}
            />
            <RiskGauge
              label={copy.portfolioRisk.concentration}
              fraction={risk.concentration_fraction}
              limit={risk.concentration_limit_fraction}
              withinLimit={risk.concentration_within_limit}
              locale={locale}
              limitLabel={copy.portfolioRisk.limit}
              withinLimitLabel={copy.portfolioRisk.withinLimit}
              overLimitLabel={copy.portfolioRisk.overLimit}
              noDataLabel={copy.portfolioRisk.noData}
            />
            <RiskGauge
              label={copy.portfolioRisk.drawdown}
              fraction={risk.max_drawdown_fraction}
              limit={risk.drawdown_limit_fraction}
              withinLimit={risk.drawdown_within_limit}
              locale={locale}
              limitLabel={copy.portfolioRisk.limit}
              withinLimitLabel={copy.portfolioRisk.withinLimit}
              overLimitLabel={copy.portfolioRisk.overLimit}
              noDataLabel={copy.portfolioRisk.noData}
            />
          </section>

          <Card>
            <CardHeader>
              <CardTitle>{copy.reasons.title}</CardTitle>
              <CardDescription>{copy.reasons.description}</CardDescription>
            </CardHeader>
            <CardContent>
              <ol className="grid gap-3 md:grid-cols-2">
                {report.rejection_reasons.map((reason) => {
                  const matchingEvents = rejectionEvents.filter(
                    (event) => event.primary_rejection_reason === reason.name,
                  );

                  return (
                    <li
                      key={reason.name}
                      className="rounded-xl border border-app-border bg-app-surface-muted p-4"
                    >
                      <div className="flex items-center justify-between gap-3">
                        <span className="text-sm font-medium text-app-foreground">
                          {copy.reasons.labels[reason.name]}
                        </span>
                        <Badge variant={reason.rejected_decisions > 0 ? 'danger' : 'neutral'}>
                          {formatNumber(reason.rejected_decisions, locale)}
                        </Badge>
                      </div>

                      {matchingEvents.length > 0 ? (
                        <div className="mt-3 flex flex-wrap gap-2">
                          {matchingEvents.map((event) => (
                            <Link
                              key={event.event_id}
                              href={`#${event.event_id}`}
                              className="rounded-md bg-app-surface px-2 py-1 font-mono text-[11px] text-app-accent hover:underline"
                            >
                              {event.candidate_id}
                            </Link>
                          ))}
                        </div>
                      ) : null}
                    </li>
                  );
                })}
              </ol>
              <p className="mt-4 text-xs text-app-muted">{copy.reasons.reconciled}</p>
            </CardContent>
          </Card>

          <section>
            <div>
              <h2 className="text-xl font-semibold text-app-foreground">{copy.events.title}</h2>
              <p className="mt-2 text-sm text-app-muted">{copy.events.description}</p>
            </div>

            <ol className="mt-5 space-y-4">
              {report.decision_events.map((event) => (
                <li
                  id={event.event_id}
                  key={event.event_id}
                  className="scroll-mt-24 rounded-2xl border border-app-border bg-app-surface p-5"
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <p className="text-xs text-app-muted">{copy.events.journal}</p>
                      <p
                        dir="ltr"
                        className="mt-1 text-left font-mono text-xs break-all text-app-foreground"
                      >
                        {event.journal_id}
                      </p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <Badge variant={event.decision === 'approved' ? 'success' : 'danger'}>
                        {copy.events[event.decision]}
                      </Badge>
                      <Badge variant="info">{copy.events.replay[event.replay_status]}</Badge>
                    </div>
                  </div>

                  <dl className="mt-4 grid gap-3 sm:grid-cols-3">
                    <div>
                      <dt className="text-xs text-app-muted">{copy.events.evaluatedAt}</dt>
                      <dd className="mt-1 text-sm">{formatDate(event.evaluated_at, locale)}</dd>
                    </div>
                    <div>
                      <dt className="text-xs text-app-muted">{copy.events.riskBudget}</dt>
                      <dd dir="ltr" className="mt-1 text-left text-sm font-semibold">
                        {formatDecimal(event.risk_budget, locale)}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-xs text-app-muted">{copy.events.riskConsumed}</dt>
                      <dd dir="ltr" className="mt-1 text-left text-sm font-semibold">
                        {formatDecimal(event.risk_consumed, locale)}
                      </dd>
                    </div>
                  </dl>

                  {event.failed_check_names.length > 0 ? (
                    <div className="mt-4">
                      <p className="text-xs text-app-muted">{copy.events.failedChecks}</p>
                      <div className="mt-2 flex flex-wrap gap-2">
                        {event.failed_check_names.map((name) => (
                          <Badge key={name} variant="danger">
                            {copy.reasons.labels[name]}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  ) : null}

                  <div className="mt-5 flex flex-wrap gap-3 border-t border-app-border pt-4">
                    <Link
                      href={`/${locale}/candidates/${encodeURIComponent(event.candidate_id)}#risk-decision`}
                      className="rounded-xl border border-app-accent-border bg-app-accent-soft px-4 py-2.5 text-sm font-semibold text-app-accent transition hover:opacity-80 focus-visible:ring-2 focus-visible:ring-app-accent focus-visible:outline-none"
                    >
                      {copy.events.viewCandidate}
                    </Link>
                    <Link
                      href={`/${locale}/portfolios/${encodeURIComponent(event.portfolio_id)}`}
                      className="rounded-xl border border-app-border bg-app-surface px-4 py-2.5 text-sm font-semibold text-app-foreground transition hover:bg-app-hover focus-visible:ring-2 focus-visible:ring-app-accent focus-visible:outline-none"
                    >
                      {copy.events.viewPortfolio}
                    </Link>
                  </div>
                </li>
              ))}
            </ol>
          </section>

          <p className="rounded-xl border border-app-warning-border bg-app-warning-soft p-4 text-xs leading-6 text-app-warning">
            {copy.scope}
          </p>
        </div>
      )}
    </div>
  );
}
