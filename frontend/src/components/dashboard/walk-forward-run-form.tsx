'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from 'react';

import type { DashboardLocale } from '@/components/dashboard/dashboard-copy';
import { getWalkForwardRunCopy } from '@/components/dashboard/walk-forward-run-copy';
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
  createWalkForwardExecution,
  getDatasets,
  getResearchStrategies,
  getWalkForwardExecution,
} from '@/lib/api/client';
import type {
  DatasetSummary,
  ResearchStrategyMetadata,
  ResearchStrategyName,
  StoredDatasetStrategyWalkForwardExecutionRequest,
  WalkForwardExecution,
  WalkForwardMode,
} from '@/lib/api/types';
import {
  findStrategyMetadata,
  getExecutableResearchStrategies,
  getStrategyParameterDefault,
  getStrategyParameterInputProps,
  isExecutableResearchStrategyName,
  isMovingAverageCrossoverStrategyName,
  isStrategyParameterValueValid,
} from '@/lib/strategies/catalog';
import { getStrategyDisplayName } from '@/lib/strategies/presentation';
import { estimateWalkForwardFoldCount } from '@/lib/walk-forward/fold-estimate';
import type { WalkForwardRunInitialValues } from '@/lib/walk-forward/run-params';

type WalkForwardRunFormProps = {
  locale: DashboardLocale;
  initialValues?: WalkForwardRunInitialValues;
  initialExecutionId?: string;
};

type FormValues = {
  datasetId: string;
  strategyName: ResearchStrategyName;
  mode: WalkForwardMode;
  fastPeriod: string;
  slowPeriod: string;
  rsiPeriod: string;
  oversoldThreshold: string;
  overboughtThreshold: string;
  horizonCandles: string;
  trainCandles: string;
  testCandles: string;
  stepCandles: string;
  gapCandles: string;
  startingBalance: string;
  allocationFraction: string;
  feeRate: string;
  slippageRate: string;
};

type NumericField = {
  key: Exclude<keyof FormValues, 'datasetId' | 'strategyName' | 'mode'>;
  label: string;
  min?: number | string;
  max?: number | string;
  step: number | string;
};

const INITIAL_VALUES: FormValues = {
  datasetId: '',
  strategyName: 'ema-crossover',
  mode: 'rolling',
  fastPeriod: '',
  slowPeriod: '',
  rsiPeriod: '',
  oversoldThreshold: '',
  overboughtThreshold: '',
  horizonCandles: '1',
  trainCandles: '120',
  testCandles: '24',
  stepCandles: '24',
  gapCandles: '0',
  startingBalance: '10000',
  allocationFraction: '0.10',
  feeRate: '0.001',
  slippageRate: '0.0005',
};

type BuiltWalkForwardRequest = StoredDatasetStrategyWalkForwardExecutionRequest;

const POLLING_INTERVAL_MS = 1000;

function fetchAvailableDatasets() {
  return getDatasets({
    sortBy: 'created_at',
    sortDirection: 'desc',
    limit: 100,
    offset: 0,
  });
}

function resolveStrategyParameterValue(
  strategy: ResearchStrategyMetadata,
  parameterName: string,
  currentValue: string,
): string {
  if (isStrategyParameterValueValid(strategy, parameterName, currentValue)) {
    return currentValue;
  }

  return getStrategyParameterDefault(strategy, parameterName) ?? '';
}

