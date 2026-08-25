'use client';

import Link from 'next/link';
import { type ChangeEvent, type FormEvent, useState } from 'react';

import type { DashboardLocale } from '@/components/dashboard/dashboard-copy';
import {
  Badge,
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  Input,
  Select,
  SelectOption,
} from '@/components/ui';
import { ApiRequestError, createDataset } from '@/lib/api/client';
import type { DatasetImportCandle, DatasetSummary, DatasetTimeframe } from '@/lib/api/types';
import { DatasetCsvError, parseDatasetCsv } from '@/lib/datasets/csv';
import { getDatasetImportCopy } from './dataset-import-copy';

const MAX_FILE_SIZE = 10 * 1024 * 1024;
const ASSET_PATTERN = /^[A-Z0-9]{2,15}$/u;

const CSV_TEMPLATE = [
  'open_time,close_time,open_price,high_price,low_price,close_price,volume,is_closed',
  '2026-08-20T10:00:00.000Z,2026-08-20T11:00:00.000Z,100,102,99,101,1500,true',
  '2026-08-20T11:00:00.000Z,2026-08-20T12:00:00.000Z,101,103,100,102,1600,true',
].join('\n');

type FormField = 'name' | 'source' | 'baseAsset' | 'quoteAsset' | 'file';

type FormErrors = Partial<Record<FormField, string>>;

type DatasetImportFormProps = {
  locale: DashboardLocale;
  onImported?: (dataset: DatasetSummary) => Promise<void> | void;
};

function formatNumber(value: number, locale: DashboardLocale): string {
  return new Intl.NumberFormat(locale === 'fa' ? 'fa-IR' : 'en-US').format(value);
}

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

