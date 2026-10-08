'use client';

import Link from 'next/link';
import { useRef, useState } from 'react';

import { PageFrame } from '@/components/platform/page-frame';
import { PageHeader } from '@/components/platform/page-header';
import {
  Badge,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  Checkbox,
  EmptyState,
  ErrorState,
  Pagination,
  Spinner,
} from '@/components/ui';
import { getCandidateProjections } from '@/features/candidates/api/client';
import type {
  CandidateDecisionEvidence,
  CandidateProjectionSummary,
} from '@/features/candidates/api/types';
import { getCandidateComparisonCopy } from '@/features/candidates/candidate-comparison-copy';
import CandidateComparisonPanel from '@/features/candidates/candidate-comparison-panel';
import { getCandidateCopy } from '@/features/candidates/candidate-copy';
import { CandidateRankingBreakdown } from '@/features/candidates/candidate-ranking-breakdown';
import type { Page } from '@/lib/api/core/types';
import { getStrategyDisplayName } from '@/lib/strategies/presentation';
import type { PlatformLocale } from '@/platform/i18n';

const PAGE_SIZE = 12;

type CandidateCatalogProps = {
  initialPage: Page<CandidateProjectionSummary>;
  locale: PlatformLocale;
};

function numberLocale(locale: PlatformLocale): string {
  return locale === 'fa' ? 'fa-IR' : 'en-US';
}

function formatNumber(value: number, locale: PlatformLocale): string {
  return new Intl.NumberFormat(numberLocale(locale)).format(value);
}

function formatDecimal(value: string, locale: PlatformLocale): string {
  const parsedValue = Number(value);

  if (!Number.isFinite(parsedValue)) {
    return value;
  }

  return new Intl.NumberFormat(numberLocale(locale), {
    maximumFractionDigits: 6,
  }).format(parsedValue);
}

function formatPercent(value: string, locale: PlatformLocale): string {
  const parsedValue = Number(value);

  if (!Number.isFinite(parsedValue)) {
    return value;
  }

  return new Intl.NumberFormat(numberLocale(locale), {
    style: 'percent',
    maximumFractionDigits: 2,
  }).format(parsedValue);
}

function formatRiskCompatibility(
  evidence: CandidateDecisionEvidence | null,
  locale: PlatformLocale,
  fallback: string,
): string {
  const fraction = evidence?.risk_compatibility.compatibility_fraction;
  return fraction === null || fraction === undefined ? fallback : formatPercent(fraction, locale);
}