function applyStrategyCatalogDefaults(
  values: FormValues,
  catalog: ResearchStrategyMetadata[],
): FormValues {
  const strategy = findStrategyMetadata(catalog, values.strategyName);

  if (strategy === null) {
    return values;
  }

  if (isMovingAverageCrossoverStrategyName(values.strategyName)) {
    let fastPeriod = resolveStrategyParameterValue(strategy, 'fast_period', values.fastPeriod);
    let slowPeriod = resolveStrategyParameterValue(strategy, 'slow_period', values.slowPeriod);

    if (Number(slowPeriod) <= Number(fastPeriod)) {
      fastPeriod = getStrategyParameterDefault(strategy, 'fast_period') ?? '';
      slowPeriod = getStrategyParameterDefault(strategy, 'slow_period') ?? '';
    }

    return {
      ...values,
      fastPeriod,
      slowPeriod,
    };
  }

  return {
    ...values,
    rsiPeriod: resolveStrategyParameterValue(strategy, 'period', values.rsiPeriod),
    oversoldThreshold: resolveStrategyParameterValue(
      strategy,
      'oversold_threshold',
      values.oversoldThreshold,
    ),
    overboughtThreshold: resolveStrategyParameterValue(
      strategy,
      'overbought_threshold',
      values.overboughtThreshold,
    ),
  };
}

function parseInteger(value: string): number | null {
  if (!value.trim()) {
    return null;
  }

  const parsedValue = Number(value);
  return Number.isInteger(parsedValue) ? parsedValue : null;
}

function parseDecimal(value: string): number | null {
  if (!value.trim()) {
    return null;
  }

  const parsedValue = Number(value);
  return Number.isFinite(parsedValue) ? parsedValue : null;
}

