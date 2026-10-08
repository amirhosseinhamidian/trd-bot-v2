'use client';

import { useRouter } from 'next/navigation';
import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from 'react';

import type { PlatformLocale } from '@/platform/i18n';
import { getDatasets } from '@/features/datasets/api/client';
import type { DatasetSummary } from '@/features/datasets/api/types';
import type { ExperimentComparisonMetric } from '@/features/experiments/api/types';
import {
  createOptimizationExecution,
  getOptimizationExecution,
} from '@/features/optimizations/api/client';
import type {
  CreateOptimizationExecutionRequest,
  OptimizationExecution,
  OptimizationParameterGrid,
} from '@/features/optimizations/api/types';
import { getOptimizationCopy } from '@/features/optimizations/optimization-copy';
import { getResearchStrategies } from '@/features/strategies/api/client';
import type {
  ResearchStrategyMetadata,
  ResearchStrategyName,
} from '@/features/strategies/api/types';
import { getWalkForwardRunCopy } from '@/features/walk-forward/walk-forward-run-copy';
import type { WalkForwardMode } from '@/features/walk-forward/api/types';
import {
  Badge,
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  FormActionBar,
  Input,
  Select,
  SelectOption,
  Spinner,
} from '@/components/ui';
import { ApiRequestError } from '@/lib/api/core/transport';
import {
  estimateOptimizationGrid,
  isOptimizationGridValueValid,
  splitOptimizationGridValues,
} from '@/lib/optimizations/grid-estimate';
import {
  findStrategyMetadata,
  getExecutableResearchStrategies,
  isExecutableResearchStrategyName,
} from '@/lib/strategies/catalog';
import { getStrategyDisplayName, getStrategyParameterLabel } from '@/lib/strategies/presentation';
import { estimateWalkForwardFoldCount } from '@/lib/walk-forward/fold-estimate';

type OptimizationRunFormProps = {
  locale: PlatformLocale;
  initialExecutionId?: string;
};

