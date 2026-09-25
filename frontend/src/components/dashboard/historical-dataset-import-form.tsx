'use client';

import Link from 'next/link';
import { useMemo, useState } from 'react';

import type { DashboardLocale } from '@/components/dashboard/dashboard-copy';
import { getHistoricalImportCopy } from '@/components/dashboard/historical-import-copy';
import { Badge, Button, Input, Select, SelectOption } from '@/components/ui';
import {
  ApiRequestError,
  importHistoricalDataset,
  previewHistoricalDatasetImport,
} from '@/lib/api/client';
import type {
  DatasetSummary,
  DatasetTimeframe,
  HistoricalDatasetCommitRequest,
  HistoricalDatasetImportPreview,
  HistoricalDatasetImportRequest,
  MarketDataConnection,
  MarketDataProviderSummary,
} from '@/lib/api/types';

type HistoricalDatasetImportFormProps = {
  connection: MarketDataConnection;
  locale: DashboardLocale;
  onImported?: () => void;
  provider: MarketDataProviderSummary | undefined;
};

const TIMEFRAME_DURATION_MS: Record<DatasetTimeframe, number> = {
  '15m': 15 * 60 * 1000,
  '1h': 60 * 60 * 1000,
  '4h': 4 * 60 * 60 * 1000,
  '1d': 24 * 60 * 60 * 1000,
};

function formatDate(value: string, locale: DashboardLocale): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat(locale === 'fa' ? 'fa-IR' : 'en-US', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date);
}

function toIso(value: string): string {
  return new Date(value).toISOString();
}

function formatCandleLimit(value: number, locale: DashboardLocale): string {
  return new Intl.NumberFormat(locale === 'fa' ? 'fa-IR' : 'en-US').format(value);
}

function formatPercent(value: number, locale: DashboardLocale): string {
  const formatted = new Intl.NumberFormat(locale === 'fa' ? 'fa-IR' : 'en-US', {
    maximumFractionDigits: 2,
  }).format(value);
  return `${formatted}${locale === 'fa' ? '٪' : '%'}`;
}

function isPreviewMismatchError(error: unknown): boolean {
  if (!(error instanceof ApiRequestError) || error.status !== 409) {
    return false;
  }

  const payload = error.payload;
  return (
    typeof payload === 'object' &&
    payload !== null &&
    'detail' in payload &&
    payload.detail === 'provider data changed after preview; run preview again before importing'
  );
}

