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
import {
  ApiRequestError,
  importDatasetFile,
  inspectDatasetFile,
  previewDatasetFile,
} from '@/lib/api/client';
import type {
  DatasetColumnMapping,
  DatasetFileField,
  DatasetFileImportPreview,
  DatasetFileInspection,
  DatasetFilePreviewRequest,
  DatasetSummary,
  DatasetTimeframe,
} from '@/lib/api/types';
import { getDatasetImportCopy } from './dataset-import-copy';

const MAX_FILE_SIZE = 10 * 1024 * 1024;
const ASSET_PATTERN = /^[A-Z0-9]{2,15}$/u;
const OPTIONAL_MAPPING_VALUE = '__optional__';
const SUPPORTED_EXTENSION = /\.(?:csv|json|parquet)$/iu;

const CSV_TEMPLATE = [
  'open_time,close_time,open_price,high_price,low_price,close_price,volume,is_closed',
  '2026-08-20T10:00:00.000Z,2026-08-20T11:00:00.000Z,100,102,99,101,1500,true',
  '2026-08-20T11:00:00.000Z,2026-08-20T12:00:00.000Z,101,103,100,102,1600,true',
].join('\n');

const REQUIRED_MAPPING_FIELDS = [
  'open_time',
  'open_price',
  'high_price',
  'low_price',
  'close_price',
  'volume',
] as const satisfies readonly DatasetFileField[];

const OPTIONAL_MAPPING_FIELDS = [
  'close_time',
  'is_closed',
] as const satisfies readonly DatasetFileField[];

type FormField = 'name' | 'source' | 'baseAsset' | 'quoteAsset' | 'file' | 'mapping';
type FormErrors = Partial<Record<FormField, string>>;

type DatasetImportFormProps = {
  locale: DashboardLocale;
  onImported?: (dataset: DatasetSummary) => Promise<void> | void;
};

function emptyMapping(): DatasetColumnMapping {
  return {
    open_time: '',
    open_price: '',
    high_price: '',
    low_price: '',
    close_price: '',
    volume: '',
    close_time: null,
    is_closed: null,
  };
}

function suggestedMapping(inspection: DatasetFileInspection): DatasetColumnMapping {
  const mapping = emptyMapping();

  for (const field of [...REQUIRED_MAPPING_FIELDS, ...OPTIONAL_MAPPING_FIELDS]) {
    const suggestion = inspection.suggested_mapping[field];
    if (suggestion) {
      mapping[field] = suggestion;
    }
  }
  return mapping;
}

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

function apiErrorCode(error: ApiRequestError): string | null {
  if (typeof error.payload !== 'object' || error.payload === null || !('detail' in error.payload)) {
    return null;
  }
  const detail = error.payload.detail;
  if (typeof detail !== 'object' || detail === null || !('code' in detail)) {
    return null;
  }
  return typeof detail.code === 'string' ? detail.code : null;
}

