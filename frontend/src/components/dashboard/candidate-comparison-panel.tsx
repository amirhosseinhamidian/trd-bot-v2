'use client';

import Link from 'next/link';
import { useState } from 'react';

import { getCandidateComparisonCopy } from '@/components/dashboard/candidate-comparison-copy';
import { getCandidateCopy } from '@/components/dashboard/candidate-copy';
import { CandidateRankingBreakdown } from '@/components/dashboard/candidate-ranking-breakdown';
import type { DashboardLocale } from '@/components/dashboard/dashboard-copy';
import {
  Badge,
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui';
import { compareCandidates } from '@/lib/api/client';
import type { CandidateComparisonResult, CandidateProjectionSummary } from '@/lib/api/types';

type CandidateComparisonPanelProps = {
  locale: DashboardLocale;
  onClearSelection: () => void;
  selectedCandidates: CandidateProjectionSummary[];
};

function formatNumber(value: number, locale: DashboardLocale): string {
  return new Intl.NumberFormat(locale === 'fa' ? 'fa-IR' : 'en-US').format(value);
}

function formatDecimal(value: string, locale: DashboardLocale): string {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) {
    return value;
  }
  return new Intl.NumberFormat(locale === 'fa' ? 'fa-IR' : 'en-US', {
    maximumFractionDigits: 6,
  }).format(numeric);
}

export default function CandidateComparisonPanel({
  locale,
  onClearSelection,
  selectedCandidates,
}: CandidateComparisonPanelProps) {
  const copy = getCandidateComparisonCopy(locale);
  const candidateCopy = getCandidateCopy(locale);
  const [result, setResult] = useState<CandidateComparisonResult | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [hasError, setHasError] = useState(false);
  const canCompare = selectedCandidates.length >= 2 && selectedCandidates.length <= 4;

  async function runComparison(): Promise<void> {
    if (!canCompare) {
      return;
    }

    setIsLoading(true);
    setHasError(false);
    setResult(null);

    try {
      setResult(
        await compareCandidates(selectedCandidates.map((candidate) => candidate.candidate_id)),
      );
    } catch {
      setHasError(true);
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <Card className="border-app-accent-border">
      <CardHeader>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <CardTitle>{copy.title}</CardTitle>
            <CardDescription className="mt-1.5">{copy.description}</CardDescription>
          </div>
          <Badge variant="info">
            {copy.selectedCount}: {formatNumber(selectedCandidates.length, locale)}
          </Badge>
        </div>
      </CardHeader>

      <CardContent className="space-y-5">
        <p className="text-sm text-app-muted">{copy.selectionHint}</p>

        <div className="flex flex-wrap gap-3">
          <Button
            disabled={!canCompare}
            isLoading={isLoading}
            loadingText={copy.comparing}
            onClick={() => void runComparison()}
          >
            {copy.compare}
          </Button>
          <Button
            variant="secondary"
            disabled={isLoading || selectedCandidates.length === 0}
            onClick={onClearSelection}
          >
            {copy.clearSelection}
          </Button>
        </div>

        {!canCompare ? (
          <p className="text-sm text-app-warning">{copy.insufficientSelection}</p>
        ) : null}

        {hasError ? (
          <div
            role="alert"
            className="rounded-xl border border-app-danger-border bg-app-danger-soft p-4"
          >
            <p className="text-sm text-app-danger">{copy.error}</p>
            <Button
              className="mt-4"
              size="sm"
              variant="danger"
              onClick={() => void runComparison()}
            >
              {copy.retry}
            </Button>
          </div>
        ) : null}

        {result ? (
          <div className="space-y-4 border-t border-app-border pt-5">
            <div>
              <h3 className="font-semibold text-app-foreground">{copy.resultTitle}</h3>
              <p className="mt-1 text-sm text-app-muted">{copy.resultDescription}</p>
              <p dir="ltr" className="mt-2 text-left text-xs font-semibold text-app-muted">
                {result.journal_id}
              </p>
            </div>

            <div className="grid gap-4 md:grid-cols-2 2xl:grid-cols-4">
              {result.entries.map(({ comparison_position, occurrence }) => (
                <Card key={occurrence.candidate.candidate_id} className="bg-app-surface-muted">
                  <CardHeader>
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <CardTitle className="truncate text-base">
                          {copy.candidate} {formatNumber(comparison_position, locale)}
                        </CardTitle>
                        <CardDescription dir="ltr" className="mt-2 truncate text-left text-xs">
                          {occurrence.candidate.candidate_id}
                        </CardDescription>
                      </div>
                      <Badge variant={occurrence.selected ? 'success' : 'info'}>
                        #{formatNumber(occurrence.rank, locale)} ·{' '}
                        {occurrence.selected ? candidateCopy.selected : candidateCopy.notSelected}
                      </Badge>
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <dl className="grid grid-cols-2 gap-3 text-sm">
                      <div>
                        <dt className="text-xs text-app-muted">{copy.rank}</dt>
                        <dd className="mt-1 font-semibold text-app-foreground">
                          {formatNumber(occurrence.rank, locale)}
                        </dd>
                      </div>
                      <div>
                        <dt className="text-xs text-app-muted">{copy.score}</dt>
                        <dd dir="ltr" className="mt-1 text-left font-semibold text-app-foreground">
                          {formatDecimal(occurrence.ranking_score, locale)}
                        </dd>
                      </div>
                    </dl>

                    <div className="flex items-center justify-between gap-3 rounded-lg border border-app-border bg-app-surface p-3">
                      <span className="text-xs text-app-muted">{candidateCopy.fields.risk}</span>
                      <Badge
                        variant={
                          occurrence.risk_decision === 'rejected'
                            ? 'danger'
                            : occurrence.risk_decision === 'approved'
                              ? 'success'
                              : 'warning'
                        }
                      >
                        {occurrence.risk_decision
                          ? candidateCopy.riskDecisions[occurrence.risk_decision]
                          : candidateCopy.notEvaluated}
                      </Badge>
                    </div>

                    <CandidateRankingBreakdown
                      evidence={occurrence.decision_evidence}
                      locale={locale}
                    />

                    <Link
                      href={`/${locale}/candidates/${encodeURIComponent(
                        occurrence.candidate.candidate_id,
                      )}`}
                      className="inline-flex text-sm font-semibold text-app-accent hover:opacity-80"
                    >
                      {occurrence.candidate.candidate_id}
                    </Link>
                  </CardContent>
                </Card>
              ))}
            </div>

            <p className="rounded-xl border border-app-warning-border bg-app-warning-soft p-4 text-sm text-app-warning">
              {copy.historicalOnly}
            </p>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
