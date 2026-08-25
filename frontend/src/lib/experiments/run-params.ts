import type { ExperimentSummary } from '@/lib/api/types';

export type ExperimentRunInitialValues = {
  datasetId?: string;
  fastPeriod?: string;
  slowPeriod?: string;
  horizonCandles?: string;
  startingBalance?: string;
  allocationFraction?: string;
  feeRate?: string;
  slippageRate?: string;
};

export type ExperimentRunSearchParams = Record<string, string | string[] | undefined>;

function getFirstValue(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

function getTextValue(
  value: string | string[] | undefined,
  maximumLength: number,
): string | undefined {
  const normalizedValue = getFirstValue(value)?.trim();

  if (!normalizedValue || normalizedValue.length > maximumLength) {
    return undefined;
  }

  return normalizedValue;
}

function getIntegerValue(
  value: string | string[] | undefined,
  minimum: number,
): string | undefined {
  const normalizedValue = getFirstValue(value)?.trim();

  if (!normalizedValue) {
    return undefined;
  }

  const parsedValue = Number(normalizedValue);

  if (!Number.isInteger(parsedValue) || parsedValue < minimum) {
    return undefined;
  }

  return String(parsedValue);
}

function getDecimalValue(
  value: string | string[] | undefined,
  isValid: (value: number) => boolean,
): string | undefined {
  const normalizedValue = getFirstValue(value)?.trim();

  if (!normalizedValue || normalizedValue.length > 50) {
    return undefined;
  }

  const parsedValue = Number(normalizedValue);

  if (!Number.isFinite(parsedValue) || !isValid(parsedValue)) {
    return undefined;
  }

  return normalizedValue;
}

function getExperimentParameter(
  experiment: ExperimentSummary,
  parameterName: string,
): string | undefined {
  return experiment.parameters.find((parameter) => parameter.name === parameterName)?.value;
}

export function buildExperimentRerunHref(
  experiment: ExperimentSummary,
  locale: 'fa' | 'en',
): string {
  const params = new URLSearchParams();

  params.set('dataset_id', experiment.dataset_id);
  params.set('horizon_candles', String(experiment.horizon_candles));

  const parameterMappings = [
    ['fast_period', 'fast_period'],
    ['slow_period', 'slow_period'],
    ['starting_balance', 'starting_balance'],
    ['allocation_fraction', 'allocation_fraction'],
    ['fee_rate', 'fee_rate'],
    ['slippage_rate', 'slippage_rate'],
  ] as const;

  for (const [parameterName, queryName] of parameterMappings) {
    const value = getExperimentParameter(experiment, parameterName);

    if (value !== undefined) {
      params.set(queryName, value);
    }
  }

  return `/${locale}/experiments?${params.toString()}`;
}

export function parseExperimentRunSearchParams(
  searchParams: ExperimentRunSearchParams,
): ExperimentRunInitialValues {
  const result: ExperimentRunInitialValues = {};

  const datasetId = getTextValue(searchParams.dataset_id, 200);

  const fastPeriod = getIntegerValue(searchParams.fast_period, 2);

  const slowPeriod = getIntegerValue(searchParams.slow_period, 3);

  const horizonCandles = getIntegerValue(searchParams.horizon_candles, 1);

  const startingBalance = getDecimalValue(searchParams.starting_balance, (value) => value > 0);

  const allocationFraction = getDecimalValue(
    searchParams.allocation_fraction,
    (value) => value > 0 && value <= 1,
  );

  const feeRate = getDecimalValue(searchParams.fee_rate, (value) => value >= 0 && value < 1);

  const slippageRate = getDecimalValue(
    searchParams.slippage_rate,
    (value) => value >= 0 && value < 1,
  );

  if (datasetId !== undefined) {
    result.datasetId = datasetId;
  }

  if (fastPeriod !== undefined) {
    result.fastPeriod = fastPeriod;
  }

  if (slowPeriod !== undefined) {
    result.slowPeriod = slowPeriod;
  }

  if (horizonCandles !== undefined) {
    result.horizonCandles = horizonCandles;
  }

  if (startingBalance !== undefined) {
    result.startingBalance = startingBalance;
  }

  if (allocationFraction !== undefined) {
    result.allocationFraction = allocationFraction;
  }

  if (feeRate !== undefined) {
    result.feeRate = feeRate;
  }

  if (slippageRate !== undefined) {
    result.slippageRate = slippageRate;
  }

  return result;
}

export function parseExperimentExecutionId(
  searchParams: ExperimentRunSearchParams,
): string | undefined {
  const executionId = getFirstValue(searchParams.execution)?.trim();

  if (executionId === undefined || !/^execution-[a-f0-9]{16}$/u.test(executionId)) {
    return undefined;
  }

  return executionId;
}
