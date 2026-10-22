import {
  AdvancedDisclosure,
  Badge,
  type BadgeVariant,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui';
import type {
  DecisionCandidateRankingEntry,
  DecisionDisposition,
  DecisionEvaluationDetail,
  DecisionStage,
} from '@/features/decision-intelligence/api/types';
import { getDecisionIntelligenceCopy } from '@/features/decision-intelligence/decision-intelligence-copy';
import type { PlatformLocale } from '@/platform/i18n';

const stages: DecisionStage[] = [
  'strategy_evaluation',
  'candidate_ranking',
  'risk_gate',
  'portfolio_simulation',
];

export type DecisionEvidenceFocus = 'strategy' | 'signal' | 'candidate' | 'risk' | 'portfolio';

type DecisionIntelligenceEvidenceProps = {
  evidence: DecisionEvaluationDetail | null;
  focus: DecisionEvidenceFocus;
  locale: PlatformLocale;
  subjectId?: string;
};

function numberLocale(locale: PlatformLocale): string {
  return locale === 'fa' ? 'fa-IR' : 'en-US';
}

function formatDate(value: string, locale: PlatformLocale): string {
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime())
    ? value
    : new Intl.DateTimeFormat(numberLocale(locale), {
        dateStyle: 'medium',
        timeStyle: 'short',
      }).format(parsed);
}

function formatDecimal(value: string | null, locale: PlatformLocale): string {
  if (value === null) return '—';
  const parsed = Number(value);
  return Number.isFinite(parsed)
    ? new Intl.NumberFormat(numberLocale(locale), { maximumFractionDigits: 6 }).format(parsed)
    : value;
}

function formatPercent(value: string, locale: PlatformLocale): string {
  const parsed = Number(value);
  return Number.isFinite(parsed)
    ? new Intl.NumberFormat(numberLocale(locale), {
        style: 'percent',
        maximumFractionDigits: 2,
      }).format(parsed)
    : value;
}

function dispositionVariant(disposition: DecisionDisposition): BadgeVariant {
  if (disposition === 'accepted') return 'success';
  if (disposition === 'rejected') return 'danger';
  return 'warning';
}

function candidateForSubject(
  evidence: DecisionEvaluationDetail,
  subjectId?: string,
): DecisionCandidateRankingEntry | undefined {
  const entries = evidence.candidate_ranking?.entries ?? [];
  return (
    entries.find(
      (entry) =>
        entry.candidate.candidate_id === subjectId || entry.candidate.signal_id === subjectId,
    ) ?? entries[0]
  );
}

function CheckList({
  checks,
  locale,
}: {
  checks: Array<{
    name: string;
    passed: boolean;
    actual_value: string;
    limit_value: string;
    explanation: string;
  }>;
  locale: PlatformLocale;
}) {
  const copy = getDecisionIntelligenceCopy(locale);
  return (
    <div className="grid gap-3 lg:grid-cols-2">
      {checks.map((check) => (
        <article key={check.name} className="rounded-xl border border-app-border p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p dir="ltr" className="text-left text-sm font-semibold text-app-foreground">
              {check.name}
            </p>
            <Badge variant={check.passed ? 'success' : 'danger'}>
              {check.passed ? copy.passed : copy.failed}
            </Badge>
          </div>
          <p dir="ltr" className="mt-2 text-left text-xs break-all text-app-muted">
            {check.actual_value} / {check.limit_value}
          </p>
          <p className="mt-2 text-xs leading-6 text-app-muted">{check.explanation}</p>
        </article>
      ))}
    </div>
  );
}

