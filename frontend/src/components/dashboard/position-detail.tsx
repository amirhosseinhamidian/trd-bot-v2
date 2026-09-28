import Link from 'next/link';

import type { DashboardLocale } from '@/components/dashboard/dashboard-copy';
import { getPositionDetailCopy } from '@/components/dashboard/position-detail-copy';
import { Badge, Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui';
import type {
  CandidateDecisionLineageNode,
  CandidateExitReason,
  CandidateRiskDecision,
  PositionDetailReport,
} from '@/lib/api/types';

type PositionDetailProps = {
  locale: DashboardLocale;
  report: PositionDetailReport;
};

function numberLocale(locale: DashboardLocale): string {
  return locale === 'fa' ? 'fa-IR' : 'en-US';
}

function formatDecimal(value: string | null, locale: DashboardLocale): string {
  if (value === null) {
    return '—';
  }
  const parsed = Number(value);
  return Number.isFinite(parsed)
    ? new Intl.NumberFormat(numberLocale(locale), { maximumFractionDigits: 8 }).format(parsed)
    : value;
}

function formatDate(value: string | null, locale: DashboardLocale): string {
  if (value === null) {
    return '—';
  }
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? value
    : new Intl.DateTimeFormat(numberLocale(locale), {
        dateStyle: 'medium',
        timeStyle: 'short',
      }).format(date);
}

function pnlClassName(value: string | null): string {
  const parsed = Number(value ?? '0');
  if (parsed > 0) return 'text-emerald-300';
  if (parsed < 0) return 'text-red-300';
  return 'text-app-foreground';
}

function nodeHref(
  node: CandidateDecisionLineageNode,
  experimentId: string | undefined,
  locale: DashboardLocale,
  portfolioId: string,
): string | null {
  if (node.status !== 'available' || node.resource_id === null) return null;
  if (node.kind === 'dataset') {
    return `/${locale}/datasets/${encodeURIComponent(node.resource_id)}`;
  }
  if (node.kind === 'experiment') {
    return `/${locale}/experiments/${encodeURIComponent(node.resource_id)}`;
  }
  if (node.kind === 'signal' && experimentId) {
    return `/${locale}/signals/${encodeURIComponent(experimentId)}/${encodeURIComponent(node.resource_id)}`;
  }
  if (node.kind === 'candidate') {
    return `/${locale}/candidates/${encodeURIComponent(node.resource_id)}`;
  }
  if (node.kind === 'position') {
    return `/${locale}/portfolios/${encodeURIComponent(portfolioId)}`;
  }
  return null;
}

export default function PositionDetail({ locale, report }: PositionDetailProps) {
  const copy = getPositionDetailCopy(locale);
  const position = report.position;
  const experimentId = report.nodes.find((node) => node.kind === 'experiment')?.resource_id;
  const evidence = report.decision_evidence;
  const risk = evidence?.risk_compatibility;
  const accounting: Array<[string, string | null, boolean?]> = [
    [copy.fields.quantity, position.quantity],
    [copy.fields.entryPrice, position.entry_price],
    [copy.fields.currentPrice, position.current_price],
    [copy.fields.exitPrice, position.exit_price],
    [copy.fields.reservedNotional, position.reserved_notional],
    [copy.fields.entryFee, position.entry_fee],
    [copy.fields.exitFee, position.exit_fee],
    [copy.fields.grossPnl, position.gross_realized_pnl, true],
    [copy.fields.realizedPnl, position.realized_pnl, true],
    [copy.fields.unrealizedPnl, position.unrealized_pnl, true],
  ];

  return (
    <div className="space-y-8">
      <section>
        <Link
          href={`/${locale}/portfolios/${encodeURIComponent(position.portfolio_id)}`}
          className="rounded-sm text-sm font-medium text-app-accent transition hover:opacity-80 focus-visible:ring-2 focus-visible:ring-app-accent focus-visible:outline-none"
        >
          {locale === 'fa' ? '→' : '←'} {copy.back}
        </Link>
        <div className="mt-5 flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0">
            <p className="text-xs font-semibold tracking-[0.25em] text-app-accent uppercase">
              {copy.eyebrow}
            </p>
            <h1 className="mt-3 text-3xl font-bold tracking-tight text-app-foreground sm:text-4xl">
              {copy.title}
            </h1>
            <p dir="ltr" className="mt-2 text-left text-xs font-semibold break-all text-app-muted">
              {position.position_id}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Badge variant="warning">{copy.readOnly}</Badge>
            <Badge variant={position.side === 'long' ? 'info' : 'warning'}>
              {copy.sides[position.side]}
            </Badge>
            <Badge variant={position.status === 'closed' ? 'success' : 'info'}>
              {copy.positionStatuses[position.status]}
            </Badge>
            <Badge variant={report.lineage_status === 'complete' ? 'success' : 'warning'}>
              {copy.lineageStatuses[report.lineage_status]}
            </Badge>
          </div>
        </div>
        <p className="mt-3 max-w-3xl text-sm leading-7 text-app-muted sm:text-base">
          {copy.description}
        </p>
      </section>

      <Card>
        <CardHeader>
          <CardTitle>{copy.accountingTitle}</CardTitle>
          <CardDescription>{copy.accountingDescription}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <dl className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
            {accounting.map(([label, value, isPnl]) => (
              <div
                key={label}
                className="rounded-xl border border-app-border bg-app-surface-muted p-3"
              >
                <dt className="text-xs text-app-muted">{label}</dt>
                <dd
                  dir="ltr"
                  className={`mt-2 text-left text-sm font-semibold ${isPnl ? pnlClassName(value) : 'text-app-foreground'}`}
                >
                  {formatDecimal(value, locale)}
                </dd>
              </div>
            ))}
          </dl>
          <dl className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {[
              [copy.fields.openedAt, position.opened_at],
              [copy.fields.currentAt, position.current_at],
              [copy.fields.closedAt, position.closed_at],
            ].map(([label, value]) => (
              <div key={label}>
                <dt className="text-xs text-app-muted">{label}</dt>
                <dd className="mt-1 text-sm text-app-foreground">{formatDate(value, locale)}</dd>
              </div>
            ))}
          </dl>
        </CardContent>
      </Card>

      <section>
        <h2 className="text-xl font-semibold text-app-foreground">{copy.lineageTitle}</h2>
        <p className="mt-2 text-sm text-app-muted">{copy.lineageDescription}</p>
        <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {report.nodes.map((node) => {
            const href = nodeHref(node, experimentId ?? undefined, locale, position.portfolio_id);
            let outcome = node.outcome;
            if (node.kind === 'risk' && outcome) {
              outcome = copy.riskDecisions[outcome as CandidateRiskDecision] ?? outcome;
            }
            if (node.kind === 'exit' && outcome) {
              outcome = copy.exitReasons[outcome as CandidateExitReason] ?? outcome;
            }
            return (
              <Card key={node.kind} className="bg-app-surface-muted">
                <CardHeader>
                  <div className="flex items-start justify-between gap-3">
                    <CardTitle className="text-base">{copy.nodeKinds[node.kind]}</CardTitle>
                    <Badge variant={node.status === 'available' ? 'success' : 'warning'}>
                      {copy.nodeStatuses[node.status]}
                    </Badge>
                  </div>
                  {outcome ? <CardDescription>{outcome}</CardDescription> : null}
                </CardHeader>
                <CardContent className="space-y-3">
                  {node.resource_id ? (
                    <p
                      dir="ltr"
                      className="text-left text-xs font-semibold break-all text-app-muted"
                    >
                      {node.resource_id}
                    </p>
                  ) : null}
                  {node.reason ? (
                    <p className="text-xs leading-5 text-app-muted">
                      {copy.reasons[node.reason] ?? node.reason}
                    </p>
                  ) : null}
                  {href ? (
                    <Link href={href} className="inline-flex text-sm font-semibold text-app-accent">
                      {copy.viewResource}
                    </Link>
                  ) : null}
                </CardContent>
              </Card>
            );
          })}
        </div>
      </section>

      <Card>
        <CardHeader>
          <CardTitle>{copy.rankingTitle}</CardTitle>
          {report.journal_id ? (
            <CardDescription dir="ltr">{report.journal_id}</CardDescription>
          ) : null}
        </CardHeader>
        <CardContent className="space-y-5">
          {evidence ? (
            <>
              <dl className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
                {[
                  [copy.fields.rank, String(evidence.ranking.rank)],
                  [copy.fields.rankingScore, evidence.ranking.total_score],
                  [copy.fields.scoreVersion, evidence.ranking.score_version],
                  [copy.fields.passedChecks, String(risk?.passed_checks ?? 0)],
                  [copy.fields.failedChecks, String(risk?.failed_checks ?? 0)],
                ].map(([label, value]) => (
                  <div key={label}>
                    <dt className="text-xs text-app-muted">{label}</dt>
                    <dd
                      dir="ltr"
                      className="mt-1 text-left text-sm font-semibold text-app-foreground"
                    >
                      {value}
                    </dd>
                  </div>
                ))}
              </dl>
              {risk && risk.checks.length > 0 ? (
                <div>
                  <h3 className="text-sm font-semibold text-app-foreground">{copy.riskTitle}</h3>
                  <div className="mt-3 grid gap-3 md:grid-cols-2">
                    {risk.checks.map((check) => (
                      <div key={check.name} className="rounded-xl border border-app-border p-3">
                        <div className="flex items-center justify-between gap-3">
                          <p className="text-sm font-semibold text-app-foreground">
                            {check.name.replaceAll('_', ' ')}
                          </p>
                          <Badge variant={check.passed ? 'success' : 'danger'}>
                            {check.passed
                              ? copy.nodeStatuses.available
                              : copy.nodeStatuses.unavailable}
                          </Badge>
                        </div>
                        <p className="mt-2 text-xs leading-5 text-app-muted">{check.reason}</p>
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}
            </>
          ) : (
            <p className="text-sm text-app-muted">{copy.rankingUnavailable}</p>
          )}
        </CardContent>
      </Card>

      <section>
        <h2 className="text-xl font-semibold text-app-foreground">{copy.eventsTitle}</h2>
        <p className="mt-2 text-sm text-app-muted">{copy.eventsDescription}</p>
        {report.events.length === 0 ? (
          <Card className="mt-4">
            <CardContent className="py-8 text-sm text-app-muted">{copy.eventsEmpty}</CardContent>
          </Card>
        ) : (
          <div className="mt-4 space-y-3">
            {report.events.map((event) => (
              <Card key={event.event_id}>
                <CardContent className="grid gap-4 py-5 sm:grid-cols-2 lg:grid-cols-5">
                  <div>
                    <p className="text-xs text-app-muted">{copy.fields.eventNumber}</p>
                    <p className="mt-1 text-sm text-app-foreground">{event.sequence_number}</p>
                  </div>
                  <div>
                    <p className="text-xs text-app-muted">{copy.eventTypes[event.event_type]}</p>
                    <p className="mt-1 text-sm text-app-foreground">
                      {formatDate(event.occurred_at, locale)}
                    </p>
                  </div>
                  {[
                    [copy.fields.price, event.price],
                    [copy.fields.equity, event.equity],
                    [copy.fields.realizedPnl, event.realized_pnl],
                  ].map(([label, value]) => (
                    <div key={label}>
                      <p className="text-xs text-app-muted">{label}</p>
                      <p
                        dir="ltr"
                        className="mt-1 text-left text-sm font-semibold text-app-foreground"
                      >
                        {formatDecimal(value, locale)}
                      </p>
                    </div>
                  ))}
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