export default function WalkForwardRunForm({
  locale,
  initialValues,
  initialExecutionId,
}: WalkForwardRunFormProps) {
  const copy = getWalkForwardRunCopy(locale);
  const { push, replace } = useRouter();
  const direction = locale === 'fa' ? 'rtl' : 'ltr';

  const [datasets, setDatasets] = useState<DatasetSummary[]>([]);
  const [strategies, setStrategies] = useState<ResearchStrategyMetadata[]>([]);
  const [values, setValues] = useState<FormValues>(() => ({
    ...INITIAL_VALUES,
    ...(initialValues?.strategyName === undefined
      ? {}
      : { strategyName: initialValues.strategyName }),
  }));
  const [isLoadingDatasets, setIsLoadingDatasets] = useState(true);
  const [hasDatasetError, setHasDatasetError] = useState(false);
  const [isLoadingStrategies, setIsLoadingStrategies] = useState(true);
  const [hasStrategyError, setHasStrategyError] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(() => Boolean(initialExecutionId));
  const [formError, setFormError] = useState<string | null>(null);
  const [execution, setExecution] = useState<WalkForwardExecution | null>(null);
  const [createdRunId, setCreatedRunId] = useState<string | null>(null);
  const pollingControllerRef = useRef<AbortController | null>(null);
  const pollingTimeoutRef = useRef<number | null>(null);

  const selectedDataset = useMemo(
    () => datasets.find((dataset) => dataset.dataset_id === values.datasetId) ?? null,
    [datasets, values.datasetId],
  );

  const selectedStrategy = useMemo(
    () => findStrategyMetadata(strategies, values.strategyName),
    [strategies, values.strategyName],
  );

  const estimatedFolds = useMemo(() => {
    if (!selectedDataset) {
      return null;
    }

    const trainCandles = parseInteger(values.trainCandles);
    const testCandles = parseInteger(values.testCandles);
    const stepCandles = parseInteger(values.stepCandles);
    const gapCandles = parseInteger(values.gapCandles);

    if (
      trainCandles === null ||
      testCandles === null ||
      stepCandles === null ||
      gapCandles === null
    ) {
      return null;
    }

    return estimateWalkForwardFoldCount(selectedDataset.candle_count, {
      trainCandles,
      testCandles,
      stepCandles,
      gapCandles,
    });
  }, [
    selectedDataset,
    values.gapCandles,
    values.stepCandles,
    values.testCandles,
    values.trainCandles,
  ]);

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

  const loadStrategies = useCallback(async (): Promise<void> => {
    setIsLoadingStrategies(true);
    setHasStrategyError(false);

    try {
      const result = getExecutableResearchStrategies(await getResearchStrategies());

      if (result.length === 0) {
        setHasStrategyError(true);
        return;
      }

      setStrategies(result);
      setValues((currentValues) => applyStrategyCatalogDefaults(currentValues, result));
    } catch {
      setHasStrategyError(true);
    } finally {
      setIsLoadingStrategies(false);
    }
  }, []);

  useEffect(() => {
    let isActive = true;

    void fetchAvailableDatasets()
      .then((result) => {
        if (isActive) {
          setDatasets(result.items);
          setHasDatasetError(false);
        }
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

  useEffect(() => {
    void loadStrategies();
  }, [loadStrategies]);

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
    setExecution(null);
    setCreatedRunId(null);
    stopPolling();
  }

  function updateStrategyName(value: string): void {
    if (!isExecutableResearchStrategyName(value)) {
      return;
    }

    setValues((currentValues) =>
      applyStrategyCatalogDefaults(
        {
          ...currentValues,
          strategyName: value,
        },
        strategies,
      ),
    );
    setFormError(null);
    setExecution(null);
    setCreatedRunId(null);
    stopPolling();
  }

  function buildRequest(): BuiltWalkForwardRequest | null {
    const horizonCandles = parseInteger(values.horizonCandles);
    const trainCandles = parseInteger(values.trainCandles);
    const testCandles = parseInteger(values.testCandles);
    const stepCandles = parseInteger(values.stepCandles);
    const gapCandles = parseInteger(values.gapCandles);
    const startingBalance = parseDecimal(values.startingBalance);
    const allocationFraction = parseDecimal(values.allocationFraction);
    const feeRate = parseDecimal(values.feeRate);
    const slippageRate = parseDecimal(values.slippageRate);

    if (!values.datasetId || selectedDataset === null) {
      setFormError(copy.errors.datasetRequired);
      return null;
    }
    if (selectedStrategy === null) {
      setFormError(copy.errors.strategyUnavailable);
      return null;
    }
    if (horizonCandles === null || horizonCandles < 1) {
      setFormError(copy.errors.invalidHorizon);
      return null;
    }
    if (trainCandles === null || trainCandles < 2) {
      setFormError(copy.errors.invalidTrain);
      return null;
    }
    if (testCandles === null || testCandles < 1) {
      setFormError(copy.errors.invalidTest);
      return null;
    }
    if (stepCandles === null || stepCandles < 1) {
      setFormError(copy.errors.invalidStep);
      return null;
    }
    if (stepCandles < testCandles) {
      setFormError(copy.errors.stepBeforeTest);
      return null;
    }
    if (gapCandles === null || gapCandles < 0) {
      setFormError(copy.errors.invalidGap);
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

    const foldCount = estimateWalkForwardFoldCount(selectedDataset.candle_count, {
      trainCandles,
      testCandles,
      stepCandles,
      gapCandles,
    });

    if (foldCount === 0) {
      setFormError(copy.errors.insufficientCandles);
      return null;
    }

    const sharedRequest = {
      dataset_id: selectedDataset.dataset_id,
      horizon_candles: horizonCandles,
      train_candles: trainCandles,
      test_candles: testCandles,
      step_candles: stepCandles,
      gap_candles: gapCandles,
      mode: values.mode,
      starting_balance: values.startingBalance.trim(),
      allocation_fraction: values.allocationFraction.trim(),
      fee_rate: values.feeRate.trim(),
      slippage_rate: values.slippageRate.trim(),
    };

    if (isMovingAverageCrossoverStrategyName(values.strategyName)) {
      const fastPeriod = parseInteger(values.fastPeriod);
      const slowPeriod = parseInteger(values.slowPeriod);

      if (
        fastPeriod === null ||
        !isStrategyParameterValueValid(selectedStrategy, 'fast_period', values.fastPeriod)
      ) {
        setFormError(copy.errors.invalidFastPeriod);
        return null;
      }
      if (
        slowPeriod === null ||
        !isStrategyParameterValueValid(selectedStrategy, 'slow_period', values.slowPeriod)
      ) {
        setFormError(copy.errors.invalidSlowPeriod);
        return null;
      }
      if (slowPeriod <= fastPeriod) {
        setFormError(copy.errors.slowMustBeGreater);
        return null;
      }

      const strategyRequest = {
        ...sharedRequest,
        strategy_version: '1.0.0' as const,
        fast_period: fastPeriod,
        slow_period: slowPeriod,
      };

      if (values.strategyName === 'sma-crossover') {
        return {
          ...strategyRequest,
          strategy_name: 'sma-crossover',
        };
      }

      return {
        ...strategyRequest,
        strategy_name: 'ema-crossover',
      };
    }

    const rsiPeriod = parseInteger(values.rsiPeriod);
    const oversoldThreshold = parseDecimal(values.oversoldThreshold);
    const overboughtThreshold = parseDecimal(values.overboughtThreshold);

    if (
      rsiPeriod === null ||
      !isStrategyParameterValueValid(selectedStrategy, 'period', values.rsiPeriod)
    ) {
      setFormError(copy.errors.invalidRsiPeriod);
      return null;
    }
    if (
      oversoldThreshold === null ||
      !isStrategyParameterValueValid(
        selectedStrategy,
        'oversold_threshold',
        values.oversoldThreshold,
      )
    ) {
      setFormError(copy.errors.invalidOversoldThreshold);
      return null;
    }
    if (
      overboughtThreshold === null ||
      !isStrategyParameterValueValid(
        selectedStrategy,
        'overbought_threshold',
        values.overboughtThreshold,
      )
    ) {
      setFormError(copy.errors.invalidOverboughtThreshold);
      return null;
    }

    return {
      ...sharedRequest,
      strategy_name: 'rsi-threshold',
      strategy_version: '1.0.0',
      period: rsiPeriod,
      oversold_threshold: values.oversoldThreshold.trim(),
      overbought_threshold: values.overboughtThreshold.trim(),
    };
  }

  const pollExecution = useCallback(
    async function pollWalkForwardExecution(
      executionId: string,
      signal: AbortSignal,
    ): Promise<void> {
      try {
        const currentExecution = await getWalkForwardExecution(executionId);

        if (signal.aborted) {
          return;
        }

        setExecution(currentExecution);

        if (currentExecution.status === 'succeeded') {
          if (!currentExecution.walk_forward_run_id) {
            setFormError(copy.errors.missingResult);
            setIsSubmitting(false);
            return;
          }

          const runId = currentExecution.walk_forward_run_id;

          setCreatedRunId(runId);
          setIsSubmitting(false);
          pollingControllerRef.current = null;

          push('/' + locale + '/walk-forward/' + encodeURIComponent(runId));
          return;
        }

        if (currentExecution.status === 'failed') {
          setFormError(copy.errors.executionFailed);
          setIsSubmitting(false);
          pollingControllerRef.current = null;
          return;
        }

        pollingTimeoutRef.current = window.setTimeout(() => {
          void pollWalkForwardExecution(executionId, signal);
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
    [
      copy.errors.executionFailed,
      copy.errors.missingResult,
      copy.errors.statusUnavailable,
      locale,
      push,
    ],
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
    setExecution(null);
    setCreatedRunId(null);

    try {
      const queuedExecution = await createWalkForwardExecution(builtRequest);

      setExecution(queuedExecution);
      replace(
        '/' +
          locale +
          '/walk-forward?execution=' +
          encodeURIComponent(queuedExecution.execution_id),
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
    isLoadingStrategies ||
    hasDatasetError ||
    hasStrategyError ||
    datasets.length === 0 ||
    strategies.length === 0 ||
    selectedStrategy === null ||
    isSubmitting ||
    isExecutionActive;
  const numberFormatter = new Intl.NumberFormat(locale === 'fa' ? 'fa-IR' : 'en-US');
  const strategyFields: NumericField[] = isMovingAverageCrossoverStrategyName(values.strategyName)
    ? [
        {
          key: 'fastPeriod',
          label: copy.fields.fastPeriod,
          ...(selectedStrategy === null
            ? { min: 0, step: 1 }
            : getStrategyParameterInputProps(selectedStrategy, 'fast_period')),
        },
        {
          key: 'slowPeriod',
          label: copy.fields.slowPeriod,
          ...(selectedStrategy === null
            ? { min: 0, step: 1 }
            : getStrategyParameterInputProps(selectedStrategy, 'slow_period')),
        },
      ]
    : [
        {
          key: 'rsiPeriod',
          label: copy.fields.rsiPeriod,
          ...(selectedStrategy === null
            ? { min: 0, step: 1 }
            : getStrategyParameterInputProps(selectedStrategy, 'period')),
        },
        {
          key: 'oversoldThreshold',
          label: copy.fields.oversoldThreshold,
          ...(selectedStrategy === null
            ? { min: 0, step: 'any' }
            : getStrategyParameterInputProps(selectedStrategy, 'oversold_threshold')),
        },
        {
          key: 'overboughtThreshold',
          label: copy.fields.overboughtThreshold,
          ...(selectedStrategy === null
            ? { min: 0, step: 'any' }
            : getStrategyParameterInputProps(selectedStrategy, 'overbought_threshold')),
        },
      ];

  const numericFields: NumericField[] = [
    ...strategyFields,
    { key: 'horizonCandles', label: copy.fields.horizonCandles, min: 1, step: 1 },
    { key: 'trainCandles', label: copy.fields.trainCandles, min: 2, step: 1 },
    { key: 'testCandles', label: copy.fields.testCandles, min: 1, step: 1 },
    { key: 'stepCandles', label: copy.fields.stepCandles, min: 1, step: 1 },
    { key: 'gapCandles', label: copy.fields.gapCandles, min: 0, step: 1 },
    { key: 'startingBalance', label: copy.fields.startingBalance, min: '0.01', step: 'any' },
    {
      key: 'allocationFraction',
      label: copy.fields.allocationFraction,
      min: '0.000001',
      max: 1,
      step: 'any',
    },
    { key: 'feeRate', label: copy.fields.feeRate, min: 0, max: '0.999999', step: 'any' },
    {
      key: 'slippageRate',
      label: copy.fields.slippageRate,
      min: 0,
      max: '0.999999',
      step: 'any',
    },
  ];

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
        {isLoadingDatasets || isLoadingStrategies ? (
          <div className="flex min-h-32 items-center justify-center">
            <Spinner
              label={
                isLoadingDatasets ? copy.states.loadingDatasets : copy.states.loadingStrategies
              }
              className="text-app-accent"
            />
          </div>
        ) : hasDatasetError ? (
          <div role="alert" className="rounded-2xl border border-rose-500/20 bg-rose-500/5 p-5">
            <p className="text-sm text-rose-500">{copy.states.datasetLoadError}</p>
            <Button
              type="button"
              variant="secondary"
              className="mt-4 w-full sm:w-auto"
              onClick={() => void loadDatasets()}
            >
              {copy.actions.retryDatasets}
            </Button>
          </div>
        ) : hasStrategyError ? (
          <div role="alert" className="rounded-2xl border border-rose-500/20 bg-rose-500/5 p-5">
            <p className="text-sm text-rose-500">{copy.states.strategyLoadError}</p>
            <Button
              type="button"
              variant="secondary"
              className="mt-4 w-full sm:w-auto"
              onClick={() => void loadStrategies()}
            >
              {copy.actions.retryStrategies}
            </Button>
          </div>
        ) : datasets.length === 0 ? (
          <p className="rounded-2xl border border-app-border bg-app-surface-muted p-5 text-sm text-app-muted">
            {copy.states.noDatasets}
          </p>
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
                onValueChange={updateStrategyName}
              >
                {strategies.map((strategy) => (
                  <SelectOption key={`${strategy.name}@${strategy.version}`} value={strategy.name}>
                    {getStrategyDisplayName(strategy.name, locale)} · v{strategy.version}
                  </SelectOption>
                ))}
              </Select>

              <Select
                dir={direction}
                label={copy.fields.mode}
                value={values.mode}
                disabled={isFormDisabled}
                onValueChange={(value) => updateValue('mode', value as WalkForwardMode)}
              >
                <SelectOption value="rolling">{copy.modes.rolling}</SelectOption>
                <SelectOption value="expanding">{copy.modes.expanding}</SelectOption>
              </Select>

              {numericFields.map((field) => (
                <Input
                  key={field.key}
                  dir="ltr"
                  type="number"
                  label={field.label}
                  value={values[field.key]}
                  min={field.min}
                  max={field.max}
                  step={field.step}
                  disabled={isFormDisabled}
                  className="text-left"
                  onChange={(event) => updateValue(field.key, event.target.value)}
                />
              ))}
            </div>

            {selectedDataset ? (
              <div className="rounded-2xl border border-app-accent-border bg-app-accent-soft p-5">
                <p className="font-semibold text-app-accent">{copy.estimate.title}</p>
                <dl className="mt-4 grid gap-4 text-sm sm:grid-cols-2">
                  <div>
                    <dt className="text-app-muted">{copy.estimate.candles}</dt>
                    <dd className="mt-1 text-app-foreground">
                      {numberFormatter.format(selectedDataset.candle_count)}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-app-muted">{copy.estimate.folds}</dt>
                    <dd className="mt-1 text-app-foreground">
                      {estimatedFolds === null
                        ? copy.estimate.unavailable
                        : numberFormatter.format(estimatedFolds)}
                    </dd>
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
                <div className="flex flex-col items-start gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <div className="flex min-w-0 items-center gap-3">
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
                  <div className="mb-2 flex flex-col items-start gap-1 text-xs text-app-muted sm:flex-row sm:items-center sm:justify-between">
                    <span>{copy.states.progress}</span>
                    <span>
                      {copy.states.foldsCompleted}:{' '}
                      {numberFormatter.format(execution.completed_folds)}/
                      {numberFormatter.format(execution.total_folds)}
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
                      style={{ width: execution.progress_percent + '%' }}
                    />
                  </div>
                  <p
                    dir="ltr"
                    className="mt-3 text-left text-xs font-semibold break-all text-app-muted"
                  >
                    {execution.execution_id}
                  </p>
                </div>
              </div>
            ) : null}

            {formError ? (
              <p
                role="alert"
                className="rounded-xl border border-rose-500/20 bg-rose-500/5 px-4 py-3 text-sm break-words text-rose-500"
              >
                {formError}
              </p>
            ) : null}

            {createdRunId ? (
              <div
                role="status"
                className="flex flex-col items-stretch gap-4 rounded-xl border border-emerald-500/20 bg-emerald-500/5 px-4 py-3 sm:flex-row sm:items-center sm:justify-between"
              >
                <p className="min-w-0 text-sm break-words text-emerald-500">
                  {copy.states.success}
                </p>
                <Link
                  href={'/' + locale + '/walk-forward/' + encodeURIComponent(createdRunId)}
                  className="inline-flex w-full items-center justify-center rounded-md text-center text-sm font-semibold text-emerald-500 transition hover:opacity-80 focus-visible:ring-2 focus-visible:ring-app-accent focus-visible:ring-offset-2 focus-visible:ring-offset-app-background focus-visible:outline-none sm:w-auto"
                >
                  {copy.actions.viewResult}
                </Link>
              </div>
            ) : null}

            <Button
              type="submit"
              isLoading={isSubmitting}
              loadingText={
                execution?.status === 'queued' ? copy.actions.queuing : copy.actions.running
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