export default function DecisionIntelligenceEvidence({
  evidence,
  focus,
  locale,
  subjectId,
}: DecisionIntelligenceEvidenceProps) {
  const copy = getDecisionIntelligenceCopy(locale);
  if (evidence === null) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>{copy.title}</CardTitle>
          <CardDescription>{copy.description}</CardDescription>
        </CardHeader>
        <CardContent className="text-sm text-app-muted">{copy.noEvidence}</CardContent>
      </Card>
    );
  }

  const outcomeByStage = new Map(evidence.outcomes.map((outcome) => [outcome.stage, outcome]));
  const candidate = candidateForSubject(evidence, subjectId);
  const risk = evidence.risk_gate?.assessment;
  const portfolio = evidence.portfolio_intelligence;
  const analysis = portfolio?.analysis;

  return (
    <section className="space-y-4" aria-labelledby="decision-intelligence-title">
      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <CardTitle id="decision-intelligence-title">{copy.title}</CardTitle>
              <CardDescription>{copy.description}</CardDescription>
            </div>
            <div className="flex flex-wrap gap-2">
              <Badge variant="warning">{copy.offline}</Badge>
              <Badge variant="neutral">{copy.noOrders}</Badge>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-5">
          <dl className="grid gap-3 sm:grid-cols-2">
            <div>
              <dt className="text-xs text-app-muted">{copy.evaluation}</dt>
              <dd dir="ltr" className="mt-1 text-left text-xs font-semibold break-all">
                {evidence.summary.evaluation_id}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-app-muted">{copy.requestedAt}</dt>
              <dd className="mt-1 text-sm font-semibold">
                {formatDate(evidence.summary.requested_at, locale)}
              </dd>
            </div>
          </dl>

          <ol className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {stages.map((stage) => {
              const outcome = outcomeByStage.get(stage);
              return (
                <li key={stage} className="rounded-xl border border-app-border p-3">
                  <p className="text-xs text-app-muted">{copy.stages[stage]}</p>
                  {outcome ? (
                    <Badge className="mt-2" variant={dispositionVariant(outcome.disposition)}>
                      {copy.dispositions[outcome.disposition]}
                    </Badge>
                  ) : (
                    <Badge className="mt-2" variant="neutral">
                      {copy.pending}
                    </Badge>
                  )}
                </li>
              );
            })}
          </ol>
        </CardContent>
      </Card>

      {(focus === 'strategy' || focus === 'signal') && (
        <Card>
          <CardHeader>
            <CardTitle>{copy.context}</CardTitle>
            <CardDescription>
              {evidence.intent.market_context.trend} · {evidence.intent.market_context.volatility}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <dl className="grid gap-3 sm:grid-cols-3">
              <div>
                <dt className="text-xs text-app-muted">{copy.confidence}</dt>
                <dd dir="ltr" className="mt-1 text-left font-semibold">
                  {formatPercent(evidence.intent.market_context.confidence, locale)}
                </dd>
              </div>
              <div>
                <dt className="text-xs text-app-muted">{copy.signals}</dt>
                <dd className="mt-1 font-semibold">{evidence.summary.signal_count}</dd>
              </div>
              {focus === 'signal' && subjectId ? (
                <div>
                  <dt className="text-xs text-app-muted">Signal ID</dt>
                  <dd dir="ltr" className="mt-1 text-left text-xs font-semibold break-all">
                    {subjectId}
                  </dd>
                </div>
              ) : null}
            </dl>
          </CardContent>
        </Card>
      )}

      {focus === 'candidate' && candidate ? (
        <Card>
          <CardHeader>
            <CardTitle>{copy.tradePlan}</CardTitle>
            <CardDescription>
              #{candidate.rank} · {copy.score} {formatDecimal(candidate.total_score, locale)}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <dl className="grid gap-3 sm:grid-cols-3">
              {[
                [copy.entry, candidate.candidate.trade_plan.entry_price],
                [copy.invalidation, candidate.candidate.trade_plan.invalidation_price],
                [copy.target, candidate.candidate.trade_plan.target_price],
              ].map(([label, value]) => (
                <div key={label} className="rounded-xl border border-app-border p-3">
                  <dt className="text-xs text-app-muted">{label}</dt>
                  <dd dir="ltr" className="mt-1 text-left font-semibold">
                    {formatDecimal(value, locale)}
                  </dd>
                </div>
              ))}
            </dl>
          </CardContent>
        </Card>
      ) : null}

      {focus === 'risk' && risk ? (
        <Card>
          <CardHeader>
            <CardTitle>{copy.riskDecision}</CardTitle>
            <CardDescription>{risk.decision}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-5">
            <CheckList checks={risk.checks} locale={locale} />
            {risk.position_sizing ? (
              <dl className="grid gap-3 sm:grid-cols-4">
                {[
                  [copy.quantity, risk.position_sizing.quantity],
                  [copy.notional, risk.position_sizing.notional],
                  [copy.maximumLoss, risk.position_sizing.maximum_loss],
                  [copy.riskBudget, risk.position_sizing.risk_budget],
                ].map(([label, value]) => (
                  <div key={label} className="rounded-xl border border-app-border p-3">
                    <dt className="text-xs text-app-muted">{label}</dt>
                    <dd dir="ltr" className="mt-1 text-left font-semibold">
                      {formatDecimal(value, locale)}
                    </dd>
                  </div>
                ))}
              </dl>
            ) : null}
          </CardContent>
        </Card>
      ) : null}

      {focus === 'portfolio' && portfolio ? (
        <Card>
          <CardHeader>
            <CardTitle>{copy.portfolioDecision}</CardTitle>
            <CardDescription>{portfolio.recommendation}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-5">
            {analysis ? (
              <>
                <dl className="grid gap-3 sm:grid-cols-3">
                  <div>
                    <dt className="text-xs text-app-muted">{copy.exposure}</dt>
                    <dd className="mt-1 font-semibold">
                      {formatPercent(analysis.exposure.projected_exposure_fraction, locale)}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs text-app-muted">{copy.concentration}</dt>
                    <dd className="mt-1 font-semibold">
                      {formatPercent(
                        analysis.exposure.projected_asset_concentration_fraction,
                        locale,
                      )}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs text-app-muted">{copy.correlation}</dt>
                    <dd className="mt-1 font-semibold">
                      {analysis.correlation.maximum_absolute_correlation === null
                        ? analysis.correlation.status
                        : formatDecimal(analysis.correlation.maximum_absolute_correlation, locale)}
                    </dd>
                  </div>
                </dl>
                <CheckList checks={analysis.checks} locale={locale} />
                <div>
                  <h3 className="text-sm font-semibold">{copy.scenarios}</h3>
                  <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                    {analysis.scenarios.map((scenario) => (
                      <div
                        key={scenario.shock_fraction}
                        className="rounded-xl border border-app-border p-3"
                      >
                        <p dir="ltr" className="text-left text-xs text-app-muted">
                          shock {formatPercent(scenario.shock_fraction, locale)}
                        </p>
                        <p className="mt-1 text-sm font-semibold">
                          loss {formatPercent(scenario.loss_fraction, locale)}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
                <div>
                  <h3 className="text-sm font-semibold">{copy.exits}</h3>
                  <p className="mt-2 text-sm text-app-muted">
                    {analysis.exit_recommendations.length === 0
                      ? copy.noExits
                      : analysis.exit_recommendations
                          .map((item) => `${item.position_id}: ${item.action}`)
                          .join(' · ')}
                  </p>
                </div>
              </>
            ) : (
              <p className="text-sm text-app-muted">{copy.unavailable}</p>
            )}
          </CardContent>
        </Card>
      ) : null}

      <AdvancedDisclosure title={copy.lineage} description={copy.lineageDescription}>
        <dl className="grid gap-4 sm:grid-cols-2">
          {[
            ['intent', evidence.intent.intent_checksum],
            ['dataset', evidence.intent.dataset.reference_checksum],
            ['strategy', evidence.intent.strategy.reference_checksum],
            ['market-context', evidence.intent.market_context.reference_checksum],
            ['policy', evidence.intent.policy.definition_checksum],
          ].map(([label, value]) => (
            <div key={label}>
              <dt dir="ltr" className="text-left text-xs text-app-muted">
                {label}
              </dt>
              <dd dir="ltr" className="mt-1 text-left text-xs break-all text-app-foreground">
                {value}
              </dd>
            </div>
          ))}
        </dl>
      </AdvancedDisclosure>
    </section>
  );
}
