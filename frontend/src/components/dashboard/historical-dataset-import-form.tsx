'use client';

import Link from 'next/link';
import { useMemo, useState } from 'react';

import type { DashboardLocale } from '@/components/dashboard/dashboard-copy';
import { getHistoricalImportCopy } from '@/components/dashboard/historical-import-copy';
import { Badge, Button, Input, Select, SelectOption } from '@/components/ui';
import { importHistoricalDataset, previewHistoricalDatasetImport } from '@/lib/api/client';
import type {
  DatasetSummary,
  DatasetTimeframe,
  HistoricalDatasetImportPreview,
  HistoricalDatasetImportRequest,
  MarketDataConnection,
  MarketDataProviderSummary,
} from '@/lib/api/types';

type HistoricalDatasetImportFormProps = {
  connection: MarketDataConnection;
  locale: DashboardLocale;
  provider: MarketDataProviderSummary | undefined;
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

export default function HistoricalDatasetImportForm({
  connection,
  locale,
  provider,
}: HistoricalDatasetImportFormProps) {
  const copy = getHistoricalImportCopy(locale);
  const availableTimeframes = provider?.supported_timeframes ?? [];
  const marketType = provider?.supported_market_types[0] ?? 'spot';

  const [name, setName] = useState('');
  const [baseAsset, setBaseAsset] = useState('BTC');
  const [quoteAsset, setQuoteAsset] = useState('USDT');
  const [timeframe, setTimeframe] = useState<DatasetTimeframe | ''>(availableTimeframes[0] ?? '');
  const [startTime, setStartTime] = useState('');
  const [endTime, setEndTime] = useState('');
  const [preview, setPreview] = useState<HistoricalDatasetImportPreview | null>(null);
  const [importedDataset, setImportedDataset] = useState<DatasetSummary | null>(null);
  const [isPreviewing, setIsPreviewing] = useState(false);
  const [isImporting, setIsImporting] = useState(false);
  const [hasRequestError, setHasRequestError] = useState(false);

  const hasValidRange = useMemo(() => {
    if (!startTime || !endTime) {
      return false;
    }

    const start = new Date(startTime);
    const end = new Date(endTime);
    return !Number.isNaN(start.getTime()) && !Number.isNaN(end.getTime()) && end > start;
  }, [endTime, startTime]);

  const canPreview = Boolean(
    provider && name.trim() && baseAsset.trim() && quoteAsset.trim() && timeframe && hasValidRange,
  );

  function invalidateResult(): void {
    setPreview(null);
    setImportedDataset(null);
    setHasRequestError(false);
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

  async function handlePreview(): Promise<void> {
    if (!canPreview) {
      return;
    }

    setIsPreviewing(true);
    setHasRequestError(false);
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

    try {
      setImportedDataset(await importHistoricalDataset(connection.connection_id, buildRequest()));
    } catch {
      setImportedDataset(null);
      setHasRequestError(true);
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
