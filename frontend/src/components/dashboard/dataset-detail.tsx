'use client';

import Link from 'next/link';
import { useRef, useState } from 'react';

import type { DashboardLocale } from '@/components/dashboard/dashboard-copy';
import { getDatasetDetailCopy } from '@/components/dashboard/dataset-detail-copy';
import DatasetVersionHistory from '@/components/dashboard/dataset-version-history';
import {
  Badge,
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  EmptyState,
  Pagination,
  Spinner,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui';
import { getDatasetCandles } from '@/lib/api/client';
import type { DatasetDetailSummary, OHLCVCandle, Page } from '@/lib/api/types';

const CANDLES_PER_PAGE = 25;

type DatasetDetailProps = {
  dataset: DatasetDetailSummary;
  initialCandlesPage: Page<OHLCVCandle>;
  locale: DashboardLocale;
};

function formatDate(value: string, locale: DashboardLocale): string {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat(locale === 'fa' ? 'fa-IR' : 'en-US', {
    dateStyle: 'medium',
    timeStyle: 'medium',
  }).format(date);
}

function formatNumber(value: number, locale: DashboardLocale): string {
  return new Intl.NumberFormat(locale === 'fa' ? 'fa-IR' : 'en-US').format(value);
}

function formatPercent(value: number, locale: DashboardLocale): string {
  const formatted = new Intl.NumberFormat(locale === 'fa' ? 'fa-IR' : 'en-US', {
    maximumFractionDigits: 2,
  }).format(value);
  return `${formatted}${locale === 'fa' ? '٪' : '%'}`;
}

export default function DatasetDetail({ dataset, initialCandlesPage, locale }: DatasetDetailProps) {
  const copy = getDatasetDetailCopy(locale);

  const [candlesPage, setCandlesPage] = useState(initialCandlesPage);
  const [isLoading, setIsLoading] = useState(false);
  const [hasError, setHasError] = useState(false);

  const requestSequence = useRef(0);

  async function loadCandles(offset: number): Promise<void> {
    const requestId = ++requestSequence.current;

    setIsLoading(true);
    setHasError(false);

    try {
      const result = await getDatasetCandles(dataset.dataset_id, {
        limit: CANDLES_PER_PAGE,
        offset,
      });

      if (requestId === requestSequence.current) {
        setCandlesPage(result);
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

  const qualityIssues = dataset.quality_report?.issues ?? [];
  const qualityStatus =
    dataset.quality_report === null
      ? 'notRecorded'
      : (dataset.quality_report.acceptance?.accepted ?? qualityIssues.length === 0)
        ? 'passed'
        : 'issues';

  const metadata = [
    {
      label: copy.metadata.datasetId,
      value: dataset.dataset_id,
      ltr: true,
    },
    {
      label: copy.metadata.schemaVersion,
      value: formatNumber(dataset.schema_version, locale),
      ltr: false,
    },
    {
      label: copy.metadata.source,
      value: dataset.source,
      ltr: false,
    },
    {
      label: copy.metadata.pair,
      value: `${dataset.pair.base_asset}/${dataset.pair.quote_asset}`,
      ltr: true,
    },
    {
      label: copy.metadata.marketType,
      value: dataset.pair.market_type,
      ltr: false,
    },
    {
      label: copy.metadata.timeframe,
      value: dataset.timeframe,
      ltr: true,
    },
    {
      label: copy.metadata.candleCount,
      value: formatNumber(dataset.candle_count, locale),
      ltr: false,
    },
    {
      label: copy.metadata.createdAt,
      value: formatDate(dataset.created_at, locale),
      ltr: false,
    },
  ];

  return (
    <div className="space-y-8">
      <section>
        <Link
          href={`/${locale}/datasets`}
          className="inline-flex items-center gap-2 rounded-sm text-sm text-app-muted transition hover:text-app-accent focus-visible:ring-2 focus-visible:ring-app-accent focus-visible:ring-offset-2 focus-visible:ring-offset-app-background focus-visible:outline-none"
        >
          <span aria-hidden="true">{locale === 'fa' ? '→' : '←'}</span>
          {copy.back}
        </Link>

        <div className="mt-6 flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0">
            <p className="text-xs font-semibold tracking-[0.25em] text-app-accent uppercase">
              {copy.eyebrow}
            </p>

            <h1 className="mt-3 truncate text-3xl font-bold tracking-tight text-app-foreground sm:text-4xl">
              {dataset.name}
            </h1>
          </div>

          <div className="flex flex-wrap gap-2">
            <Badge variant="info">
              {dataset.pair.base_asset}/{dataset.pair.quote_asset}
            </Badge>

            <Badge variant="neutral">{dataset.timeframe}</Badge>
          </div>
        </div>
      </section>

      <Card>
        <CardHeader>
          <CardTitle>{copy.metadata.title}</CardTitle>
          <CardDescription>{copy.metadata.description}</CardDescription>
        </CardHeader>

        <CardContent>
          <dl className="grid gap-5 md:grid-cols-2 xl:grid-cols-4">
            {metadata.map((item) => (
              <div
                key={item.label}
                className="rounded-xl border border-app-border bg-app-surface-muted p-4"
              >
                <dt className="text-xs text-app-muted">{item.label}</dt>

                <dd
                  dir={item.ltr ? 'ltr' : undefined}
                  className={
                    item.ltr
                      ? 'mt-2 truncate text-left text-sm font-semibold text-app-foreground'
                      : 'mt-2 truncate text-sm font-medium text-app-foreground'
                  }
                  title={item.value}
                >
                  {item.value}
                </dd>
              </div>
            ))}
          </dl>

          <div className="mt-5 grid gap-5 md:grid-cols-2">
            <div className="rounded-xl border border-app-border bg-app-surface-muted p-4">
              <p className="text-xs text-app-muted">{copy.metadata.dataPeriod}</p>

              <p className="mt-2 text-sm leading-7 text-app-foreground">
                {formatDate(dataset.start_time, locale)}

                <span className="mx-2 text-app-subtle">—</span>

                {formatDate(dataset.end_time, locale)}
              </p>
            </div>

            <div className="rounded-xl border border-app-border bg-app-surface-muted p-4">
              <p className="text-xs text-app-muted">{copy.metadata.checksum}</p>

              <p
                dir="ltr"
                title={dataset.checksum}
                className="mt-2 truncate text-left text-xs font-semibold text-app-muted"
              >
                {dataset.checksum}
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <CardTitle>{copy.provenance.title}</CardTitle>
            <CardDescription>{copy.provenance.description}</CardDescription>
          </div>

          <Badge variant={dataset.provenance.kind === 'market_data_import' ? 'info' : 'neutral'}>
            {copy.provenance.kinds[dataset.provenance.kind]}
          </Badge>
        </CardHeader>

        <CardContent>
          <p className="text-sm leading-7 text-app-muted">
            {copy.provenance.kindDescriptions[dataset.provenance.kind]}
          </p>

          {dataset.provenance.kind === 'market_data_import' ? (
            <dl className="mt-5 grid gap-4 md:grid-cols-2">
              <div className="rounded-xl border border-app-border bg-app-surface-muted p-4">
                <dt className="text-xs text-app-muted">{copy.provenance.connectionId}</dt>
                <dd
                  dir="ltr"
                  className="mt-2 text-left text-sm font-semibold break-all text-app-foreground"
                >
                  {dataset.provenance.connection_id}
                </dd>
              </div>

              <div className="rounded-xl border border-app-border bg-app-surface-muted p-4">
                <dt className="text-xs text-app-muted">{copy.provenance.providerId}</dt>
                <dd
                  dir="ltr"
                  className="mt-2 text-left text-sm font-semibold break-all text-app-foreground"
                >
                  {dataset.provenance.provider_id}
                </dd>
              </div>

              <div className="rounded-xl border border-app-border bg-app-surface-muted p-4 md:col-span-2">
                <dt className="text-xs text-app-muted">{copy.provenance.importId}</dt>
                <dd
                  dir="ltr"
                  className="mt-2 text-left text-sm font-semibold break-all text-app-foreground"
                >
                  {dataset.provenance.import_id}
                </dd>
              </div>

              <div className="rounded-xl border border-app-border bg-app-surface-muted p-4 md:col-span-2">
                <dt className="text-xs text-app-muted">{copy.provenance.requestedRange}</dt>
                <dd className="mt-2 text-sm leading-7 text-app-foreground">
                  {dataset.provenance.requested_start_time
                    ? formatDate(dataset.provenance.requested_start_time, locale)
                    : '—'}
                  <span className="mx-2 text-app-subtle">—</span>
                  {dataset.provenance.requested_end_time
                    ? formatDate(dataset.provenance.requested_end_time, locale)
                    : '—'}
                </dd>
              </div>
            </dl>
          ) : null}

          {dataset.provenance.kind === 'manual_upload' && dataset.provenance.original_filename ? (
            <dl className="mt-5 grid gap-4 md:grid-cols-2">
              <div className="rounded-xl border border-app-border bg-app-surface-muted p-4">
                <dt className="text-xs text-app-muted">{copy.provenance.originalFilename}</dt>
                <dd
                  dir="ltr"
                  className="mt-2 text-left text-sm font-semibold break-all text-app-foreground"
                >
                  {dataset.provenance.original_filename}
                </dd>
              </div>

              <div className="rounded-xl border border-app-border bg-app-surface-muted p-4">
                <dt className="text-xs text-app-muted">{copy.provenance.originalFileFormat}</dt>
                <dd className="mt-2 text-sm font-semibold text-app-foreground uppercase">
                  {dataset.provenance.original_file_format}
                </dd>
              </div>

              <div className="rounded-xl border border-app-border bg-app-surface-muted p-4 md:col-span-2">
                <dt className="text-xs text-app-muted">{copy.provenance.originalFileChecksum}</dt>
                <dd
                  dir="ltr"
                  title={dataset.provenance.original_file_checksum ?? undefined}
                  className="mt-2 truncate text-left text-xs font-semibold text-app-muted"
                >
                  {dataset.provenance.original_file_checksum}
                </dd>
              </div>

              <div className="rounded-xl border border-app-border bg-app-surface-muted p-4 md:col-span-2">
                <dt className="text-xs text-app-muted">{copy.provenance.columnMapping}</dt>
                <dd className="mt-3 flex flex-wrap gap-2">
                  {Object.entries(dataset.provenance.column_mapping ?? {}).map(
                    ([field, column]) => (
                      <Badge key={field} variant="neutral">
                        {field} → {column}
                      </Badge>
                    ),
                  )}
                </dd>
              </div>
            </dl>
          ) : null}
        </CardContent>
      </Card>

      {dataset.provenance.kind === 'market_data_import' &&
      dataset.provenance.connection_id &&
      dataset.provenance.import_id ? (
        <DatasetVersionHistory
          connectionId={dataset.provenance.connection_id}
          importId={dataset.provenance.import_id}
          currentDatasetId={dataset.dataset_id}
          locale={locale}
        />
      ) : null}

      <Card>
        <CardHeader className="flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <CardTitle>{copy.quality.title}</CardTitle>
            <CardDescription>{copy.quality.description}</CardDescription>
          </div>

          <Badge
            variant={
              qualityStatus === 'passed'
                ? 'success'
                : qualityStatus === 'issues'
                  ? 'warning'
                  : 'neutral'
            }
          >
            {copy.quality.statuses[qualityStatus]}
          </Badge>
        </CardHeader>

        <CardContent>
          {dataset.quality_report === null ? (
            <p className="text-sm leading-7 text-app-muted">
              {copy.quality.notRecordedDescription}
            </p>
          ) : (
            <>
              <dl className="grid gap-4 sm:grid-cols-2">
                <div className="rounded-xl border border-app-border bg-app-surface-muted p-4">
                  <dt className="text-xs text-app-muted">{copy.quality.candlesChecked}</dt>
                  <dd className="mt-2 text-sm font-semibold text-app-foreground">
                    {formatNumber(dataset.quality_report.candles_checked, locale)}
                  </dd>
                </div>

                <div className="rounded-xl border border-app-border bg-app-surface-muted p-4">
                  <dt className="text-xs text-app-muted">{copy.quality.issueCount}</dt>
                  <dd className="mt-2 text-sm font-semibold text-app-foreground">
                    {formatNumber(qualityIssues.length, locale)}
                  </dd>
                </div>
              </dl>

              {dataset.quality_report.score && dataset.quality_report.acceptance ? (
                <section className="mt-5 rounded-xl border border-app-border bg-app-surface-muted p-4">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <h4 className="text-sm font-semibold text-app-foreground">
                      {copy.quality.scoreTitle}
                    </h4>
                    <Badge
                      variant={dataset.quality_report.acceptance.accepted ? 'success' : 'warning'}
                    >
                      {dataset.quality_report.acceptance.accepted
                        ? copy.quality.policyPassed
                        : copy.quality.policyFailed}
                    </Badge>
                  </div>
                  <dl className="mt-4 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
                    <div>
                      <dt className="text-xs text-app-muted">{copy.quality.scorePercent}</dt>
                      <dd className="mt-2 text-sm font-semibold text-app-foreground">
                        {formatPercent(dataset.quality_report.score.score_percent, locale)}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-xs text-app-muted">{copy.quality.coverageComponent}</dt>
                      <dd className="mt-2 text-sm font-semibold text-app-foreground">
                        {formatPercent(dataset.quality_report.score.coverage_percent, locale)}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-xs text-app-muted">{copy.quality.integrityComponent}</dt>
                      <dd className="mt-2 text-sm font-semibold text-app-foreground">
                        {formatPercent(dataset.quality_report.score.integrity_percent, locale)}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-xs text-app-muted">{copy.quality.scoreVersion}</dt>
                      <dd
                        dir="ltr"
                        className="mt-2 text-left text-sm font-semibold text-app-foreground"
                      >
                        {dataset.quality_report.score.score_version}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-xs text-app-muted">{copy.quality.policyVersion}</dt>
                      <dd
                        dir="ltr"
                        className="mt-2 text-left text-sm font-semibold text-app-foreground"
                      >
                        {dataset.quality_report.acceptance.policy_version}
                      </dd>
                    </div>
                  </dl>
                </section>
              ) : (
                <p className="mt-5 text-sm leading-7 text-app-muted">
                  {copy.quality.scoreNotRecorded}
                </p>
              )}

              {dataset.quality_report.coverage ? (
                <section className="mt-5 rounded-xl border border-app-border bg-app-surface-muted p-4">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <h4 className="text-sm font-semibold text-app-foreground">
                      {copy.quality.coverageTitle}
                    </h4>
                    <Badge
                      variant={dataset.quality_report.coverage.complete ? 'success' : 'warning'}
                    >
                      {dataset.quality_report.coverage.complete
                        ? copy.quality.completeCoverage
                        : copy.quality.incompleteCoverage}
                    </Badge>
                  </div>
                  <dl className="mt-4 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                    <div>
                      <dt className="text-xs text-app-muted">{copy.quality.expectedCandles}</dt>
                      <dd className="mt-2 text-sm font-semibold text-app-foreground">
                        {formatNumber(dataset.quality_report.coverage.expected_candles, locale)}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-xs text-app-muted">{copy.quality.receivedCandles}</dt>
                      <dd className="mt-2 text-sm font-semibold text-app-foreground">
                        {formatNumber(dataset.quality_report.coverage.received_candles, locale)}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-xs text-app-muted">{copy.quality.missingCandles}</dt>
                      <dd className="mt-2 text-sm font-semibold text-app-foreground">
                        {formatNumber(dataset.quality_report.coverage.missing_candles, locale)}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-xs text-app-muted">{copy.quality.coveragePercent}</dt>
                      <dd className="mt-2 text-sm font-semibold text-app-foreground">
                        {formatPercent(dataset.quality_report.coverage.coverage_percent, locale)}
                      </dd>
                    </div>
                  </dl>
                </section>
              ) : null}

              {qualityIssues.length === 0 ? (
                <p className="mt-5 text-sm leading-7 text-app-muted">
                  {copy.quality.passedDescription}
                </p>
              ) : (
                <ul className="mt-5 space-y-3">
                  {qualityIssues.map((issue, index) => (
                    <li
                      key={`${issue.code}-${issue.timestamp ?? 'none'}-${index}`}
                      className="rounded-xl border border-app-border bg-app-surface-muted p-4"
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <Badge variant="warning">{issue.code}</Badge>
                        {issue.timestamp ? (
                          <span className="text-xs text-app-muted">
                            {copy.quality.issueTimestamp}: {formatDate(issue.timestamp, locale)}
                          </span>
                        ) : null}
                      </div>
                      <p className="mt-3 text-sm leading-7 text-app-foreground">{issue.message}</p>
                    </li>
                  ))}
                </ul>
              )}
            </>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <CardTitle>{copy.candles.title}</CardTitle>
            <CardDescription>{copy.candles.description}</CardDescription>
          </div>

          <Badge variant="neutral">
            {copy.candles.total}:​​ {formatNumber(candlesPage.total, locale)}
          </Badge>
        </CardHeader>

        <CardContent className="relative min-h-64">
          {isLoading ? (
            <div className="absolute inset-0 z-20 flex items-center justify-center rounded-xl bg-app-overlay backdrop-blur-sm">
              <Spinner size="lg" label={copy.candles.loading} className="text-app-accent" />
            </div>
          ) : null}

          {hasError ? (
            <EmptyState
              title={copy.candles.errorTitle}
              description={copy.candles.errorDescription}
              className="border-red-500/20 bg-red-500/10"
              icon={<span className="font-bold text-red-500">!</span>}
              action={
                <Button
                  size="sm"
                  variant="danger"
                  onClick={() => void loadCandles(candlesPage.offset)}
                >
                  {copy.candles.retry}
                </Button>
              }
            />
          ) : (
            <>
              <Table scrollLabel={copy.candles.scrollLabel} className="min-w-[58rem]">
                <TableHeader>
                  <TableRow>
                    <TableHead>{copy.candles.row}</TableHead>
                    <TableHead>{copy.candles.openTime}</TableHead>
                    <TableHead>{copy.candles.closeTime}</TableHead>
                    <TableHead>{copy.candles.open}</TableHead>
                    <TableHead>{copy.candles.high}</TableHead>
                    <TableHead>{copy.candles.low}</TableHead>
                    <TableHead>{copy.candles.close}</TableHead>
                    <TableHead>{copy.candles.volume}</TableHead>
                    <TableHead>{copy.candles.status}</TableHead>
                  </TableRow>
                </TableHeader>

                <TableBody>
                  {candlesPage.items.map((candle, index) => (
                    <TableRow key={`${candle.open_time}-${candlesPage.offset + index}`}>
                      <TableCell>{formatNumber(candlesPage.offset + index + 1, locale)}</TableCell>

                      <TableCell>{formatDate(candle.open_time, locale)}</TableCell>

                      <TableCell>{formatDate(candle.close_time, locale)}</TableCell>

                      <TableCell dir="ltr" className="text-left font-semibold">
                        {candle.open_price}
                      </TableCell>

                      <TableCell dir="ltr" className="text-left font-semibold text-emerald-500">
                        {candle.high_price}
                      </TableCell>

                      <TableCell dir="ltr" className="text-left font-semibold text-red-500">
                        {candle.low_price}
                      </TableCell>

                      <TableCell dir="ltr" className="text-left font-semibold">
                        {candle.close_price}
                      </TableCell>

                      <TableCell dir="ltr" className="text-left font-semibold">
                        {candle.volume}
                      </TableCell>

                      <TableCell>
                        <Badge variant={candle.is_closed ? 'success' : 'warning'}>
                          {candle.is_closed ? copy.candles.closed : copy.candles.openCandle}
                        </Badge>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>

              <div className="mt-5">
                <Pagination
                  total={candlesPage.total}
                  limit={candlesPage.limit}
                  offset={candlesPage.offset}
                  isLoading={isLoading}
                  pageLabel={copy.pagination.page}
                  previousLabel={copy.pagination.previous}
                  nextLabel={copy.pagination.next}
                  onOffsetChange={(nextOffset) => void loadCandles(nextOffset)}
                />
              </div>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
