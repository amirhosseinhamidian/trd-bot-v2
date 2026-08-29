'use client';

import Link from 'next/link';
import { useRef, useState } from 'react';

import type { DashboardLocale } from '@/components/dashboard/dashboard-copy';
import { getDatasetDetailCopy } from '@/components/dashboard/dataset-detail-copy';
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
import type { DatasetSummary, OHLCVCandle, Page } from '@/lib/api/types';

const CANDLES_PER_PAGE = 25;

type DatasetDetailProps = {
  dataset: DatasetSummary;
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
          className="inline-flex items-center gap-2 text-sm text-app-muted transition hover:text-app-accent"
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
              <Table>
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