export default function DatasetImportForm({ locale, onImported }: DatasetImportFormProps) {
  const copy = getDatasetImportCopy(locale);
  const direction = locale === 'fa' ? 'rtl' : 'ltr';

  const [name, setName] = useState('');
  const [source, setSource] = useState('');
  const [baseAsset, setBaseAsset] = useState('');
  const [quoteAsset, setQuoteAsset] = useState('');
  const [timeframe, setTimeframe] = useState<DatasetTimeframe>('1h');

  const [fileName, setFileName] = useState('');
  const [csvText, setCsvText] = useState('');
  const [candles, setCandles] = useState<DatasetImportCandle[]>([]);

  const [errors, setErrors] = useState<FormErrors>({});
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [createdDataset, setCreatedDataset] = useState<DatasetSummary | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  function clearFieldError(field: FormField): void {
    setErrors((current) => {
      const next = { ...current };
      delete next[field];

      return next;
    });
  }

  function formatCsvError(error: DatasetCsvError): string {
    const message = copy.csvErrors[error.code];

    if (error.row === undefined) {
      return message;
    }

    return `${message} (${copy.row} ${formatNumber(error.row, locale)})`;
  }

  function parseFileContents(contents: string, selectedTimeframe: DatasetTimeframe): void {
    try {
      const parsedCandles = parseDatasetCsv(contents, selectedTimeframe);

      setCandles(parsedCandles);
      clearFieldError('file');
    } catch (error) {
      setCandles([]);

      setErrors((current) => ({
        ...current,
        file: error instanceof DatasetCsvError ? formatCsvError(error) : copy.errors.readFailed,
      }));
    }
  }

  async function handleFileChange(event: ChangeEvent<HTMLInputElement>): Promise<void> {
    const file = event.target.files?.[0];

    setCreatedDataset(null);
    setSubmitError(null);
    setCsvText('');
    setCandles([]);

    if (!file) {
      setFileName('');

      setErrors((current) => ({
        ...current,
        file: copy.errors.fileRequired,
      }));

      return;
    }

    setFileName(file.name);

    if (file.size > MAX_FILE_SIZE) {
      setErrors((current) => ({
        ...current,
        file: copy.errors.fileTooLarge,
      }));

      return;
    }

    try {
      const contents = await file.text();

      setCsvText(contents);
      parseFileContents(contents, timeframe);
    } catch {
      setErrors((current) => ({
        ...current,
        file: copy.errors.readFailed,
      }));
    }
  }

  function handleTimeframeChange(value: string): void {
    const nextTimeframe = value as DatasetTimeframe;

    setTimeframe(nextTimeframe);
    setCreatedDataset(null);

    if (csvText) {
      parseFileContents(csvText, nextTimeframe);
    }
  }

  function downloadTemplate(): void {
    const blob = new Blob([CSV_TEMPLATE], {
      type: 'text/csv;charset=utf-8',
    });

    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');

    link.href = url;
    link.download = 'dataset-template.csv';

    document.body.append(link);
    link.click();
    link.remove();

    URL.revokeObjectURL(url);
  }

  function validateForm(): FormErrors {
    const nextErrors: FormErrors = {};

    const normalizedName = name.trim();
    const normalizedSource = source.trim();
    const normalizedBaseAsset = baseAsset.trim().toUpperCase();
    const normalizedQuoteAsset = quoteAsset.trim().toUpperCase();

    if (!normalizedName) {
      nextErrors.name = copy.errors.required;
    }

    if (!normalizedSource) {
      nextErrors.source = copy.errors.required;
    }

    if (!ASSET_PATTERN.test(normalizedBaseAsset)) {
      nextErrors.baseAsset = copy.errors.invalidAsset;
    }

    if (!ASSET_PATTERN.test(normalizedQuoteAsset)) {
      nextErrors.quoteAsset = copy.errors.invalidAsset;
    }

    if (normalizedBaseAsset && normalizedBaseAsset === normalizedQuoteAsset) {
      nextErrors.quoteAsset = copy.errors.identicalAssets;
    }

    if (candles.length === 0) {
      nextErrors.file = errors.file ?? copy.errors.fileRequired;
    }

    return nextErrors;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();

    const nextErrors = validateForm();

    setErrors(nextErrors);
    setSubmitError(null);
    setCreatedDataset(null);

    if (Object.keys(nextErrors).length > 0) {
      return;
    }

    setIsSubmitting(true);

    try {
      const dataset = await createDataset({
        name: name.trim(),
        source: source.trim(),
        pair: {
          base_asset: baseAsset.trim().toUpperCase(),
          quote_asset: quoteAsset.trim().toUpperCase(),
          market_type: 'spot',
        },
        timeframe,
        candles,
      });

      setCreatedDataset(dataset);

      if (onImported) {
        await onImported(dataset);
      }
    } catch (error) {
      if (error instanceof ApiRequestError && error.status === 422) {
        setSubmitError(copy.errors.backendValidation);
      } else {
        setSubmitError(copy.errors.submitFailed);
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  const firstCandle = candles[0];
  const lastCandle = candles[candles.length - 1];

  return (
    <Card>
      <CardHeader className="border-b border-slate-800">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <CardTitle>{copy.title}</CardTitle>
            <CardDescription className="mt-2 max-w-2xl">{copy.description}</CardDescription>
          </div>

          <Badge variant="warning">{copy.historicalOnly}</Badge>
        </div>
      </CardHeader>

      <CardContent className="pt-6">
        <form className="space-y-6" onSubmit={handleSubmit} noValidate>
          <div className="grid gap-5 md:grid-cols-2">
            <Input
              label={copy.name}
              placeholder={copy.namePlaceholder}
              value={name}
              error={errors.name}
              disabled={isSubmitting}
              maxLength={100}
              onChange={(event) => {
                setName(event.target.value);
                setCreatedDataset(null);
                clearFieldError('name');
              }}
            />

            <Input
              label={copy.source}
              placeholder={copy.sourcePlaceholder}
              value={source}
              error={errors.source}
              disabled={isSubmitting}
              maxLength={50}
              onChange={(event) => {
                setSource(event.target.value);
                setCreatedDataset(null);
                clearFieldError('source');
              }}
            />

            <Input
              dir="ltr"
              label={copy.baseAsset}
              placeholder="BTC"
              value={baseAsset}
              error={errors.baseAsset}
              disabled={isSubmitting}
              maxLength={15}
              className="text-left uppercase"
              onChange={(event) => {
                setBaseAsset(event.target.value.toUpperCase());
                setCreatedDataset(null);
                clearFieldError('baseAsset');
              }}
            />

            <Input
              dir="ltr"
              label={copy.quoteAsset}
              placeholder="USDT"
              value={quoteAsset}
              error={errors.quoteAsset}
              disabled={isSubmitting}
              maxLength={15}
              className="text-left uppercase"
              onChange={(event) => {
                setQuoteAsset(event.target.value.toUpperCase());
                setCreatedDataset(null);
                clearFieldError('quoteAsset');
              }}
            />

            <Select
              label={copy.timeframe}
              dir={direction}
              value={timeframe}
              disabled={isSubmitting}
              onValueChange={handleTimeframeChange}
            >
              <SelectOption value="15m">{copy.timeframes['15m']}</SelectOption>

              <SelectOption value="1h">{copy.timeframes['1h']}</SelectOption>

              <SelectOption value="4h">{copy.timeframes['4h']}</SelectOption>

              <SelectOption value="1d">{copy.timeframes['1d']}</SelectOption>
            </Select>

            <Input
              type="file"
              accept=".csv,text/csv"
              label={copy.csvFile}
              hint={copy.csvHint}
              error={errors.file}
              disabled={isSubmitting}
              onChange={(event) => {
                void handleFileChange(event);
              }}
            />
          </div>

          <div>
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={downloadTemplate}
              disabled={isSubmitting}
            >
              {copy.downloadTemplate}
            </Button>
          </div>

          {candles.length > 0 && firstCandle && lastCandle ? (
            <section
              aria-label={copy.previewTitle}
              className="rounded-2xl border border-cyan-400/20 bg-cyan-400/5 p-5"
            >
              <h3 className="text-sm font-semibold text-cyan-200">{copy.previewTitle}</h3>

              <dl className="mt-4 grid gap-4 text-sm sm:grid-cols-2 lg:grid-cols-4">
                <div>
                  <dt className="text-xs text-slate-500">{copy.previewFile}</dt>
                  <dd dir="ltr" className="mt-2 truncate text-left text-slate-200">
                    {fileName}
                  </dd>
                </div>

                <div>
                  <dt className="text-xs text-slate-500">{copy.previewCandles}</dt>
                  <dd className="mt-2 text-slate-200">{formatNumber(candles.length, locale)}</dd>
                </div>

                <div>
                  <dt className="text-xs text-slate-500">{copy.previewStart}</dt>
                  <dd className="mt-2 text-slate-200">
                    {formatDate(firstCandle.open_time, locale)}
                  </dd>
                </div>

                <div>
                  <dt className="text-xs text-slate-500">{copy.previewEnd}</dt>
                  <dd className="mt-2 text-slate-200">
                    {formatDate(lastCandle.close_time, locale)}
                  </dd>
                </div>
              </dl>
            </section>
          ) : null}

          {submitError ? (
            <p
              role="alert"
              className="rounded-xl border border-red-400/20 bg-red-400/5 p-4 text-sm text-red-300"
            >
              {submitError}
            </p>
          ) : null}

          {createdDataset ? (
            <div
              role="status"
              className="rounded-xl border border-emerald-400/20 bg-emerald-400/5 p-5"
            >
              <p className="font-semibold text-emerald-300">{copy.successTitle}</p>

              <p className="mt-2 text-sm leading-6 text-slate-400">{copy.successDescription}</p>

              <p dir="ltr" className="mt-3 text-left font-mono text-xs break-all text-slate-500">
                {createdDataset.dataset_id}
              </p>

              <Link
                href={`/${locale}/datasets/${encodeURIComponent(createdDataset.dataset_id)}`}
                className="mt-4 inline-flex min-h-10 items-center justify-center rounded-xl border border-emerald-400/30 px-4 py-2 text-sm font-semibold text-emerald-300 transition hover:bg-emerald-400/10"
              >
                {copy.viewDataset}
              </Link>
            </div>
          ) : null}

          <Button
            type="submit"
            size="lg"
            fullWidth
            isLoading={isSubmitting}
            loadingText={copy.importing}
          >
            {copy.importButton}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
