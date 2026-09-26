'use client';

import { useState } from 'react';

import type { ExperimentDetailLocale } from '@/components/dashboard/experiment-detail-copy';
import { getExperimentReplayCopy } from '@/components/dashboard/experiment-replay-copy';
import {
  Badge,
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui';
import { verifyExperimentReplay } from '@/lib/api/client';
import type {
  ExperimentReplayStatus,
  ExperimentReplayVerification,
} from '@/lib/api/types';

type ExperimentReplayPanelProps = {
  experimentId: string;
  locale: ExperimentDetailLocale;
};

function statusVariant(status: ExperimentReplayStatus): 'success' | 'danger' | 'warning' {
  if (status === 'verified') {
    return 'success';
  }
  if (status === 'mismatch') {
    return 'danger';
  }
  return 'warning';
}

function formatDate(value: string, locale: ExperimentDetailLocale): string {
  return new Intl.DateTimeFormat(locale === 'fa' ? 'fa-IR' : 'en-US', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value));
}

export function ExperimentReplayPanel({ experimentId, locale }: ExperimentReplayPanelProps) {
  const copy = getExperimentReplayCopy(locale);
  const [verification, setVerification] = useState<ExperimentReplayVerification | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [hasError, setHasError] = useState(false);

  async function runVerification(): Promise<void> {
    setIsLoading(true);
    setHasError(false);
    try {
      setVerification(await verifyExperimentReplay(experimentId));
    } catch {
      setVerification(null);
      setHasError(true);
    } finally {
      setIsLoading(false);
    }
  }

  const values = verification
    ? [
        [copy.checkedAt, formatDate(verification.checked_at, locale)],
        [copy.recordedResult, verification.recorded_result_checksum],
        [copy.replayedResult, verification.replayed_result_checksum ?? copy.unavailable],
        [
          copy.recordedStrategy,
          verification.recorded_strategy_fingerprint ?? copy.unavailable,
        ],
        [copy.currentStrategy, verification.current_strategy_fingerprint ?? copy.unavailable],
      ]
    : [];

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <CardTitle>{copy.title}</CardTitle>
            <CardDescription>{copy.description}</CardDescription>
          </div>
          {verification ? (
            <Badge variant={statusVariant(verification.status)}>
              {copy.statusLabel}: {copy.statuses[verification.status]}
            </Badge>
          ) : null}
        </div>
      </CardHeader>

      <CardContent className="space-y-5">
        <Button
          type="button"
          variant="secondary"
          isLoading={isLoading}
          loadingText={copy.running}
          onClick={() => void runVerification()}
        >
          {copy.run}
        </Button>

        {hasError ? <p className="text-sm text-red-500">{copy.requestError}</p> : null}

        {!verification && !hasError ? (
          <p className="text-sm leading-7 text-app-muted">{copy.notRun}</p>
        ) : null}

        {verification ? (
          <div className="space-y-4">
            <p className="rounded-xl border border-app-border bg-app-surface-muted p-4 text-sm leading-7 text-app-foreground">
              {copy.reasons[verification.code]}
            </p>

            <dl className="grid gap-3 md:grid-cols-2">
              {values.map(([label, value]) => (
                <div key={label} className="rounded-xl border border-app-border p-4">
                  <dt className="text-xs text-app-muted">{label}</dt>
                  <dd dir="ltr" className="mt-2 text-left text-xs break-all text-app-foreground">
                    {value}
                  </dd>
                </div>
              ))}
            </dl>

            {verification.mismatch_fields.length > 0 ? (
              <div className="rounded-xl border border-red-500/20 bg-red-500/10 p-4">
                <p className="text-xs text-red-500">{copy.mismatchFields}</p>
                <p dir="ltr" className="mt-2 text-left text-sm text-red-500">
                  {verification.mismatch_fields.join(', ')}
                </p>
              </div>
            ) : null}
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