export default function DatasetImportForm({ locale, onImported }: DatasetImportFormProps) {
  const copy = getDatasetImportCopy(locale);
  const direction = locale === 'fa' ? 'rtl' : 'ltr';

  const [name, setName] = useState('');
  const [source, setSource] = useState('');
  const [baseAsset, setBaseAsset] = useState('');
  const [quoteAsset, setQuoteAsset] = useState('');
  const [timeframe, setTimeframe] = useState<DatasetTimeframe>('1h');
  const [file, setFile] = useState<File | null>(null);
  const [inspection, setInspection] = useState<DatasetFileInspection | null>(null);
  const [mapping, setMapping] = useState<DatasetColumnMapping>(emptyMapping);
  const [preview, setPreview] = useState<DatasetFileImportPreview | null>(null);
  const [errors, setErrors] = useState<FormErrors>({});
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [createdDataset, setCreatedDataset] = useState<DatasetSummary | null>(null);
  const [activity, setActivity] = useState<'inspect' | 'preview' | 'import' | null>(null);

  const isBusy = activity !== null;

  function clearFieldError(field: FormField): void {
    setErrors((current) => {
      const next = { ...current };
      delete next[field];
      return next;
    });
  }

  function invalidatePreview(): void {
    setPreview(null);
    setCreatedDataset(null);
    setSubmitError(null);
  }

  async function handleFileChange(event: ChangeEvent<HTMLInputElement>): Promise<void> {
    const selectedFile = event.target.files?.[0] ?? null;

    setFile(selectedFile);
    setInspection(null);
    setMapping(emptyMapping());
    invalidatePreview();

    if (!selectedFile) {
      setErrors((current) => ({ ...current, file: copy.errors.fileRequired }));
      return;
    }
    if (selectedFile.size > MAX_FILE_SIZE) {
      setErrors((current) => ({ ...current, file: copy.errors.fileTooLarge }));
      return;
    }
    if (!SUPPORTED_EXTENSION.test(selectedFile.name)) {
      setErrors((current) => ({ ...current, file: copy.errors.unsupportedFile }));
      return;
    }

    clearFieldError('file');
    setActivity('inspect');
    try {
      const result = await inspectDatasetFile(selectedFile);
      setInspection(result);
      setMapping(suggestedMapping(result));
      if (!result.can_preview) {
        setErrors((current) => ({ ...current, mapping: copy.errors.mappingRequired }));
      }
    } catch {
      setErrors((current) => ({ ...current, file: copy.errors.inspectionFailed }));
    } finally {
      setActivity(null);
    }
  }

  function updateMapping(field: DatasetFileField, value: string): void {
    setMapping((current) => ({
      ...current,
      [field]: value === OPTIONAL_MAPPING_VALUE ? null : value,
    }));
    invalidatePreview();
    clearFieldError('mapping');
  }

  function downloadTemplate(): void {
    const blob = new Blob([CSV_TEMPLATE], { type: 'text/csv;charset=utf-8' });
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
    const normalizedBaseAsset = baseAsset.trim().toUpperCase();
    const normalizedQuoteAsset = quoteAsset.trim().toUpperCase();

    if (!name.trim()) nextErrors.name = copy.errors.required;
    if (!source.trim()) nextErrors.source = copy.errors.required;
    if (!ASSET_PATTERN.test(normalizedBaseAsset)) nextErrors.baseAsset = copy.errors.invalidAsset;
    if (!ASSET_PATTERN.test(normalizedQuoteAsset)) nextErrors.quoteAsset = copy.errors.invalidAsset;
    if (normalizedBaseAsset && normalizedBaseAsset === normalizedQuoteAsset) {
      nextErrors.quoteAsset = copy.errors.identicalAssets;
    }
    if (!file || !inspection) nextErrors.file = errors.file ?? copy.errors.fileRequired;
    if (REQUIRED_MAPPING_FIELDS.some((field) => !mapping[field])) {
      nextErrors.mapping = copy.errors.mappingRequired;
    }

    const selectedColumns = Object.values(mapping).filter(
      (column): column is string => column !== null && column.length > 0,
    );
    if (selectedColumns.length !== new Set(selectedColumns).size) {
      nextErrors.mapping = copy.errors.duplicateMapping;
    }
    return nextErrors;
  }

  function buildPreviewRequest(): DatasetFilePreviewRequest {
    return {
      name: name.trim(),
      source: source.trim(),
      pair: {
        base_asset: baseAsset.trim().toUpperCase(),
        quote_asset: quoteAsset.trim().toUpperCase(),
        market_type: 'spot',
      },
      timeframe,
      column_mapping: mapping,
    };
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    const nextErrors = validateForm();

    setErrors(nextErrors);
    setSubmitError(null);
    setCreatedDataset(null);
    if (Object.keys(nextErrors).length > 0 || !file) return;

    if (!preview) {
      setActivity('preview');
      try {
        const result = await previewDatasetFile(file, buildPreviewRequest());
        setPreview(result);
        if (!result.ready_to_import) setSubmitError(copy.errors.qualityRejected);
      } catch {
        setSubmitError(copy.errors.previewFailed);
      } finally {
        setActivity(null);
      }
      return;
    }

    if (!preview.ready_to_import) {
      setSubmitError(copy.errors.qualityRejected);
      return;
    }

    setActivity('import');
    try {
      const dataset = await importDatasetFile(file, {
        ...buildPreviewRequest(),
        preview_checksum: preview.preview_checksum,
      });
      setCreatedDataset(dataset);
      if (onImported) await onImported(dataset);
    } catch (error) {
      if (error instanceof ApiRequestError && apiErrorCode(error) === 'preview_mismatch') {
        setPreview(null);
        setSubmitError(copy.errors.previewExpired);
      } else {
        setSubmitError(copy.errors.submitFailed);
      }
    } finally {
      setActivity(null);
    }
  }

  const score = preview?.quality_report.score?.score_percent;

  return (
    <Card>
      <CardHeader className="border-b border-app-border">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0 flex-1">
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
              disabled={isBusy}
              maxLength={100}
              onChange={(event) => {
                setName(event.target.value);
                invalidatePreview();
                clearFieldError('name');
              }}
            />
            <Input
              label={copy.source}
              placeholder={copy.sourcePlaceholder}
              value={source}
              error={errors.source}
              disabled={isBusy}
              maxLength={50}
              onChange={(event) => {
                setSource(event.target.value);
                invalidatePreview();
                clearFieldError('source');
              }}
            />
            <Input
              dir="ltr"
              label={copy.baseAsset}
              placeholder="BTC"
              value={baseAsset}
              error={errors.baseAsset}
              disabled={isBusy}
              maxLength={15}
              className="text-left uppercase"
              onChange={(event) => {
                setBaseAsset(event.target.value.toUpperCase());
                invalidatePreview();
                clearFieldError('baseAsset');
              }}
            />
            <Input
              dir="ltr"
              label={copy.quoteAsset}
              placeholder="USDT"
              value={quoteAsset}
              error={errors.quoteAsset}
              disabled={isBusy}
              maxLength={15}
              className="text-left uppercase"
              onChange={(event) => {
                setQuoteAsset(event.target.value.toUpperCase());
                invalidatePreview();
                clearFieldError('quoteAsset');
              }}
            />
            <Select
              label={copy.timeframe}
              dir={direction}
              value={timeframe}
              disabled={isBusy}
              onValueChange={(value) => {
                setTimeframe(value as DatasetTimeframe);
                invalidatePreview();
              }}
            >
              <SelectOption value="15m">{copy.timeframes['15m']}</SelectOption>
              <SelectOption value="1h">{copy.timeframes['1h']}</SelectOption>
              <SelectOption value="4h">{copy.timeframes['4h']}</SelectOption>
              <SelectOption value="1d">{copy.timeframes['1d']}</SelectOption>
            </Select>
            <Input
              type="file"
              accept=".csv,.json,.parquet,text/csv,application/json,application/vnd.apache.parquet"
              label={copy.datasetFile}
              hint={activity === 'inspect' ? copy.inspecting : copy.fileHint}
              error={errors.file}
              disabled={isBusy}
              onChange={(event) => void handleFileChange(event)}
            />
          </div>

          <Button
            type="button"
            variant="secondary"
            size="sm"
            className="w-full sm:w-auto"
            onClick={downloadTemplate}
            disabled={isBusy}
          >
            {copy.downloadTemplate}
          </Button>

          {inspection ? (
            <section className="rounded-2xl border border-app-border bg-app-surface-muted p-5">
              <h3 className="font-semibold text-app-foreground">{copy.mappingTitle}</h3>
              <p className="mt-2 text-sm text-app-muted">{copy.mappingDescription}</p>
              <div className="mt-5 grid gap-4 md:grid-cols-2">
                {REQUIRED_MAPPING_FIELDS.map((field) => (
                  <Select
                    key={field}
                    label={copy.fields[field]}
                    dir={direction}
                    value={mapping[field] || undefined}
                    placeholder={copy.errors.mappingRequired}
                    disabled={isBusy}
                    onValueChange={(value) => updateMapping(field, value)}
                  >
                    {inspection.columns.map((column) => (
                      <SelectOption key={column} value={column}>
                        {column}
                      </SelectOption>
                    ))}
                  </Select>
                ))}
                {OPTIONAL_MAPPING_FIELDS.map((field) => (
                  <Select
                    key={field}
                    label={`${copy.fields[field]} (${copy.optional})`}
                    dir={direction}
                    value={mapping[field] ?? OPTIONAL_MAPPING_VALUE}
                    disabled={isBusy}
                    onValueChange={(value) => updateMapping(field, value)}
                  >
                    <SelectOption value={OPTIONAL_MAPPING_VALUE}>
                      {field === 'close_time' ? copy.derivedCloseTime : copy.defaultClosed}
                    </SelectOption>
                    {inspection.columns.map((column) => (
                      <SelectOption key={column} value={column}>
                        {column}
                      </SelectOption>
                    ))}
                  </Select>
                ))}
              </div>
              {errors.mapping ? (
                <p role="alert" className="mt-4 text-sm text-red-500">
                  {errors.mapping}
                </p>
              ) : null}
            </section>
          ) : null}

          {preview ? (
            <section
              aria-label={copy.previewTitle}
              className="rounded-2xl border border-app-accent-border bg-app-accent-soft p-5"
            >
              <div className="flex flex-wrap items-center justify-between gap-3">
                <h3 className="text-sm font-semibold text-app-accent">{copy.previewTitle}</h3>
                <Badge variant={preview.ready_to_import ? 'success' : 'warning'}>
                  {preview.ready_to_import ? copy.qualityPassed : copy.qualityRejected}
                </Badge>
              </div>
              <dl className="mt-4 grid gap-4 text-sm sm:grid-cols-2 lg:grid-cols-4">
                <div>
                  <dt className="text-xs text-app-muted">{copy.previewFile}</dt>
                  <dd dir="ltr" className="mt-2 truncate text-left text-app-foreground">
                    {preview.inspection.file_name}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs text-app-muted">{copy.previewFormat}</dt>
                  <dd className="mt-2 text-app-foreground uppercase">
                    {preview.inspection.file_format}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs text-app-muted">{copy.previewRows}</dt>
                  <dd className="mt-2 text-app-foreground">
                    {formatNumber(preview.inspection.row_count, locale)}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs text-app-muted">{copy.previewCandles}</dt>
                  <dd className="mt-2 text-app-foreground">
                    {formatNumber(preview.candle_count, locale)}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs text-app-muted">{copy.previewStart}</dt>
                  <dd className="mt-2 text-app-foreground">
                    {formatDate(preview.first_open_time, locale)}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs text-app-muted">{copy.previewEnd}</dt>
                  <dd className="mt-2 text-app-foreground">
                    {formatDate(preview.last_close_time, locale)}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs text-app-muted">{copy.qualityScore}</dt>
                  <dd className="mt-2 text-app-foreground">
                    {score === undefined ? '—' : `${formatNumber(score, locale)}%`}
                  </dd>
                </div>
                <div className="min-w-0">
                  <dt className="text-xs text-app-muted">{copy.checksum}</dt>
                  <dd
                    dir="ltr"
                    title={preview.preview_checksum}
                    className="mt-2 truncate text-left text-xs text-app-foreground"
                  >
                    {preview.preview_checksum}
                  </dd>
                </div>
              </dl>
              {preview.quality_report.issues.length > 0 ? (
                <ul className="mt-5 space-y-2 text-sm text-amber-600">
                  {preview.quality_report.issues.map((issue, index) => (
                    <li key={`${issue.code}-${issue.timestamp ?? index}`}>{issue.message}</li>
                  ))}
                </ul>
              ) : null}
            </section>
          ) : null}

          {submitError ? (
            <p
              role="alert"
              className="rounded-xl border border-red-500/20 bg-red-500/10 p-4 text-sm text-red-500"
            >
              {submitError}
            </p>
          ) : null}

          {createdDataset ? (
            <div
              role="status"
              className="rounded-xl border border-emerald-500/20 bg-emerald-500/10 p-5"
            >
              <p className="font-semibold text-emerald-500">{copy.successTitle}</p>
              <p className="mt-2 text-sm leading-6 text-app-muted">{copy.successDescription}</p>
              <p
                dir="ltr"
                className="mt-3 text-left text-xs font-semibold break-all text-app-muted"
              >
                {createdDataset.dataset_id}
              </p>
              <Link
                href={`/${locale}/datasets/${encodeURIComponent(createdDataset.dataset_id)}`}
                className="mt-4 inline-flex min-h-10 w-full items-center justify-center rounded-xl border border-emerald-500/30 px-4 py-2 text-center text-sm font-semibold text-emerald-500 transition hover:bg-emerald-500/10 focus-visible:ring-2 focus-visible:ring-app-accent focus-visible:ring-offset-2 focus-visible:ring-offset-app-background focus-visible:outline-none sm:w-auto"
              >
                {copy.viewDataset}
              </Link>
            </div>
          ) : null}

          <Button
            type="submit"
            size="lg"
            fullWidth
            isLoading={activity === 'preview' || activity === 'import'}
            loadingText={activity === 'preview' ? copy.previewing : copy.importing}
            disabled={activity === 'inspect' || (preview !== null && !preview.ready_to_import)}
          >
            {preview ? copy.importButton : copy.previewButton}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
