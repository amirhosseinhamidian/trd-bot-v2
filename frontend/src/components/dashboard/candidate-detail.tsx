'use client';

import Link from 'next/link';
import { useRef, useState } from 'react';

import { getCandidateDetailCopy } from '@/components/dashboard/candidate-detail-copy';
import type { DashboardLocale } from '@/components/dashboard/dashboard-copy';
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
import { getCandidateLineage } from '@/lib/api/client';
import type { CandidateJournalOccurrence, CandidateProjectionDetail, Page } from '@/lib/api/types';

const LINEAGE_PAGE_SIZE = 10;

type CandidateDetailProps = {
  candidate: CandidateProjectionDetail;
  initialLineage: Page<CandidateJournalOccurrence>;
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
    maximumFractionDigits: 6,
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

export default function CandidateDetail({
  candidate,
  initialLineage,
  locale,
}: CandidateDetailProps) {
  const copy = getCandidateDetailCopy(locale);
  const [lineage, setLineage] = useState(initialLineage);
  const [isLoading, setIsLoading] = useState(false);
  const [hasError, setHasError] = useState(false);
  const requestSequence = useRef(0);

  async function loadLineage(offset: number): Promise<void> {
    const requestId = ++requestSequence.current;

    setIsLoading(true);
    setHasError(false);

    try {
      const result = await getCandidateLineage(candidate.candidate.candidate_id, {
        limit: LINEAGE_PAGE_SIZE,
        offset,
      });

      if (requestId === requestSequence.current) {
        setLineage(result);
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

  const snapshot = candidate.candidate;
  const latest = candidate.latest;

  return (
    <div className="space-y-8">
      <section>
        <Link
          href={`/${locale}/candidates`}
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
              {snapshot.pair.base_asset}/{snapshot.pair.quote_asset}
            </h1>

            <p dir="ltr" className="mt-2 text-xs font-semibold text-app-muted">
              {snapshot.candidate_id}
            </p>
          </div>

          <div className="flex flex-wrap gap-2">
            <Badge variant="warning">{copy.readOnly}</Badge>
            <Badge variant={latest.selected ? 'success' : 'info'}>
              {latest.selected ? copy.selected : copy.notSelected}
            </Badge>
            <Badge variant={latest.occurrence_type === 'skipped' ? 'warning' : 'info'}>
              {copy.occurrenceTypes[latest.occurrence_type]}
            </Badge>
            <Badge variant="info">{copy.statuses[snapshot.status]}</Badge>
            <Badge variant="warning">{copy.actions[snapshot.action]}</Badge>
          </div>
        </div>
      </section>

      <Card>
        <CardHeader>
          <CardTitle>{snapshot.strategy_name}</CardTitle>
          <CardDescription>{snapshot.strategy_version}</CardDescription>
        </CardHeader>

        <CardContent className="space-y-6">
          <dl className="grid gap-3 sm:grid-cols-3">
            <div className="rounded-xl border border-app-border bg-app-surface-muted p-3">
              <dt className="text-xs text-app-muted">{copy.fields.confidence}</dt>
              <dd dir="ltr" className="mt-2 text-left text-sm font-semibold text-app-foreground">
                {formatDecimal(snapshot.confidence, locale)}
              </dd>
            </div>
            <div className="rounded-xl border border-app-border bg-app-surface-muted p-3">
              <dt className="text-xs text-app-muted">{copy.fields.signalScore}</dt>
              <dd dir="ltr" className="mt-2 text-left text-sm font-semibold text-app-foreground">
                {formatDecimal(snapshot.signal_score, locale)}
              </dd>
            </div>
            <div className="rounded-xl border border-app-border bg-app-surface-muted p-3">
              <dt className="text-xs text-app-muted">{copy.fields.occurrences}</dt>
              <dd className="mt-2 text-sm text-app-foreground">
                {formatNumber(candidate.occurrence_count, locale)}
              </dd>
            </div>
          </dl>

          <dl className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <div>
              <dt className="text-xs text-app-muted">{copy.fields.datasetId}</dt>
              <dd
                dir="ltr"
                className="mt-1 text-left text-xs font-semibold break-all text-app-foreground"
              >
                {snapshot.dataset_id}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-app-muted">{copy.fields.experimentId}</dt>
              <dd
                dir="ltr"
                className="mt-1 text-left text-xs font-semibold break-all text-app-foreground"
              >
                {snapshot.experiment_id}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-app-muted">{copy.fields.signalId}</dt>
              <dd
                dir="ltr"
                className="mt-1 text-left text-xs font-semibold break-all text-app-foreground"
              >
                {snapshot.signal_id}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-app-muted">{copy.fields.timeframe}</dt>
              <dd className="mt-1 text-sm text-app-foreground">{snapshot.timeframe}</dd>
            </div>
            <div>
              <dt className="text-xs text-app-muted">{copy.fields.createdAt}</dt>
              <dd className="mt-1 text-sm text-app-foreground">
                {formatDate(snapshot.created_at, locale)}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-app-muted">{copy.fields.validUntil}</dt>
              <dd className="mt-1 text-sm text-app-foreground">
                {formatDate(snapshot.valid_until, locale)}
              </dd>
            </div>
          </dl>

          <div className="grid gap-3 border-t border-app-border pt-5 sm:grid-cols-2 lg:grid-cols-4">
            <div>
              <p className="text-xs text-app-muted">{copy.fields.replay}</p>
              <p className="mt-2 text-sm text-app-foreground">
                {latest.replay_status
                  ? copy.replayStatuses[latest.replay_status]
                  : copy.notEvaluated}
              </p>
            </div>
            <div>
              <p className="text-xs text-app-muted">{copy.fields.risk}</p>
              <p className="mt-2 text-sm text-app-foreground">
                {latest.risk_decision
                  ? copy.riskDecisions[latest.risk_decision]
                  : copy.notEvaluated}
              </p>
            </div>
            <div>
              <p className="text-xs text-app-muted">{copy.fields.positionId}</p>
              <p
                dir="ltr"
                className="mt-2 text-left text-xs font-semibold break-all text-app-foreground"
              >
                {latest.position_id ?? '—'}
              </p>
            </div>
            <div>
              <p className="text-xs text-app-muted">{copy.fields.exitReason}</p>
              <p className="mt-2 text-sm text-app-foreground">
                {latest.exit_reason ? copy.exitReasons[latest.exit_reason] : '—'}
              </p>
            </div>
            {latest.skip_reason ? (
              <div>
                <p className="text-xs text-app-muted">{copy.fields.skipReason}</p>
                <p className="mt-2 text-sm text-app-foreground">
                  {copy.skipReasons[latest.skip_reason]}
                </p>
              </div>
            ) : null}
          </div>
        </CardContent>
      </Card>

      <section>
        <div>
          <h2 className="text-xl font-semibold text-app-foreground">{copy.lineageTitle}</h2>
          <p className="mt-2 text-sm text-app-muted">{copy.lineageDescription}</p>
        </div>

        <div className="relative mt-5 min-h-48" aria-busy={isLoading}>
          {isLoading ? (
            <div className="absolute inset-0 z-20 flex items-center justify-center rounded-2xl bg-app-overlay backdrop-blur-sm">
              <Spinner size="lg" label={copy.lineageLoading} className="text-app-accent" />
            </div>
          ) : null}

          {hasError ? (
            <ErrorState
              title={copy.lineageErrorTitle}
              description={copy.lineageErrorDescription}
              retryLabel={copy.retry}
              onRetry={() => void loadLineage(lineage.offset)}
            />
          ) : (
            <div className="space-y-3">
              {lineage.items.map((occurrence) => (
                <Card key={occurrence.journal_id}>
                  <CardContent className="grid gap-4 pt-6 sm:grid-cols-2 lg:grid-cols-4">
                    <div>
                      <p className="text-xs text-app-muted">{copy.fields.journal}</p>
                      <p
                        dir="ltr"
                        className="mt-2 text-left text-xs font-semibold break-all text-app-foreground"
                      >
                        {occurrence.journal_id}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-app-muted">{copy.fields.recordedAt}</p>
                      <p className="mt-2 text-sm text-app-foreground">
                        {formatDate(occurrence.recorded_at, locale)}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-app-muted">{copy.fields.rank}</p>
                      <p className="mt-2 text-sm text-app-foreground">
                        {formatNumber(occurrence.rank, locale)}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-app-muted">{copy.fields.rankingScore}</p>
                      <p
                        dir="ltr"
                        className="mt-2 text-left text-sm font-semibold text-app-foreground"
                      >
                        {formatDecimal(occurrence.ranking_score, locale)}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-app-muted">{copy.fields.occurrence}</p>
                      <p className="mt-2 text-sm text-app-foreground">
                        {copy.occurrenceTypes[occurrence.occurrence_type]}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-app-muted">{copy.fields.replay}</p>
                      <p className="mt-2 text-sm text-app-foreground">
                        {occurrence.replay_status
                          ? copy.replayStatuses[occurrence.replay_status]
                          : copy.notEvaluated}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-app-muted">{copy.fields.risk}</p>
                      <p className="mt-2 text-sm text-app-foreground">
                        {occurrence.risk_decision
                          ? copy.riskDecisions[occurrence.risk_decision]
                          : copy.notEvaluated}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-app-muted">{copy.fields.skipReason}</p>
                      <p className="mt-2 text-sm text-app-foreground">
                        {occurrence.skip_reason ? copy.skipReasons[occurrence.skip_reason] : '—'}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-app-muted">{copy.fields.positionId}</p>
                      <p
                        dir="ltr"
                        className="mt-2 text-left text-xs font-semibold break-all text-app-foreground"
                      >
                        {occurrence.position_id ?? '—'}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-app-muted">{copy.fields.exitReason}</p>
                      <p className="mt-2 text-sm text-app-foreground">
                        {occurrence.exit_reason ? copy.exitReasons[occurrence.exit_reason] : '—'}
                      </p>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </div>

        {!hasError && lineage.total > 0 ? (
          <div className="mt-4 rounded-2xl border border-app-border bg-app-surface px-5 py-4">
            <Pagination
              total={lineage.total}
              limit={lineage.limit}
              offset={lineage.offset}
              isLoading={isLoading}
              pageLabel={copy.page}
              previousLabel={copy.previous}
              nextLabel={copy.next}
              onOffsetChange={(offset) => void loadLineage(offset)}
            />
          </div>
        ) : null}
      </section>
    </div>
  );
}