type FormValues = {
  datasetId: string;
  strategyName: ResearchStrategyName;
  objective: ExperimentComparisonMetric;
  mode: WalkForwardMode;
  parameterGrids: Record<string, string>;
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

type NumericFieldKey = Exclude<
  keyof FormValues,
  'datasetId' | 'strategyName' | 'objective' | 'mode' | 'parameterGrids'
>;

const INITIAL_VALUES: FormValues = {
  datasetId: '',
  strategyName: 'ema-crossover',
  objective: 'excess_return',
  mode: 'rolling',
  parameterGrids: {},
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

const POLLING_INTERVAL_MS = 1000;

function parseInteger(value: string): number | null {
  const parsed = Number(value);
  return value.trim() && Number.isInteger(parsed) ? parsed : null;
}

function parseDecimal(value: string): number | null {
  const parsed = Number(value);
  return value.trim() && Number.isFinite(parsed) ? parsed : null;
}

function defaultParameterGrids(strategy: ResearchStrategyMetadata): Record<string, string> {
  return Object.fromEntries(
    strategy.parameters.map((parameter) => [parameter.name, parameter.default_value]),
  );
}

function canonicalGridValue(value: string): string {
  return String(Number(value));
}

function fetchAvailableDatasets() {
  return getDatasets({
    sortBy: 'created_at',
    sortDirection: 'desc',
    limit: 100,
    offset: 0,
  });
}

export default function OptimizationRunForm({
  locale,
  initialExecutionId,
}: OptimizationRunFormProps) {
  const copy = getOptimizationCopy(locale);
  const sharedCopy = getWalkForwardRunCopy(locale);
  const { push, replace } = useRouter();
  const direction = locale === 'fa' ? 'rtl' : 'ltr';
  const numberFormatter = useMemo(
    () => new Intl.NumberFormat(locale === 'fa' ? 'fa-IR' : 'en-US'),
    [locale],
  );

  const [datasets, setDatasets] = useState<DatasetSummary[]>([]);
  const [strategies, setStrategies] = useState<ResearchStrategyMetadata[]>([]);
  const [values, setValues] = useState<FormValues>(INITIAL_VALUES);
  const [isLoadingDatasets, setIsLoadingDatasets] = useState(true);
  const [hasDatasetError, setHasDatasetError] = useState(false);
  const [isLoadingStrategies, setIsLoadingStrategies] = useState(true);
  const [hasStrategyError, setHasStrategyError] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(() => Boolean(initialExecutionId));
  const [formError, setFormError] = useState<string | null>(null);
  const [execution, setExecution] = useState<OptimizationExecution | null>(null);
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

  const workloadEstimate = useMemo(() => {
    if (selectedDataset === null || selectedStrategy === null) {
      return null;
    }

    const grids = Object.fromEntries(
      selectedStrategy.parameters.map((parameter) => [
        parameter.name,
        splitOptimizationGridValues(values.parameterGrids[parameter.name] ?? ''),
      ]),
    );

    if (
      selectedStrategy.parameters.some((parameter) =>
        grids[parameter.name].some(
          (value) => !isOptimizationGridValueValid(selectedStrategy, parameter.name, value),
        ),
      )
    ) {
      return null;
    }

    const grid = estimateOptimizationGrid(selectedStrategy, grids);
    const trainCandles = parseInteger(values.trainCandles);
    const testCandles = parseInteger(values.testCandles);
    const stepCandles = parseInteger(values.stepCandles);
    const gapCandles = parseInteger(values.gapCandles);

    if (
      grid === null ||
      trainCandles === null ||
      testCandles === null ||
      stepCandles === null ||
      gapCandles === null
    ) {
      return null;
    }

    const folds = estimateWalkForwardFoldCount(selectedDataset.candle_count, {
      trainCandles,
      testCandles,
      stepCandles,
      gapCandles,
    });

    if (folds === null) {
      return null;
    }

    return {
      ...grid,
      folds,
      validationRuns: grid.validTrials * folds,
    };
  }, [
    selectedDataset,
    selectedStrategy,
    values.gapCandles,
    values.parameterGrids,
    values.stepCandles,
    values.testCandles,
    values.trainCandles,
  ]);

  const stopPolling = useCallback((): void => {
    pollingControllerRef.current?.abort();
    pollingControllerRef.current = null;

    if (pollingTimeoutRef.current !== null) {
      window.clearTimeout(pollingTimeoutRef.current);
      pollingTimeoutRef.current = null;
    }
  }, []);

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
      const initialStrategy =
        result.find((strategy) => strategy.name === INITIAL_VALUES.strategyName) ?? result[0];

      if (initialStrategy === undefined) {
        setHasStrategyError(true);
        return;
      }

      setStrategies(result);
      setValues((current) => ({
        ...current,
        strategyName: initialStrategy.name,
        parameterGrids: defaultParameterGrids(initialStrategy),
      }));
    } catch {
      setHasStrategyError(true);
    } finally {
      setIsLoadingStrategies(false);
    }
  }, []);

  useEffect(() => {
    void loadDatasets();
    void loadStrategies();
  }, [loadDatasets, loadStrategies]);

  useEffect(() => stopPolling, [stopPolling]);

  const pollExecution = useCallback(
    async function pollOptimizationExecution(
      executionId: string,
      signal: AbortSignal,
    ): Promise<void> {
      try {
        const current = await getOptimizationExecution(executionId);

        if (signal.aborted) {
          return;
        }

        setExecution(current);

        if (current.status === 'succeeded') {
          setIsSubmitting(false);
          pollingControllerRef.current = null;
          push(`/${locale}/optimizations/${encodeURIComponent(current.execution_id)}`);
          return;
        }

        if (current.status === 'failed') {
          setFormError(current.error_message ?? copy.form.errors.executionFailed);
          setIsSubmitting(false);
          pollingControllerRef.current = null;
          return;
        }

        pollingTimeoutRef.current = window.setTimeout(() => {
          void pollOptimizationExecution(executionId, signal);
        }, POLLING_INTERVAL_MS);
      } catch {
        if (!signal.aborted) {
          setFormError(copy.form.errors.statusUnavailable);
          setIsSubmitting(false);
          pollingControllerRef.current = null;
        }
      }
    },
    [copy.form.errors.executionFailed, copy.form.errors.statusUnavailable, locale, push],
  );

  useEffect(() => {
    if (!initialExecutionId) {
      return;
    }

    const controller = new AbortController();
    pollingControllerRef.current = controller;
    void pollExecution(initialExecutionId, controller.signal);

    return stopPolling;
  }, [initialExecutionId, pollExecution, stopPolling]);

  function clearResultState(): void {
    setFormError(null);
    setExecution(null);
    stopPolling();
  }

  function updateValue<Key extends keyof FormValues>(key: Key, value: FormValues[Key]): void {
    setValues((current) => ({ ...current, [key]: value }));
    clearResultState();
  }

  function updateStrategyName(value: string): void {
    if (!isExecutableResearchStrategyName(value)) {
      return;
    }

    const strategy = findStrategyMetadata(strategies, value);

    if (strategy === null) {
      return;
    }

    setValues((current) => ({
      ...current,
      strategyName: value,
      parameterGrids: defaultParameterGrids(strategy),
    }));
    clearResultState();
  }

  function updateParameterGrid(name: string, value: string): void {
    setValues((current) => ({
      ...current,
      parameterGrids: {
        ...current.parameterGrids,
        [name]: value,
      },
    }));
    clearResultState();
  }

  function buildParameterGrid(): OptimizationParameterGrid[] | null {
    if (selectedStrategy === null) {
      setFormError(sharedCopy.errors.strategyUnavailable);
      return null;
    }

    const parameterGrid: OptimizationParameterGrid[] = [];

    for (const parameter of selectedStrategy.parameters) {
      const gridValues = splitOptimizationGridValues(values.parameterGrids[parameter.name] ?? '');

      if (gridValues.length === 0) {
        setFormError(copy.form.errors.gridRequired);
        return null;
      }
      if (gridValues.length > 20) {
        setFormError(copy.form.errors.tooManyValues);
        return null;
      }
      if (
        gridValues.some(
          (value) => !isOptimizationGridValueValid(selectedStrategy, parameter.name, value),
        )
      ) {
        setFormError(copy.form.errors.gridInvalid);
        return null;
      }

      const canonicalValues = gridValues.map(canonicalGridValue);
      if (new Set(canonicalValues).size !== canonicalValues.length) {
        setFormError(copy.form.errors.gridDuplicate);
        return null;
      }

      parameterGrid.push({
        name: parameter.name,
        values: gridValues,
      });
    }

    return parameterGrid;
  }

  function buildRequest(): CreateOptimizationExecutionRequest | null {
    if (!values.datasetId || selectedDataset === null) {
      setFormError(sharedCopy.errors.datasetRequired);
      return null;
    }
    if (selectedStrategy === null) {
      setFormError(sharedCopy.errors.strategyUnavailable);
      return null;
    }

    const parameterGrid = buildParameterGrid();
    if (parameterGrid === null) {
      return null;
    }

    const grids = Object.fromEntries(parameterGrid.map((grid) => [grid.name, grid.values]));
    const gridEstimate = estimateOptimizationGrid(selectedStrategy, grids);
    if (gridEstimate === null || gridEstimate.validTrials === 0) {
      setFormError(copy.form.errors.noValidTrials);
      return null;
    }
    if (gridEstimate.requestedCombinations > 100) {
      setFormError(copy.form.errors.tooManyTrials);
      return null;
    }

    const horizonCandles = parseInteger(values.horizonCandles);
    const trainCandles = parseInteger(values.trainCandles);
    const testCandles = parseInteger(values.testCandles);
    const stepCandles = parseInteger(values.stepCandles);
    const gapCandles = parseInteger(values.gapCandles);
    const startingBalance = parseDecimal(values.startingBalance);
    const allocationFraction = parseDecimal(values.allocationFraction);
    const feeRate = parseDecimal(values.feeRate);
    const slippageRate = parseDecimal(values.slippageRate);

    if (horizonCandles === null || horizonCandles < 1) {
      setFormError(sharedCopy.errors.invalidHorizon);
      return null;
    }
    if (trainCandles === null || trainCandles < 2) {
      setFormError(sharedCopy.errors.invalidTrain);
      return null;
    }
    if (testCandles === null || testCandles < 1) {
      setFormError(sharedCopy.errors.invalidTest);
      return null;
    }
    if (stepCandles === null || stepCandles < testCandles) {
      setFormError(sharedCopy.errors.stepBeforeTest);
      return null;
    }
    if (gapCandles === null || gapCandles < 0) {
      setFormError(sharedCopy.errors.invalidGap);
      return null;
    }
    if (startingBalance === null || startingBalance <= 0) {
      setFormError(sharedCopy.errors.invalidStartingBalance);
      return null;
    }
    if (allocationFraction === null || allocationFraction <= 0 || allocationFraction > 1) {
      setFormError(sharedCopy.errors.invalidAllocation);
      return null;
    }
    if (feeRate === null || feeRate < 0 || feeRate >= 1) {
      setFormError(sharedCopy.errors.invalidFee);
      return null;
    }
    if (slippageRate === null || slippageRate < 0 || slippageRate >= 1) {
      setFormError(sharedCopy.errors.invalidSlippage);
      return null;
    }

    const folds = estimateWalkForwardFoldCount(selectedDataset.candle_count, {
      trainCandles,
      testCandles,
      stepCandles,
      gapCandles,
    });
    if (folds === null || folds < 3 || folds > 12) {
      setFormError(copy.form.errors.foldRange);
      return null;
    }
    if (gridEstimate.validTrials * folds > 300) {
      setFormError(copy.form.errors.tooManyValidationRuns);
      return null;
    }

    return {
      dataset_id: selectedDataset.dataset_id,
      strategy_name: values.strategyName,
      strategy_version: selectedStrategy.version,
      objective: values.objective,
      parameter_grid: parameterGrid,
      horizon_candles: horizonCandles,
      backtest_config: {
        starting_balance: values.startingBalance.trim(),
        allocation_fraction: values.allocationFraction.trim(),
        fee_rate: values.feeRate.trim(),
        slippage_rate: values.slippageRate.trim(),
      },
      walk_forward_config: {
        train_candles: trainCandles,
        test_candles: testCandles,
        step_candles: stepCandles,
        gap_candles: gapCandles,
        mode: values.mode,
      },
    };
  }

  async function submitForm(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    const request = buildRequest();

    if (request === null) {
      return;
    }

    stopPolling();
    setIsSubmitting(true);
    setFormError(null);
    setExecution(null);

    try {
      const submission = await createOptimizationExecution(request);
      setExecution(submission.execution);
      replace(
        `/${locale}/optimizations?execution=${encodeURIComponent(submission.execution.execution_id)}`,
      );

      const controller = new AbortController();
      pollingControllerRef.current = controller;
      void pollExecution(submission.execution.execution_id, controller.signal);
    } catch (error) {
      setIsSubmitting(false);

      if (error instanceof ApiRequestError && error.status === 404) {
        setFormError(copy.form.errors.datasetNotFound);
      } else if (
        error instanceof ApiRequestError &&
        (error.status === 409 || error.status === 422)
      ) {
        setFormError(copy.form.errors.validationFailed);
      } else {
        setFormError(copy.form.errors.generic);
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
    selectedStrategy === null ||
    isSubmitting ||
    isExecutionActive;
  const progressPercent = execution
    ? Math.round((execution.completed_trials / execution.total_trials) * 100)
    : 0;
  const numericFields: Array<{
    key: NumericFieldKey;
    label: string;
    min: number | string;
    max?: number | string;
    step: number | string;
  }> = [
    {
      key: 'horizonCandles',
      label: sharedCopy.fields.horizonCandles,
      min: 1,
      step: 1,
    },
    { key: 'trainCandles', label: sharedCopy.fields.trainCandles, min: 2, step: 1 },
    { key: 'testCandles', label: sharedCopy.fields.testCandles, min: 1, step: 1 },
    { key: 'stepCandles', label: sharedCopy.fields.stepCandles, min: 1, step: 1 },
    { key: 'gapCandles', label: sharedCopy.fields.gapCandles, min: 0, step: 1 },
    {
      key: 'startingBalance',
      label: sharedCopy.fields.startingBalance,
      min: '0.01',
      step: 'any',
    },
    {
      key: 'allocationFraction',
      label: sharedCopy.fields.allocationFraction,
      min: '0.000001',
      max: 1,
      step: 'any',
    },
    {
      key: 'feeRate',
      label: sharedCopy.fields.feeRate,
      min: 0,
      max: '0.999999',
      step: 'any',
    },
    {
      key: 'slippageRate',
      label: sharedCopy.fields.slippageRate,
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
            <CardTitle>{copy.form.title}</CardTitle>
            <CardDescription className="mt-2 max-w-3xl leading-7">
              {copy.form.description}
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
                isLoadingDatasets
                  ? sharedCopy.states.loadingDatasets
                  : sharedCopy.states.loadingStrategies
              }
              className="text-app-accent"
            />
          </div>
        ) : hasDatasetError || hasStrategyError ? (
          <div
            role="alert"
            className="rounded-2xl border border-app-danger-border bg-app-danger-soft p-5"
          >
            <p className="text-sm text-app-danger">
              {hasDatasetError
                ? sharedCopy.states.datasetLoadError
                : sharedCopy.states.strategyLoadError}
            </p>
            <Button
              variant="secondary"
              className="mt-4"
              onClick={() => void (hasDatasetError ? loadDatasets() : loadStrategies())}
            >
              {hasDatasetError
                ? sharedCopy.actions.retryDatasets
                : sharedCopy.actions.retryStrategies}
            </Button>
          </div>
        ) : datasets.length === 0 ? (
          <p className="rounded-2xl border border-app-border bg-app-surface-muted p-5 text-sm text-app-muted">
            {sharedCopy.states.noDatasets}
          </p>
        ) : (
          <form onSubmit={(event) => void submitForm(event)} className="space-y-6">
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
              <Select
                dir={direction}
                label={sharedCopy.fields.dataset}
                value={values.datasetId}
                disabled={isFormDisabled}
                containerClassName="md:col-span-2"
                onValueChange={(value) => updateValue('datasetId', value)}
              >
                <SelectOption value="">{sharedCopy.fields.datasetPlaceholder}</SelectOption>
                {datasets.map((dataset) => (
                  <SelectOption key={dataset.dataset_id} value={dataset.dataset_id}>
                    {dataset.name} · {dataset.pair.base_asset}/{dataset.pair.quote_asset} ·{' '}
                    {dataset.timeframe}
                  </SelectOption>
                ))}
              </Select>

              <Select
                dir={direction}
                label={sharedCopy.fields.strategy}
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
                label={copy.form.objective}
                value={values.objective}
                disabled={isFormDisabled}
                onValueChange={(value) =>
                  updateValue('objective', value as ExperimentComparisonMetric)
                }
              >
                <SelectOption value="excess_return">{copy.objectives.excess_return}</SelectOption>
                <SelectOption value="total_return">{copy.objectives.total_return}</SelectOption>
                <SelectOption value="max_drawdown_fraction">
                  {copy.objectives.max_drawdown_fraction}
                </SelectOption>
              </Select>
            </div>

            {selectedStrategy ? (
              <fieldset className="rounded-2xl border border-app-border p-5">
                <legend className="px-2 text-sm font-semibold text-app-foreground">
                  {copy.form.parameterGrid}
                </legend>
                <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                  {selectedStrategy.parameters.map((parameter) => (
                    <Input
                      key={parameter.name}
                      dir="ltr"
                      type="text"
                      label={getStrategyParameterLabel(parameter.name, locale)}
                      hint={copy.form.parameterHint}
                      value={values.parameterGrids[parameter.name] ?? ''}
                      disabled={isFormDisabled}
                      className="text-left"
                      onChange={(event) => updateParameterGrid(parameter.name, event.target.value)}
                    />
                  ))}
                </div>
              </fieldset>
            ) : null}

            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
              <Select
                dir={direction}
                label={sharedCopy.fields.mode}
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

            <div className="rounded-2xl border border-app-accent-border bg-app-accent-soft p-5">
              <p className="font-semibold text-app-accent">{copy.form.estimateTitle}</p>
              {workloadEstimate === null ? (
                <p className="mt-3 text-sm text-app-muted">{copy.form.unavailable}</p>
              ) : (
                <dl className="mt-4 grid gap-4 text-sm sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
                  <div>
                    <dt className="text-app-muted">{copy.form.requested}</dt>
                    <dd className="mt-1 text-app-foreground">
                      {numberFormatter.format(workloadEstimate.requestedCombinations)}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-app-muted">{copy.form.valid}</dt>
                    <dd className="mt-1 text-app-foreground">
                      {numberFormatter.format(workloadEstimate.validTrials)}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-app-muted">{copy.form.skipped}</dt>
                    <dd className="mt-1 text-app-foreground">
                      {numberFormatter.format(workloadEstimate.skippedCombinations)}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-app-muted">{copy.form.folds}</dt>
                    <dd className="mt-1 text-app-foreground">
                      {numberFormatter.format(workloadEstimate.folds)}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-app-muted">{copy.form.validationRuns}</dt>
                    <dd className="mt-1 text-app-foreground">
                      {numberFormatter.format(workloadEstimate.validationRuns)}
                    </dd>
                  </div>
                </dl>
              )}
            </div>

            {execution && isExecutionActive ? (
              <div
                role="status"
                aria-live="polite"
                className="rounded-2xl border border-app-accent-border bg-app-accent-soft p-5"
              >
                <div className="flex items-center justify-between gap-4">
                  <div className="flex items-center gap-3">
                    <Spinner className="text-app-accent" />
                    <p className="text-sm font-medium text-app-accent">
                      {execution.status === 'queued'
                        ? copy.form.queuedState
                        : copy.form.runningState}
                    </p>
                  </div>
                  <span dir="ltr" className="text-sm font-semibold text-app-accent">
                    {progressPercent}%
                  </span>
                </div>
                <div className="mt-4">
                  <div className="mb-2 flex justify-between gap-4 text-xs text-app-muted">
                    <span>{copy.form.progress}</span>
                    <span>
                      {numberFormatter.format(execution.completed_trials)}/
                      {numberFormatter.format(execution.total_trials)}
                    </span>
                  </div>
                  <div
                    role="progressbar"
                    aria-label={copy.form.progress}
                    aria-valuemin={0}
                    aria-valuemax={100}
                    aria-valuenow={progressPercent}
                    className="h-2 overflow-hidden rounded-full bg-app-border"
                  >
                    <div
                      className="h-full rounded-full bg-app-accent transition-[width]"
                      style={{ width: `${progressPercent}%` }}
                    />
                  </div>
                  <p dir="ltr" className="mt-3 text-left text-xs break-all text-app-muted">
                    {execution.execution_id}
                  </p>
                </div>
              </div>
            ) : null}

            {formError ? (
              <p
                role="alert"
                className="rounded-xl border border-app-danger-border bg-app-danger-soft px-4 py-3 text-sm text-app-danger"
              >
                {formError}
              </p>
            ) : null}

            <FormActionBar stickyOnMobile>
              <Button
                type="submit"
                isLoading={isSubmitting}
                loadingText={
                  execution?.status === 'running' ? copy.form.running : copy.form.queuing
                }
                disabled={isFormDisabled}
                className="w-full sm:w-auto"
              >
                {copy.form.queue}
              </Button>
            </FormActionBar>
          </form>
        )}
      </CardContent>
    </Card>
  );
}
