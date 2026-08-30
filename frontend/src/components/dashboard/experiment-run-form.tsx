'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from 'react';

import type { DashboardLocale } from '@/components/dashboard/dashboard-copy';
import { getExperimentRunCopy } from '@/components/dashboard/experiment-run-copy';
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
  Spinner,
} from '@/components/ui';
import {
  ApiRequestError,
  createEmaCrossoverExperimentExecution,
  createRsiThresholdExperimentExecution,
  getDatasets,
  getExperimentExecution,
} from '@/lib/api/client';
import type {
  CreatedResearchExperiment,
  DatasetSummary,
  ExperimentExecution,
  ResearchStrategyName,
  StoredDatasetEMACrossoverRequest,
  StoredDatasetRSIThresholdRequest,
} from '@/lib/api/types';

import type { ExperimentRunInitialValues } from '@/lib/experiments/run-params';

type ExperimentRunFormProps = {
  locale: DashboardLocale;
  initialValues?: ExperimentRunInitialValues;
  initialExecutionId?: string;
  onCreated?: (experiment: CreatedResearchExperiment) => Promise<void> | void;
};

type FormValues = {
  datasetId: string;
  strategyName: ResearchStrategyName;
  fastPeriod: string;
  slowPeriod: string;
  rsiPeriod: string;
  oversoldThreshold: string;
  overboughtThreshold: string;
  horizonCandles: string;
  startingBalance: string;
  allocationFraction: string;
  feeRate: string;
  slippageRate: string;
};

const INITIAL_VALUES: FormValues = {
  datasetId: '',
  strategyName: 'ema-crossover',
  fastPeriod: '9',
  slowPeriod: '21',
  rsiPeriod: '14',
  oversoldThreshold: '30',
  overboughtThreshold: '70',
  horizonCandles: '1',
  startingBalance: '10000',
  allocationFraction: '0.10',
  feeRate: '0.001',
  slippageRate: '0.0005',
};

type BuiltExperimentRequest =
  | {
      strategyName: 'ema-crossover';
      request: StoredDatasetEMACrossoverRequest;
    }
  | {
      strategyName: 'rsi-threshold';
      request: StoredDatasetRSIThresholdRequest;
    };

const POLLING_INTERVAL_MS = 1000;

function fetchAvailableDatasets() {
  return getDatasets({
    sortBy: 'created_at',
    sortDirection: 'desc',
    limit: 100,
    offset: 0,
  });
}

function buildInitialFormValues(initialValues?: ExperimentRunInitialValues): FormValues {
  const mergedValues: FormValues = {
    ...INITIAL_VALUES,
    ...initialValues,
  };

  if (mergedValues.strategyName === 'ema-crossover') {
    const fastPeriod = Number(mergedValues.fastPeriod);
    const slowPeriod = Number(mergedValues.slowPeriod);

    if (
      !Number.isInteger(fastPeriod) ||
      !Number.isInteger(slowPeriod) ||
      slowPeriod <= fastPeriod
    ) {
      mergedValues.fastPeriod = INITIAL_VALUES.fastPeriod;
      mergedValues.slowPeriod = INITIAL_VALUES.slowPeriod;
    }
  } else {
    const rsiPeriod = Number(mergedValues.rsiPeriod);
    const oversoldThreshold = Number(mergedValues.oversoldThreshold);
    const overboughtThreshold = Number(mergedValues.overboughtThreshold);

    if (!Number.isInteger(rsiPeriod) || rsiPeriod < 2) {
      mergedValues.rsiPeriod = INITIAL_VALUES.rsiPeriod;
    }

    if (!Number.isFinite(oversoldThreshold) || oversoldThreshold <= 0 || oversoldThreshold >= 50) {
      mergedValues.oversoldThreshold = INITIAL_VALUES.oversoldThreshold;
    }

    if (
      !Number.isFinite(overboughtThreshold) ||
      overboughtThreshold <= 50 ||
      overboughtThreshold >= 100
    ) {
      mergedValues.overboughtThreshold = INITIAL_VALUES.overboughtThreshold;
    }
  }

  return mergedValues;
}