function formatDate(value: string, locale: PlatformLocale): string {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat(numberLocale(locale), {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date);
}

export default function CandidateCatalog({ initialPage, locale }: CandidateCatalogProps) {
  const copy = getCandidateCopy(locale);
  const [page, setPage] = useState(initialPage);
  const [isLoading, setIsLoading] = useState(false);
  const [hasError, setHasError] = useState(false);
  const [selectedCandidates, setSelectedCandidates] = useState<CandidateProjectionSummary[]>([]);
  const requestSequence = useRef(0);
  const comparisonCopy = getCandidateComparisonCopy(locale);

  function isCandidateSelected(candidateId: string): boolean {
    return selectedCandidates.some((candidate) => candidate.candidate_id === candidateId);
  }

  function isCandidateCompatible(candidate: CandidateProjectionSummary): boolean {
    return (
      selectedCandidates.length === 0 ||
      candidate.latest_journal_id === selectedCandidates[0].latest_journal_id
    );
  }

  function toggleCandidate(candidate: CandidateProjectionSummary): void {
    if (isCandidateSelected(candidate.candidate_id)) {
      setSelectedCandidates((current) =>
        current.filter((item) => item.candidate_id !== candidate.candidate_id),
      );
      return;
    }

    if (selectedCandidates.length >= 4 || !isCandidateCompatible(candidate)) {
      return;
    }

    setSelectedCandidates((current) => [...current, candidate]);
  }

  async function loadCandidates(offset: number): Promise<void> {
    const requestId = ++requestSequence.current;

    setIsLoading(true);
    setHasError(false);

    try {
      const result = await getCandidateProjections({
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
            <Badge variant="warning">{copy.readOnly}</Badge>
            <Badge variant="info">
              {copy.total}: {formatNumber(page.total, locale)}
            </Badge>
          </>
        }
      />

      <CandidateComparisonPanel
        key={selectedCandidates.map((candidate) => candidate.candidate_id).join(':')}
        locale={locale}
        selectedCandidates={selectedCandidates}
        onClearSelection={() => setSelectedCandidates([])}
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
            onRetry={() => void loadCandidates(page.offset)}
          />
        ) : page.items.length === 0 ? (
          <EmptyState title={copy.emptyTitle} description={copy.emptyDescription} />
        ) : (
          <div className="grid gap-4 xl:grid-cols-2">
            {page.items.map((candidate) => (
              <Card
                key={candidate.candidate_id}
                className={[
                  'overflow-hidden',
                  isCandidateSelected(candidate.candidate_id)
                    ? 'border-app-accent-border bg-app-accent-soft'
                    : '',
                ].join(' ')}
              >
                <CardHeader className="border-b border-app-border">
                  <div className="flex flex-wrap items-start justify-between gap-4">
                    <div className="min-w-0">
                      <CardTitle>
                        {candidate.pair.base_asset}/{candidate.pair.quote_asset}
                      </CardTitle>

                      <CardDescription
                        dir="ltr"
                        title={candidate.candidate_id}
                        className="mt-2 text-left text-xs font-semibold break-all"
                      >
                        {candidate.candidate_id}
                      </CardDescription>
                    </div>

                    <div className="flex flex-col items-end gap-3">
                      <div className="flex flex-wrap justify-end gap-2">
                        <Badge variant={candidate.selected ? 'success' : 'info'}>
                          {candidate.selected ? copy.selected : copy.notSelected}
                        </Badge>

                        <Badge
                          variant={
                            candidate.latest_occurrence_type === 'skipped' ? 'warning' : 'info'
                          }
                        >
                          {copy.occurrenceTypes[candidate.latest_occurrence_type]}
                        </Badge>

                        <Badge variant="info">{copy.statuses[candidate.status]}</Badge>
                        <Badge variant="warning">{copy.actions[candidate.action]}</Badge>
                      </div>

                      <Checkbox
                        label={comparisonCopy.selectCandidate}
                        checked={isCandidateSelected(candidate.candidate_id)}
                        disabled={
                          !isCandidateCompatible(candidate) ||
                          (selectedCandidates.length >= 4 &&
                            !isCandidateSelected(candidate.candidate_id))
                        }
                        description={
                          !isCandidateCompatible(candidate)
                            ? comparisonCopy.incompatibleCandidate
                            : selectedCandidates.length >= 4 &&
                                !isCandidateSelected(candidate.candidate_id)
                              ? comparisonCopy.limitReached
                              : undefined
                        }
                        onChange={() => toggleCandidate(candidate)}
                      />
                    </div>
                  </div>
                </CardHeader>

                <CardContent className="space-y-6 pt-6">
                  <dl className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                    <div className="rounded-xl border border-app-border bg-app-surface-muted p-3">
                      <dt className="text-xs text-app-muted">{copy.fields.rank}</dt>
                      <dd className="mt-2 text-sm font-semibold text-app-foreground">
                        {formatNumber(candidate.latest_rank, locale)}
                      </dd>
                    </div>

                    <div className="rounded-xl border border-app-border bg-app-surface-muted p-3">
                      <dt className="text-xs text-app-muted">{copy.fields.confidence}</dt>
                      <dd
                        dir="ltr"
                        className="mt-2 text-left text-sm font-semibold text-app-foreground"
                      >
                        {formatDecimal(candidate.confidence, locale)}
                      </dd>
                    </div>

                    <div className="rounded-xl border border-app-border bg-app-surface-muted p-3">
                      <dt className="text-xs text-app-muted">{copy.fields.signalScore}</dt>
                      <dd
                        dir="ltr"
                        className="mt-2 text-left text-sm font-semibold text-app-foreground"
                      >
                        {formatDecimal(candidate.signal_score, locale)}
                      </dd>
                    </div>

                    <div className="rounded-xl border border-app-border bg-app-surface-muted p-3">
                      <dt className="text-xs text-app-muted">{copy.fields.rankingScore}</dt>
                      <dd
                        dir="ltr"
                        className="mt-2 text-left text-sm font-semibold text-app-foreground"
                      >
                        {formatDecimal(candidate.latest_ranking_score, locale)}
                      </dd>
                    </div>

                    <div className="rounded-xl border border-app-border bg-app-surface-muted p-3">
                      <dt className="text-xs text-app-muted">{copy.fields.riskCompatibility}</dt>
                      <dd className="mt-2 text-sm font-semibold text-app-foreground">
                        {formatRiskCompatibility(
                          candidate.latest_decision_evidence,
                          locale,
                          copy.notEvaluated,
                        )}
                      </dd>
                    </div>

                    <div className="rounded-xl border border-app-border bg-app-surface-muted p-3">
                      <dt className="text-xs text-app-muted">{copy.fields.occurrences}</dt>
                      <dd className="mt-2 text-sm text-app-foreground">
                        {formatNumber(candidate.occurrence_count, locale)}
                      </dd>
                    </div>
                  </dl>

                  <CandidateRankingBreakdown
                    evidence={candidate.latest_decision_evidence}
                    locale={locale}
                  />

                  <dl className="grid gap-4 sm:grid-cols-2">
                    <div>
                      <dt className="text-xs text-app-muted">{copy.fields.strategy}</dt>
                      <dd className="mt-1 text-sm text-app-foreground">
                        {getStrategyDisplayName(candidate.strategy_name, locale)} ·{' '}
                        {candidate.strategy_version}
                      </dd>
                    </div>

                    <div>
                      <dt className="text-xs text-app-muted">{copy.fields.timeframe}</dt>
                      <dd className="mt-1 text-sm text-app-foreground">{candidate.timeframe}</dd>
                    </div>

                    <div>
                      <dt className="text-xs text-app-muted">{copy.fields.replay}</dt>
                      <dd className="mt-1 text-sm text-app-foreground">
                        {candidate.latest_replay_status
                          ? copy.replayStatuses[candidate.latest_replay_status]
                          : copy.notEvaluated}
                      </dd>
                    </div>

                    <div>
                      <dt className="text-xs text-app-muted">{copy.fields.risk}</dt>
                      <dd className="mt-1 text-sm text-app-foreground">
                        {candidate.latest_risk_decision
                          ? copy.riskDecisions[candidate.latest_risk_decision]
                          : copy.notEvaluated}
                      </dd>
                    </div>

                    {candidate.latest_skip_reason ? (
                      <div className="sm:col-span-2">
                        <dt className="text-xs text-app-muted">{copy.fields.skipReason}</dt>
                        <dd className="mt-1 text-sm text-app-foreground">
                          {copy.skipReasons[candidate.latest_skip_reason]}
                        </dd>
                      </div>
                    ) : null}
                  </dl>

                  <div className="grid gap-3 border-t border-app-border pt-4 sm:grid-cols-2">
                    <div>
                      <p className="text-xs text-app-muted">{copy.fields.recordedAt}</p>
                      <p className="mt-2 text-xs text-app-muted">
                        {formatDate(candidate.latest_recorded_at, locale)}
                      </p>
                    </div>

                    <div>
                      <p className="text-xs text-app-muted">{copy.fields.exitReason}</p>
                      <p className="mt-2 text-xs text-app-muted">
                        {candidate.exit_reason ? copy.exitReasons[candidate.exit_reason] : '—'}
                      </p>
                    </div>
                  </div>

                  <div className="flex border-t border-app-border pt-4">
                    <Link
                      href={`/${locale}/candidates/${encodeURIComponent(candidate.candidate_id)}`}
                      className="inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-xl border border-app-border bg-app-surface px-4 py-2.5 text-sm font-semibold text-app-foreground transition hover:border-app-accent-border hover:bg-app-hover hover:text-app-accent focus-visible:ring-2 focus-visible:ring-app-accent focus-visible:ring-offset-2 focus-visible:ring-offset-app-background focus-visible:outline-none"
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
        <section className="rounded-2xl border border-app-border bg-app-surface px-5 py-4">
          <Pagination
            locale={locale}
            total={page.total}
            limit={page.limit}
            offset={page.offset}
            isLoading={isLoading}
            pageLabel={copy.page}
            previousLabel={copy.previous}
            nextLabel={copy.next}
            onOffsetChange={(offset) => void loadCandidates(offset)}
          />
        </section>
      ) : null}
    </PageFrame>
  );
}
