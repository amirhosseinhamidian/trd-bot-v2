'use client';

import Link from 'next/link';
import { useRef, useState } from 'react';

import type { DashboardLocale } from '@/components/dashboard/dashboard-copy';
import { getCandidateCopy } from '@/components/dashboard/candidate-copy';
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
import { getCandidateProjections } from '@/lib/api/client';
import type { CandidateProjectionSummary, Page } from '@/lib/api/types';

const PAGE_SIZE = 12;

type CandidateCatalogProps = {
  initialPage: Page<CandidateProjectionSummary>;
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

export default function CandidateCatalog({ initialPage, locale }: CandidateCatalogProps) {
  const copy = getCandidateCopy(locale);
  const [page, setPage] = useState(initialPage);
  const [isLoading, setIsLoading] = useState(false);
  const [hasError, setHasError] = useState(false);
  const requestSequence = useRef(0);

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
            onRetry={() => void loadCandidates(page.offset)}
          />
        ) : page.items.length === 0 ? (
          <EmptyState title={copy.emptyTitle} description={copy.emptyDescription} />
        ) : (
          <div className="grid gap-4 xl:grid-cols-2">
            {page.items.map((candidate) => (
              <Card key={candidate.candidate_id} className="overflow-hidden">
                <CardHeader className="border-b border-slate-800">
                  <div className="flex flex-wrap items-start justify-between gap-4">
                    <div className="min-w-0">
                      <CardTitle>
                        {candidate.pair.base_asset}/{candidate.pair.quote_asset}
                      </CardTitle>

                      <CardDescription
                        dir="ltr"
                        title={candidate.candidate_id}
                        className="mt-2 truncate text-left font-mono text-xs"
                      >
                        {candidate.candidate_id}
                      </CardDescription>
                    </div>

                    <div className="flex flex-wrap gap-2">
                      <Badge variant={candidate.selected ? 'success' : 'info'}>
                        {candidate.selected ? copy.selected : copy.notSelected}
                      </Badge>

                      <Badge variant="info">{copy.statuses[candidate.status]}</Badge>
                      <Badge variant="warning">{copy.actions[candidate.action]}</Badge>
                    </div>
                  </div>
                </CardHeader>

                <CardContent className="space-y-6 pt-6">
                  <dl className="grid gap-3 sm:grid-cols-3">
                    <div className="rounded-xl border border-slate-800 bg-slate-950/50 p-3">
                      <dt className="text-xs text-slate-500">{copy.fields.confidence}</dt>
                      <dd dir="ltr" className="mt-2 text-left font-mono text-sm text-slate-200">
                        {formatDecimal(candidate.confidence, locale)}
                      </dd>
                    </div>

                    <div className="rounded-xl border border-slate-800 bg-slate-950/50 p-3">
                      <dt className="text-xs text-slate-500">{copy.fields.signalScore}</dt>
                      <dd dir="ltr" className="mt-2 text-left font-mono text-sm text-slate-200">
                        {formatDecimal(candidate.signal_score, locale)}
                      </dd>
                    </div>

                    <div className="rounded-xl border border-slate-800 bg-slate-950/50 p-3">
                      <dt className="text-xs text-slate-500">{copy.fields.occurrences}</dt>
                      <dd className="mt-2 text-sm text-slate-200">
                        {formatNumber(candidate.occurrence_count, locale)}
                      </dd>
                    </div>
                  </dl>

                  <dl className="grid gap-4 sm:grid-cols-2">
                    <div>
                      <dt className="text-xs text-slate-500">{copy.fields.strategy}</dt>
                      <dd className="mt-1 text-sm text-slate-200">
                        {candidate.strategy_name} · {candidate.strategy_version}
                      </dd>
                    </div>

                    <div>
                      <dt className="text-xs text-slate-500">{copy.fields.timeframe}</dt>
                      <dd className="mt-1 text-sm text-slate-200">{candidate.timeframe}</dd>
                    </div>

                    <div>
                      <dt className="text-xs text-slate-500">{copy.fields.replay}</dt>
                      <dd className="mt-1 text-sm text-slate-200">
                        {copy.replayStatuses[candidate.latest_replay_status]}
                      </dd>
                    </div>

                    <div>
                      <dt className="text-xs text-slate-500">{copy.fields.risk}</dt>
                      <dd className="mt-1 text-sm text-slate-200">
                        {copy.riskDecisions[candidate.latest_risk_decision]}
                      </dd>
                    </div>
                  </dl>

                  <div className="grid gap-3 border-t border-slate-800 pt-4 sm:grid-cols-2">
                    <div>
                      <p className="text-xs text-slate-500">{copy.fields.recordedAt}</p>
                      <p className="mt-2 text-xs text-slate-400">
                        {formatDate(candidate.latest_recorded_at, locale)}
                      </p>
                    </div>

                    <div>
                      <p className="text-xs text-slate-500">{copy.fields.exitReason}</p>
                      <p className="mt-2 text-xs text-slate-400">
                        {candidate.exit_reason ? copy.exitReasons[candidate.exit_reason] : '—'}
                      </p>
                    </div>
                  </div>

                  <div className="flex border-t border-slate-800 pt-4">
                    <Link
                      href={`/${locale}/candidates/${encodeURIComponent(candidate.candidate_id)}`}
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
            onOffsetChange={(offset) => void loadCandidates(offset)}
          />
        </section>
      ) : null}
    </div>
  );
}