function parseInteger(value: string): number | null {
  const parsedValue = Number(value);

  if (!Number.isInteger(parsedValue)) {
    return null;
  }

  return parsedValue;
}

function parseDecimal(value: string): number | null {
  if (!value.trim()) {
    return null;
  }

  const parsedValue = Number(value);

  if (!Number.isFinite(parsedValue)) {
    return null;
  }

  return parsedValue;
}

export default function ExperimentRunForm({
  locale,
  initialValues,
  initialExecutionId,
  onCreated,
}: ExperimentRunFormProps) {
  const copy = getExperimentRunCopy(locale);
  const { push, replace } = useRouter();
  const direction = locale === 'fa' ? 'rtl' : 'ltr';

  const [datasets, setDatasets] = useState<DatasetSummary[]>([]);
  const [values, setValues] = useState<FormValues>(() => buildInitialFormValues(initialValues));
  const [isLoadingDatasets, setIsLoadingDatasets] = useState(true);
  const [hasDatasetError, setHasDatasetError] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(() => Boolean(initialExecutionId));
  const [formError, setFormError] = useState<string | null>(null);
  const [createdExperimentId, setCreatedExperimentId] = useState<string | null>(null);
  const [execution, setExecution] = useState<ExperimentExecution | null>(null);
  const pollingControllerRef = useRef<AbortController | null>(null);
  const pollingTimeoutRef = useRef<number | null>(null);

  const selectedDataset = useMemo(
    () => datasets.find((dataset) => dataset.dataset_id === values.datasetId) ?? null,
    [datasets, values.datasetId],
  );

  const loadDatasets = useCallback(async (): Promise<void> => {
    setIsLoadingDatasets(true);
    setHasDatasetError(false);

    try {
      const result = await fetchAvailableDatasets();
      setDatasets(result.items);
    } catch {
      setHasDatasetError(true);
    } finally {
      setIsLoadingDatasets(false);
    }
  }, []);

  useEffect(() => {
    let isActive = true;

    void fetchAvailableDatasets()
      .then((result) => {
        if (!isActive) {
          return;
        }

        setDatasets(result.items);
        setHasDatasetError(false);
      })
      .catch(() => {
        if (isActive) {
          setHasDatasetError(true);
        }
      })
      .finally(() => {
        if (isActive) {
          setIsLoadingDatasets(false);
        }
      });

    return () => {
      isActive = false;
    };
  }, []);

  const stopPolling = useCallback((): void => {
    pollingControllerRef.current?.abort();
    pollingControllerRef.current = null;

    if (pollingTimeoutRef.current !== null) {
      window.clearTimeout(pollingTimeoutRef.current);
      pollingTimeoutRef.current = null;
    }
  }, []);

  useEffect(() => stopPolling, [stopPolling]);

  function updateValue<Key extends keyof FormValues>(key: Key, value: FormValues[Key]): void {
    setValues((currentValues) => ({
      ...currentValues,
      [key]: value,
    }));

    setFormError(null);
    setCreatedExperimentId(null);
    setExecution(null);
    stopPolling();
  }

  function buildRequest(): BuiltExperimentRequest | null {
    const horizonCandles = parseInteger(values.horizonCandles);
    const startingBalance = parseDecimal(values.startingBalance);
    const allocationFraction = parseDecimal(values.allocationFraction);
    const feeRate = parseDecimal(values.feeRate);
    const slippageRate = parseDecimal(values.slippageRate);

    if (!values.datasetId || selectedDataset === null) {
      setFormError(copy.errors.datasetRequired);
      return null;
    }

    if (horizonCandles === null || horizonCandles < 1) {
      setFormError(copy.errors.invalidHorizon);
      return null;
    }

    if (startingBalance === null || startingBalance <= 0) {
      setFormError(copy.errors.invalidStartingBalance);
      return null;
    }

    if (allocationFraction === null || allocationFraction <= 0 || allocationFraction > 1) {
      setFormError(copy.errors.invalidAllocation);
      return null;
    }

    if (feeRate === null || feeRate < 0 || feeRate >= 1) {
      setFormError(copy.errors.invalidFee);
      return null;
    }

    if (slippageRate === null || slippageRate < 0 || slippageRate >= 1) {
      setFormError(copy.errors.invalidSlippage);
      return null;
    }

    const sharedRequest = {
      dataset_id: selectedDataset.dataset_id,
      horizon_candles: horizonCandles,
      starting_balance: values.startingBalance.trim(),
      allocation_fraction: values.allocationFraction.trim(),
      fee_rate: values.feeRate.trim(),
      slippage_rate: values.slippageRate.trim(),
    };

    if (values.strategyName === 'ema-crossover') {
      const fastPeriod = parseInteger(values.fastPeriod);
      const slowPeriod = parseInteger(values.slowPeriod);

      if (fastPeriod === null || fastPeriod < 2) {
        setFormError(copy.errors.invalidFastPeriod);
        return null;
      }

      if (slowPeriod === null || slowPeriod < 3) {
        setFormError(copy.errors.invalidSlowPeriod);
        return null;
      }

      if (slowPeriod <= fastPeriod) {
        setFormError(copy.errors.slowMustBeGreater);
        return null;
      }

      if (selectedDataset.candle_count < slowPeriod + horizonCandles) {
        setFormError(copy.errors.insufficientCandles);
        return null;
      }

      return {
        strategyName: 'ema-crossover',
        request: {
          ...sharedRequest,
          fast_period: fastPeriod,
          slow_period: slowPeriod,
        },
      };
    }

    const rsiPeriod = parseInteger(values.rsiPeriod);
    const oversoldThreshold = parseDecimal(values.oversoldThreshold);
    const overboughtThreshold = parseDecimal(values.overboughtThreshold);

    if (rsiPeriod === null || rsiPeriod < 2) {
      setFormError(copy.errors.invalidRsiPeriod);
      return null;
    }

    if (oversoldThreshold === null || oversoldThreshold <= 0 || oversoldThreshold >= 50) {
      setFormError(copy.errors.invalidOversoldThreshold);
      return null;
    }

    if (overboughtThreshold === null || overboughtThreshold <= 50 || overboughtThreshold >= 100) {
      setFormError(copy.errors.invalidOverboughtThreshold);
      return null;
    }

    if (selectedDataset.candle_count < rsiPeriod + horizonCandles + 1) {
      setFormError(copy.errors.insufficientCandles);
      return null;
    }

    return {
      strategyName: 'rsi-threshold',
      request: {
        ...sharedRequest,
        period: rsiPeriod,
        oversold_threshold: values.oversoldThreshold.trim(),
        overbought_threshold: values.overboughtThreshold.trim(),
      },
    };
  }

  const pollExecution = useCallback(
    async function pollExperimentExecution(
      executionId: string,
      signal: AbortSignal,
    ): Promise<void> {
      try {
        const currentExecution = await getExperimentExecution(executionId);

        if (signal.aborted) {
          return;
        }

        setExecution(currentExecution);

        if (currentExecution.status === 'succeeded') {
          if (!currentExecution.experiment_id) {
            setFormError(copy.errors.executionFailed);
            setIsSubmitting(false);
            return;
          }

          const experimentId = currentExecution.experiment_id;

          setCreatedExperimentId(experimentId);

          onCreated?.({
            experiment_id: experimentId,
          });

          setIsSubmitting(false);
          pollingControllerRef.current = null;

          push(`/${locale}/experiments/${encodeURIComponent(experimentId)}`);

          return;
        }

        if (currentExecution.status === 'failed') {
          setFormError(copy.errors.executionFailed);
          setIsSubmitting(false);
          pollingControllerRef.current = null;
          return;
        }

        pollingTimeoutRef.current = window.setTimeout(() => {
          void pollExperimentExecution(executionId, signal);
        }, POLLING_INTERVAL_MS);
      } catch {
        if (signal.aborted) {
          return;
        }

        setFormError(copy.errors.statusUnavailable);
        setIsSubmitting(false);
        pollingControllerRef.current = null;
      }
    },
    [copy.errors.executionFailed, copy.errors.statusUnavailable, locale, onCreated, push],
  );

  useEffect(() => {
    if (!initialExecutionId) {
      return;
    }

    const pollingController = new AbortController();

    pollingControllerRef.current = pollingController;

    void pollExecution(initialExecutionId, pollingController.signal);

    return stopPolling;
  }, [initialExecutionId, pollExecution, stopPolling]);

  async function submitForm(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();

    const builtRequest = buildRequest();

    if (builtRequest === null) {
      return;
    }

    stopPolling();

    setIsSubmitting(true);
    setFormError(null);
    setCreatedExperimentId(null);
    setExecution(null);

    try {
      const queuedExecution =
        builtRequest.strategyName === 'ema-crossover'
          ? await createEmaCrossoverExperimentExecution(builtRequest.request)
          : await createRsiThresholdExperimentExecution(builtRequest.request);

      setExecution(queuedExecution);

      replace(
        `/${locale}/experiments?execution=${encodeURIComponent(queuedExecution.execution_id)}`,
      );

      const pollingController = new AbortController();

      pollingControllerRef.current = pollingController;

      void pollExecution(queuedExecution.execution_id, pollingController.signal);
    } catch (error) {
      setIsSubmitting(false);

      if (error instanceof ApiRequestError) {
        if (error.status === 404) {
          setFormError(copy.errors.datasetNotFound);
        } else if (error.status === 409 || error.status === 422) {
          setFormError(copy.errors.validationFailed);
        } else {
          setFormError(copy.errors.generic);
        }
      } else {
        setFormError(copy.errors.generic);
      }
    }
  }

  const isExecutionActive = execution?.status === 'queued' || execution?.status === 'running';

  const isFormDisabled =
    isLoadingDatasets ||
    hasDatasetError ||
    datasets.length === 0 ||
    isSubmitting ||
    isExecutionActive;

  return (
    <Card>
      <CardHeader className="border-b border-app-border">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0 flex-1">
            <p className="text-xs font-semibold tracking-[0.22em] text-app-accent uppercase">
              {copy.eyebrow}
            </p>

            <CardTitle className="mt-3">{copy.title}</CardTitle>

            <CardDescription className="mt-2 max-w-3xl leading-7">
              {copy.description}
            </CardDescription>
          </div>

          <Badge variant="warning">{copy.historicalOnly}</Badge>
        </div>
      </CardHeader>

      <CardContent className="pt-6">
        {isLoadingDatasets ? (
          <div className="flex min-h-32 items-center justify-center">
            <Spinner label={copy.states.loadingDatasets} className="text-app-accent" />
          </div>
        ) : hasDatasetError ? (
          <div role="alert" className="rounded-2xl border border-rose-500/20 bg-rose-500/5 p-5">
            <p className="text-sm text-rose-600">{copy.states.datasetLoadError}</p>

            <Button
              type="button"
              variant="secondary"
              className="mt-4 w-full sm:w-auto"
              onClick={() => void loadDatasets()}
            >
              {copy.actions.retryDatasets}
            </Button>
          </div>
        ) : datasets.length === 0 ? (
          <div className="rounded-2xl border border-app-border bg-app-surface-muted p-5">
            <p className="text-sm leading-7 text-app-muted">{copy.states.noDatasets}</p>
          </div>
        ) : (
          <form onSubmit={(event) => void submitForm(event)} className="space-y-6">
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
              <div className="min-w-0 md:col-span-2">
                <Select
                  dir={direction}
                  label={copy.fields.dataset}
                  value={values.datasetId}
                  disabled={isFormDisabled}
                  onValueChange={(value) => updateValue('datasetId', value)}
                >
                  <SelectOption value="">{copy.fields.datasetPlaceholder}</SelectOption>

                  {datasets.map((dataset) => (
                    <SelectOption key={dataset.dataset_id} value={dataset.dataset_id}>
                      {dataset.name} · {dataset.pair.base_asset}/{dataset.pair.quote_asset} ·{' '}
                      {dataset.timeframe}
                    </SelectOption>
                  ))}
                </Select>
              </div>

              <Select
                dir={direction}
                label={copy.fields.strategy}
                value={values.strategyName}
                disabled={isFormDisabled}
                onValueChange={(value) =>
                  updateValue('strategyName', value as ResearchStrategyName)
                }
              >
                <SelectOption value="ema-crossover">{copy.strategy.emaCrossover}</SelectOption>
                <SelectOption value="rsi-threshold">{copy.strategy.rsiThreshold}</SelectOption>
              </Select>

              <Input
                dir="ltr"
                type="number"
                label={copy.fields.horizonCandles}
                value={values.horizonCandles}
                min={1}
                step={1}
                disabled={isFormDisabled}
                className="text-left"
                onChange={(event) => updateValue('horizonCandles', event.target.value)}
              />

              {values.strategyName === 'ema-crossover' ? (
                <>
                  <Input
                    dir="ltr"
                    type="number"
                    label={copy.fields.fastPeriod}
                    value={values.fastPeriod}
                    min={2}
                    step={1}
                    disabled={isFormDisabled}
                    className="text-left"
                    onChange={(event) => updateValue('fastPeriod', event.target.value)}
                  />

                  <Input
                    dir="ltr"
                    type="number"
                    label={copy.fields.slowPeriod}
                    value={values.slowPeriod}
                    min={3}
                    step={1}
                    disabled={isFormDisabled}
                    className="text-left"
                    onChange={(event) => updateValue('slowPeriod', event.target.value)}
                  />
                </>
              ) : (
                <>
                  <Input
                    dir="ltr"
                    type="number"
                    label={copy.fields.rsiPeriod}
                    value={values.rsiPeriod}
                    min={2}
                    step={1}
                    disabled={isFormDisabled}
                    className="text-left"
                    onChange={(event) => updateValue('rsiPeriod', event.target.value)}
                  />

                  <Input
                    dir="ltr"
                    type="number"
                    label={copy.fields.oversoldThreshold}
                    value={values.oversoldThreshold}
                    min="0.000001"
                    max="49.999999"
                    step="any"
                    disabled={isFormDisabled}
                    className="text-left"
                    onChange={(event) => updateValue('oversoldThreshold', event.target.value)}
                  />

                  <Input
                    dir="ltr"
                    type="number"
                    label={copy.fields.overboughtThreshold}
                    value={values.overboughtThreshold}
                    min="50.000001"
                    max="99.999999"
                    step="any"
                    disabled={isFormDisabled}
                    className="text-left"
                    onChange={(event) => updateValue('overboughtThreshold', event.target.value)}
                  />
                </>
              )}

              <Input
                dir="ltr"
                type="number"
                label={copy.fields.startingBalance}
                value={values.startingBalance}
                min="0.01"
                step="any"
                disabled={isFormDisabled}
                className="text-left"
                onChange={(event) => updateValue('startingBalance', event.target.value)}
              />

              <Input
                dir="ltr"
                type="number"
                label={copy.fields.allocationFraction}
                value={values.allocationFraction}
                min="0.000001"
                max="1"
                step="any"
                disabled={isFormDisabled}
                className="text-left"
                onChange={(event) => updateValue('allocationFraction', event.target.value)}
              />

              <Input
                dir="ltr"
                type="number"
                label={copy.fields.feeRate}
                value={values.feeRate}
                min="0"
                max="0.999999"
                step="any"
                disabled={isFormDisabled}
                className="text-left"
                onChange={(event) => updateValue('feeRate', event.target.value)}
              />

              <Input
                dir="ltr"
                type="number"
                label={copy.fields.slippageRate}
                value={values.slippageRate}
                min="0"
                max="0.999999"
                step="any"
                disabled={isFormDisabled}
                className="text-left"
                onChange={(event) => updateValue('slippageRate', event.target.value)}
              />
            </div>

            {selectedDataset ? (
              <div className="rounded-2xl border border-app-accent-border bg-app-accent-soft p-5">
                <p className="font-semibold text-app-accent">{copy.selectedDataset.title}</p>

                <dl className="mt-4 grid gap-4 text-sm sm:grid-cols-2 xl:grid-cols-4">
                  <div>
                    <dt className="text-app-muted">{copy.selectedDataset.pair}</dt>
                    <dd dir="ltr" className="mt-1 text-app-foreground">
                      {selectedDataset.pair.base_asset}/{selectedDataset.pair.quote_asset}
                    </dd>
                  </div>

                  <div>
                    <dt className="text-app-muted">{copy.selectedDataset.timeframe}</dt>
                    <dd dir="ltr" className="mt-1 text-app-foreground">
                      {selectedDataset.timeframe}
                    </dd>
                  </div>

                  <div>
                    <dt className="text-app-muted">{copy.selectedDataset.candles}</dt>
                    <dd className="mt-1 text-app-foreground">
                      {new Intl.NumberFormat(locale === 'fa' ? 'fa-IR' : 'en-US').format(
                        selectedDataset.candle_count,
                      )}
                    </dd>
                  </div>

                  <div className="min-w-0">
                    <dt className="text-app-muted">{copy.selectedDataset.source}</dt>
                    <dd className="mt-1 truncate text-app-foreground">{selectedDataset.source}</dd>
                  </div>
                </dl>
              </div>
            ) : null}

            {execution && isExecutionActive ? (
              <div
                role="status"
                aria-live="polite"
                className="rounded-2xl border border-app-accent-border bg-app-accent-soft p-5"
              >
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="flex items-center gap-3">
                    <Spinner
                      label={
                        execution.status === 'queued' ? copy.states.queued : copy.states.running
                      }
                      className="text-app-accent"
                    />

                    <p className="text-sm font-medium text-app-accent">
                      {execution.status === 'queued' ? copy.states.queued : copy.states.running}
                    </p>
                  </div>

                  <span dir="ltr" className="text-sm font-semibold text-app-accent">
                    {execution.progress_percent}%
                  </span>
                </div>

                <div className="mt-4">
                  <div className="mb-2 flex flex-col items-start gap-2 text-xs text-app-muted sm:flex-row sm:items-center sm:justify-between">
                    <span>{copy.states.progress}</span>

                    <span dir="ltr" className="w-full text-left break-all sm:w-auto sm:text-end">
                      {execution.execution_id}
                    </span>
                  </div>

                  <div
                    role="progressbar"
                    aria-label={copy.states.progress}
                    aria-valuemin={0}
                    aria-valuemax={100}
                    aria-valuenow={execution.progress_percent}
                    className="h-2 overflow-hidden rounded-full bg-app-border"
                  >
                    <div
                      className="h-full rounded-full bg-app-accent transition-[width] duration-500 ease-out"
                      style={{
                        width: `${execution.progress_percent}%`,
                      }}
                    />
                  </div>
                </div>
              </div>
            ) : null}

            {formError ? (
              <p
                role="alert"
                className="rounded-xl border border-rose-500/20 bg-rose-500/5 px-4 py-3 text-sm break-words text-rose-600"
              >
                {formError}
              </p>
            ) : null}

            {createdExperimentId ? (
              <div
                role="status"
                className="flex flex-col items-stretch gap-4 rounded-xl border border-emerald-500/20 bg-emerald-500/5 px-4 py-3 sm:flex-row sm:items-center sm:justify-between"
              >
                <p className="min-w-0 text-sm break-words text-emerald-600">
                  {copy.states.success}
                </p>

                <Link
                  href={`/${locale}/experiments/${encodeURIComponent(createdExperimentId)}`}
                  className="inline-flex w-full items-center justify-center rounded-md text-center text-sm font-semibold text-emerald-600 transition hover:text-emerald-700 focus-visible:ring-2 focus-visible:ring-app-accent focus-visible:ring-offset-2 focus-visible:ring-offset-app-background focus-visible:outline-none sm:w-auto"
                >
                  {copy.actions.viewResult}
                </Link>
              </div>
            ) : null}

            <Button
              type="submit"
              isLoading={isSubmitting}
              loadingText={
                execution?.status === 'queued' ? copy.actions.queued : copy.actions.running
              }
              disabled={isFormDisabled}
              className="w-full sm:w-auto"
            >
              {copy.actions.run}
            </Button>
          </form>
        )}
      </CardContent>
    </Card>
  );
}
