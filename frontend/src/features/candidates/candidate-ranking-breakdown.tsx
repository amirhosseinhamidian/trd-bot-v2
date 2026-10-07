import { Badge } from '@/components/ui';
import { getCandidateCopy } from '@/features/candidates/candidate-copy';
import type { CandidateDecisionEvidence } from '@/lib/api/types';
import type { PlatformLocale } from '@/platform/i18n';

type CandidateRankingBreakdownProps = {
  evidence: CandidateDecisionEvidence | null;
  locale: PlatformLocale;
};

function numberLocale(locale: PlatformLocale): string {
  return locale === 'fa' ? 'fa-IR' : 'en-US';
}

function formatDecimal(value: string, locale: PlatformLocale): string {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    return value;
  }
  return new Intl.NumberFormat(numberLocale(locale), {
    maximumFractionDigits: 6,
  }).format(parsed);
}

function formatPercent(value: string, locale: PlatformLocale): string {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    return value;
  }
  return new Intl.NumberFormat(numberLocale(locale), {
    style: 'percent',
    maximumFractionDigits: 2,
  }).format(parsed);
}

function formatInteger(value: number, locale: PlatformLocale): string {
  return new Intl.NumberFormat(numberLocale(locale)).format(value);
}

export function CandidateRankingBreakdown({ evidence, locale }: CandidateRankingBreakdownProps) {
  const copy = getCandidateCopy(locale);

  if (evidence === null) {
    return (
      <div className="rounded-xl border border-dashed border-app-warning-border bg-app-warning-soft p-4 text-sm text-app-warning">
        {copy.unavailableEvidence}
      </div>
    );
  }

  const ranking = evidence.ranking;
  const risk = evidence.risk_compatibility;
  const totalChecks = risk.passed_checks + risk.failed_checks;

  return (
    <details className="group rounded-xl border border-app-border bg-app-surface-muted">
      <summary className="cursor-pointer list-none px-4 py-3 text-sm font-semibold text-app-foreground focus-visible:ring-2 focus-visible:ring-app-accent focus-visible:outline-none">
        <span className="flex items-center justify-between gap-3">
          <span>{copy.rankingBreakdown}</span>
          <span aria-hidden="true" className="text-app-accent transition group-open:rotate-180">
            ↓
          </span>
        </span>
      </summary>

      <div className="space-y-5 border-t border-app-border px-4 py-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-xs text-app-muted">{copy.rankingBreakdownDescription}</p>
          <Badge variant="info">
            {copy.scoreVersion}: {ranking.score_version}
          </Badge>
        </div>

        <dl className="grid gap-3 sm:grid-cols-3">
          {ranking.components.map((component) => (
            <div
              key={component.name}
              className="rounded-lg border border-app-border bg-app-surface p-3"
            >
              <dt className="text-xs text-app-muted">{copy.rankingComponents[component.name]}</dt>
              <dd dir="ltr" className="mt-2 text-left text-xs font-semibold text-app-foreground">
                {formatDecimal(component.raw_value, locale)} ×{' '}
                {formatPercent(component.weight, locale)} ={' '}
                {formatDecimal(component.weighted_value, locale)}
              </dd>
            </div>
          ))}
        </dl>

        <div className="rounded-lg border border-app-border bg-app-surface p-3">
          <p className="text-xs leading-6 text-app-muted">
            {ranking.tie_break.applied ? copy.tieBreakApplied : copy.tieBreakNotApplied}
          </p>
          {ranking.tie_break.applied ? (
            <p dir="ltr" className="mt-2 text-left font-mono text-xs break-all text-app-accent">
              {copy.tieOrder}: {ranking.tie_break.tied_candidate_ids.join(' → ')}
            </p>
          ) : null}
        </div>

        <div className="rounded-lg border border-app-border bg-app-surface p-3">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm font-semibold text-app-foreground">
              {copy.fields.riskCompatibility}
            </p>
            {risk.status === 'evaluated' && risk.compatibility_fraction !== null ? (
              <Badge variant={risk.failed_checks === 0 ? 'success' : 'danger'}>
                {formatPercent(risk.compatibility_fraction, locale)} ·{' '}
                {formatInteger(risk.passed_checks, locale)}/{formatInteger(totalChecks, locale)}
              </Badge>
            ) : (
              <Badge variant="warning">{copy.notEvaluated}</Badge>
            )}
          </div>

          <p className="mt-2 text-xs leading-6 text-app-muted">
            {copy.riskCompatibilityDoesNotAffectRank}
          </p>

          {risk.status === 'evaluated' ? (
            risk.failed_check_names.length === 0 ? (
              <p className="mt-3 text-xs text-app-accent">{copy.allRiskChecksPassed}</p>
            ) : (
              <div className="mt-3">
                <p className="text-xs font-medium text-app-warning">{copy.failedRiskChecks}</p>
                <ul className="mt-2 space-y-2">
                  {risk.failed_check_names.map((name) => {
                    const check = risk.checks.find((item) => item.name === name);
                    return (
                      <li key={name} className="text-xs text-app-muted">
                        <span className="font-medium text-app-foreground">
                          {copy.riskChecks[name]}
                        </span>
                        {check ? (
                          <>
                            <span dir="ltr" className="ms-2">
                              {check.actual_value} / {check.limit_value ?? '—'}
                            </span>
                            <span className="mt-1 block leading-5">{check.reason}</span>
                          </>
                        ) : null}
                      </li>
                    );
                  })}
                </ul>
              </div>
            )
          ) : risk.not_evaluated_reason ? (
            <p className="mt-3 text-xs text-app-warning">
              {copy.skipReasons[risk.not_evaluated_reason]}
            </p>
          ) : null}
        </div>
      </div>
    </details>
  );
}