export default function HistoricalDatasetImportForm({
  connection,
  locale,
  onImported,
  provider,
}: HistoricalDatasetImportFormProps) {
  const copy = getHistoricalImportCopy(locale);
  const availableTimeframes = provider?.supported_timeframes ?? [];
  const marketType = provider?.supported_market_types[0] ?? 'spot';

  const [name, setName] = useState('');
  const [baseAsset, setBaseAsset] = useState(provider?.default_pair.base_asset ?? 'BTC');
  const [quoteAsset, setQuoteAsset] = useState(provider?.default_pair.quote_asset ?? 'USDT');
  const [timeframe, setTimeframe] = useState<DatasetTimeframe | ''>(availableTimeframes[0] ?? '');
  const [startTime, setStartTime] = useState('');
  const [endTime, setEndTime] = useState('');
  const [preview, setPreview] = useState<HistoricalDatasetImportPreview | null>(null);
  const [importedDataset, setImportedDataset] = useState<DatasetSummary | null>(null);
  const [isPreviewing, setIsPreviewing] = useState(false);
  const [isImporting, setIsImporting] = useState(false);
  const [hasRequestError, setHasRequestError] = useState(false);
  const [hasPreviewMismatch, setHasPreviewMismatch] = useState(false);

  const hasValidRange = useMemo(() => {
    if (!startTime || !endTime) {
      return false;
    }

    const start = new Date(startTime);
    const end = new Date(endTime);
    return !Number.isNaN(start.getTime()) && !Number.isNaN(end.getTime()) && end > start;
  }, [endTime, startTime]);

  const exceedsProviderWindow = useMemo(() => {
    if (!provider?.max_closed_candles || !timeframe || !startTime) {
      return false;
    }

    const start = new Date(startTime);
    if (Number.isNaN(start.getTime())) {
      return false;
    }

    const earliestSupportedStart =
      Date.now() - TIMEFRAME_DURATION_MS[timeframe] * provider.max_closed_candles;
    return start.getTime() < earliestSupportedStart;
  }, [provider?.max_closed_candles, startTime, timeframe]);

  const canPreview = Boolean(
    provider &&
    name.trim() &&
    baseAsset.trim() &&
    quoteAsset.trim() &&
    timeframe &&
    hasValidRange &&
    !exceedsProviderWindow,
  );

  function invalidateResult(): void {
    setPreview(null);
    setImportedDataset(null);
    setHasRequestError(false);
    setHasPreviewMismatch(false);
  }

  function buildRequest(): HistoricalDatasetImportRequest {
    if (!timeframe) {
      throw new Error('timeframe is required');
    }

    return {
      name: name.trim(),
      pair: {
        base_asset: baseAsset.trim().toUpperCase(),
        quote_asset: quoteAsset.trim().toUpperCase(),
        market_type: marketType,
      },
      timeframe,
      start_time: toIso(startTime),
      end_time: toIso(endTime),
    };
  }

  function buildCommitRequest(): HistoricalDatasetCommitRequest {
    if (!preview) {
      throw new Error('preview is required');
    }

    return {
      ...buildRequest(),
      preview_checksum: preview.preview_checksum,
    };
  }

  async function handlePreview(): Promise<void> {
    if (!canPreview) {
      return;
    }

    setIsPreviewing(true);
    setHasRequestError(false);
    setHasPreviewMismatch(false);
    setImportedDataset(null);

    try {
      setPreview(await previewHistoricalDatasetImport(connection.connection_id, buildRequest()));
    } catch {
      setPreview(null);
      setHasRequestError(true);
    } finally {
      setIsPreviewing(false);
    }
  }

  async function handleImport(): Promise<void> {
    if (!preview?.ready_to_import || !canPreview) {
      return;
    }

    setIsImporting(true);
    setHasRequestError(false);
    setHasPreviewMismatch(false);

    try {
      const dataset = await importHistoricalDataset(connection.connection_id, buildCommitRequest());
      setImportedDataset(dataset);
      onImported?.();
    } catch (error) {
      setImportedDataset(null);
      if (isPreviewMismatchError(error)) {
        setPreview(null);
        setHasPreviewMismatch(true);
      } else {
        setHasRequestError(true);
      }
    } finally {
      setIsImporting(false);
    }
  }

  if (!provider) {
    return (
      <p className="mt-5 rounded-xl border border-app-warning-border bg-app-warning-soft p-3 text-sm text-app-warning">
        {copy.providerMetadataMissing}
      </p>
    );
  }

  return (
    <div className="mt-6 border-t border-app-border pt-6">
      <div>
        <h3 className="text-base font-semibold text-app-foreground">{copy.title}</h3>
        <p className="mt-1 text-sm leading-6 text-app-muted">{copy.description}</p>
      </div>

      <p
        className={`mt-4 rounded-xl border p-3 text-sm leading-6 ${
          provider.access_mode === 'direct'
            ? 'border-emerald-500/20 bg-emerald-500/10 text-emerald-600'
            : 'border-app-warning-border bg-app-warning-soft text-app-warning'
        }`}
      >
        {provider.access_mode === 'direct' ? copy.directAccessNotice : copy.vpnAccessNotice}
      </p>

      {provider.max_closed_candles !== null ? (
        <p className="mt-3 rounded-xl border border-app-warning-border bg-app-warning-soft p-3 text-sm leading-6 text-app-warning">
          {copy.recentWindowNotice.replace(
            '{count}',
            formatCandleLimit(provider.max_closed_candles, locale),
          )}
        </p>
      ) : null}

      <div className="mt-5 grid gap-4 md:grid-cols-2">
        <Input
          label={copy.datasetName}
          placeholder={copy.datasetNamePlaceholder}
          value={name}
          maxLength={100}
          disabled={isPreviewing || isImporting}
          onChange={(event) => {
            setName(event.target.value);
            invalidateResult();
          }}
        />
        <div className="grid grid-cols-2 gap-3">
          <Input
            label={copy.baseAsset}
            value={baseAsset}
            maxLength={15}
            disabled={isPreviewing || isImporting}
            onChange={(event) => {
              setBaseAsset(event.target.value);
              invalidateResult();
            }}
          />
          <Input
            label={copy.quoteAsset}
            value={quoteAsset}
            maxLength={15}
            disabled={isPreviewing || isImporting}
            onChange={(event) => {
              setQuoteAsset(event.target.value);
              invalidateResult();
            }}
          />
        </div>
        <Select
          label={copy.timeframe}
          value={timeframe}
          disabled={isPreviewing || isImporting || availableTimeframes.length === 0}
          onValueChange={(value) => {
            setTimeframe(value as DatasetTimeframe);
            invalidateResult();
          }}
        >
          {availableTimeframes.map((value) => (
            <SelectOption key={value} value={value}>
              {value}
            </SelectOption>
          ))}
        </Select>
        <Input label={copy.marketType} value={marketType} disabled />
        <Input
          label={copy.startTime}
          type="datetime-local"
          value={startTime}
          error={
            exceedsProviderWindow && provider.max_closed_candles !== null
              ? copy.recentWindowError.replace(
                  '{count}',
                  formatCandleLimit(provider.max_closed_candles, locale),
                )
              : undefined
          }
          disabled={isPreviewing || isImporting}
          onChange={(event) => {
            setStartTime(event.target.value);
            invalidateResult();
          }}
        />
        <Input
          label={copy.endTime}
          type="datetime-local"
          value={endTime}
          error={startTime && endTime && !hasValidRange ? copy.invalidRange : undefined}
          disabled={isPreviewing || isImporting}
          onChange={(event) => {
            setEndTime(event.target.value);
            invalidateResult();
          }}
        />
      </div>

      <div className="mt-5 flex flex-wrap gap-2">
        <Button
          variant="secondary"
          isLoading={isPreviewing}
          loadingText={copy.previewing}
          disabled={!canPreview || isImporting}
          onClick={() => void handlePreview()}
        >
          {copy.preview}
        </Button>
        <Button
          isLoading={isImporting}
          loadingText={copy.importing}
          disabled={!preview?.ready_to_import || isPreviewing}
          onClick={() => void handleImport()}
        >
          {copy.importDataset}
        </Button>
      </div>

      {hasRequestError ? (
        <p
          role="alert"
          className="mt-4 rounded-xl border border-red-500/20 bg-red-500/10 p-3 text-sm text-red-500"
        >
          {copy.requestError}
        </p>
      ) : null}

      {hasPreviewMismatch ? (
        <p
          role="alert"
          className="mt-4 rounded-xl border border-app-warning-border bg-app-warning-soft p-3 text-sm text-app-warning"
        >
          {copy.previewMismatchError}
        </p>
      ) : null}

      {preview ? (
        <section className="mt-5 rounded-2xl border border-app-border bg-app-surface-muted p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h4 className="font-semibold text-app-foreground">{copy.previewTitle}</h4>
            <Badge variant={preview.ready_to_import ? 'success' : 'warning'}>
              {preview.ready_to_import ? copy.ready : copy.notReady}
            </Badge>
          </div>

          <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2">
            <div>
              <dt className="text-app-muted">{copy.candles}</dt>
              <dd className="mt-1 font-semibold text-app-foreground">{preview.candle_count}</dd>
            </div>
            <div>
              <dt className="text-app-muted">{copy.requestedRange}</dt>
              <dd className="mt-1 text-app-foreground">
                {formatDate(preview.requested_start_time, locale)} —{' '}
                {formatDate(preview.requested_end_time, locale)}
              </dd>
            </div>
            <div className="sm:col-span-2">
              <dt className="text-app-muted">{copy.availableRange}</dt>
              <dd className="mt-1 text-app-foreground">
                {preview.first_open_time && preview.last_close_time
                  ? `${formatDate(preview.first_open_time, locale)} — ${formatDate(
                      preview.last_close_time,
                      locale,
                    )}`
                  : copy.noCoverage}
              </dd>
            </div>
          </dl>

          {preview.quality_report.score && preview.quality_report.acceptance ? (
            <section className="mt-4 rounded-xl border border-app-border bg-app-surface p-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <h5 className="text-sm font-semibold text-app-foreground">{copy.scoreTitle}</h5>
                <Badge variant={preview.quality_report.acceptance.accepted ? 'success' : 'warning'}>
                  {preview.quality_report.acceptance.accepted
                    ? copy.policyPassed
                    : copy.policyFailed}
                </Badge>
              </div>
              <dl className="mt-3 grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-3">
                <div>
                  <dt className="text-app-muted">{copy.scorePercent}</dt>
                  <dd className="mt-1 font-semibold text-app-foreground">
                    {formatPercent(preview.quality_report.score.score_percent, locale)}
                  </dd>
                </div>
                <div>
                  <dt className="text-app-muted">{copy.coverageComponent}</dt>
                  <dd className="mt-1 font-semibold text-app-foreground">
                    {formatPercent(preview.quality_report.score.coverage_percent, locale)}
                  </dd>
                </div>
                <div>
                  <dt className="text-app-muted">{copy.integrityComponent}</dt>
                  <dd className="mt-1 font-semibold text-app-foreground">
                    {formatPercent(preview.quality_report.score.integrity_percent, locale)}
                  </dd>
                </div>
                <div>
                  <dt className="text-app-muted">{copy.scoreVersion}</dt>
                  <dd dir="ltr" className="mt-1 text-left font-semibold text-app-foreground">
                    {preview.quality_report.score.score_version}
                  </dd>
                </div>
                <div>
                  <dt className="text-app-muted">{copy.policyVersion}</dt>
                  <dd dir="ltr" className="mt-1 text-left font-semibold text-app-foreground">
                    {preview.quality_report.acceptance.policy_version}
                  </dd>
                </div>
              </dl>
            </section>
          ) : null}

          {preview.quality_report.coverage ? (
            <section className="mt-4 rounded-xl border border-app-border bg-app-surface p-4">
              <h5 className="text-sm font-semibold text-app-foreground">{copy.coverageTitle}</h5>
              <dl className="mt-3 grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-4">
                <div>
                  <dt className="text-app-muted">{copy.expectedCandles}</dt>
                  <dd className="mt-1 font-semibold text-app-foreground">
                    {formatCandleLimit(preview.quality_report.coverage.expected_candles, locale)}
                  </dd>
                </div>
                <div>
                  <dt className="text-app-muted">{copy.receivedCandles}</dt>
                  <dd className="mt-1 font-semibold text-app-foreground">
                    {formatCandleLimit(preview.quality_report.coverage.received_candles, locale)}
                  </dd>
                </div>
                <div>
                  <dt className="text-app-muted">{copy.missingCandles}</dt>
                  <dd className="mt-1 font-semibold text-app-foreground">
                    {formatCandleLimit(preview.quality_report.coverage.missing_candles, locale)}
                  </dd>
                </div>
                <div>
                  <dt className="text-app-muted">{copy.coveragePercent}</dt>
                  <dd className="mt-1 font-semibold text-app-foreground">
                    {formatPercent(preview.quality_report.coverage.coverage_percent, locale)}
                  </dd>
                </div>
              </dl>
              <div className="mt-3 border-t border-app-border pt-3">
                <p className="text-xs text-app-muted">{copy.previewChecksum}</p>
                <p
                  dir="ltr"
                  title={preview.preview_checksum}
                  className="mt-1 truncate text-left font-mono text-xs text-app-foreground"
                >
                  {preview.preview_checksum}
                </p>
              </div>
            </section>
          ) : null}

          <div className="mt-4 border-t border-app-border pt-4">
            <h5 className="text-sm font-semibold text-app-foreground">{copy.qualityTitle}</h5>
            {preview.quality_report.issues.length === 0 ? (
              <p className="mt-2 text-sm text-app-muted">{copy.qualityPassed}</p>
            ) : (
              <div className="mt-3">
                <p className="text-sm font-medium text-app-warning">{copy.qualityIssues}</p>
                <ul className="mt-2 space-y-2">
                  {preview.quality_report.issues.map((issue, index) => (
                    <li
                      key={`${issue.code}-${issue.timestamp ?? 'none'}-${index}`}
                      className="rounded-xl border border-app-warning-border bg-app-warning-soft p-3 text-sm text-app-warning"
                    >
                      <span className="font-semibold">{copy.issueLabels[issue.code]}: </span>
                      {issue.message}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </section>
      ) : null}

      {importedDataset ? (
        <section className="mt-5 rounded-2xl border border-emerald-500/20 bg-emerald-500/10 p-4">
          <h4 className="font-semibold text-emerald-500">{copy.importedTitle}</h4>
          <p dir="ltr" className="mt-2 text-left text-sm break-all text-app-foreground">
            {importedDataset.dataset_id}
          </p>
          <Link
            href={`/${locale}/datasets/${encodeURIComponent(importedDataset.dataset_id)}`}
            className="mt-3 inline-flex min-h-10 items-center justify-center rounded-xl border border-app-border bg-app-surface px-4 py-2.5 text-sm font-semibold text-app-foreground transition hover:border-app-accent-border hover:text-app-accent focus-visible:ring-2 focus-visible:ring-app-accent focus-visible:ring-offset-2 focus-visible:ring-offset-app-background focus-visible:outline-none"
          >
            {copy.viewDataset}
          </Link>
        </section>
      ) : null}
    </div>
  );
}
