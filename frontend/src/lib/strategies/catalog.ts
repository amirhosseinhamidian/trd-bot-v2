import type {
  ResearchStrategyMetadata,
  ResearchStrategyName,
  StrategyParameterMetadata,
} from '@/lib/api/types';

export type ExecutableResearchStrategyMetadata = Omit<ResearchStrategyMetadata, 'name'> & {
  name: ResearchStrategyName;
};

export type StrategyParameterInputProps = {
  min?: string;
  max?: string;
  step: 1 | 'any';
};

const EXECUTABLE_STRATEGY_NAMES = new Set<ResearchStrategyName>(['ema-crossover', 'rsi-threshold']);

export function isExecutableResearchStrategyName(name: string): name is ResearchStrategyName {
  return EXECUTABLE_STRATEGY_NAMES.has(name as ResearchStrategyName);
}

export function getExecutableResearchStrategies(
  catalog: ResearchStrategyMetadata[],
): ExecutableResearchStrategyMetadata[] {
  return catalog.filter((strategy): strategy is ExecutableResearchStrategyMetadata =>
    isExecutableResearchStrategyName(strategy.name),
  );
}

export function findStrategyMetadata(
  catalog: ResearchStrategyMetadata[],
  name: string,
  version?: string,
): ResearchStrategyMetadata | null {
  return (
    catalog.find(
      (strategy) =>
        strategy.name === name && (version === undefined || strategy.version === version),
    ) ?? null
  );
}

export function findStrategyParameterMetadata(
  strategy: ResearchStrategyMetadata,
  parameterName: string,
): StrategyParameterMetadata | null {
  return strategy.parameters.find((parameter) => parameter.name === parameterName) ?? null;
}

export function getStrategyParameterDefault(
  strategy: ResearchStrategyMetadata,
  parameterName: string,
): string | null {
  return findStrategyParameterMetadata(strategy, parameterName)?.default_value ?? null;
}

function parseMetadataBound(value: string | null): number | null {
  if (value === null) {
    return null;
  }

  const parsedValue = Number(value);

  return Number.isFinite(parsedValue) ? parsedValue : null;
}

export function isStrategyParameterValueValid(
  strategy: ResearchStrategyMetadata,
  parameterName: string,
  value: string,
): boolean {
  const parameter = findStrategyParameterMetadata(strategy, parameterName);

  if (parameter === null || !value.trim()) {
    return false;
  }

  const parsedValue = Number(value);

  if (!Number.isFinite(parsedValue)) {
    return false;
  }

  if (parameter.kind === 'integer' && !Number.isInteger(parsedValue)) {
    return false;
  }

  const minimum = parseMetadataBound(parameter.minimum);

  if (
    parameter.minimum !== null &&
    (minimum === null ||
      (parameter.minimum_exclusive ? parsedValue <= minimum : parsedValue < minimum))
  ) {
    return false;
  }

  const maximum = parseMetadataBound(parameter.maximum);

  if (
    parameter.maximum !== null &&
    (maximum === null ||
      (parameter.maximum_exclusive ? parsedValue >= maximum : parsedValue > maximum))
  ) {
    return false;
  }

  return true;
}

export function getStrategyParameterInputProps(
  strategy: ResearchStrategyMetadata,
  parameterName: string,
): StrategyParameterInputProps {
  const parameter = findStrategyParameterMetadata(strategy, parameterName);

  if (parameter === null) {
    return {
      step: 'any',
    };
  }

  return {
    ...(parameter.minimum === null ? {} : { min: parameter.minimum }),
    ...(parameter.maximum === null ? {} : { max: parameter.maximum }),
    step: parameter.kind === 'integer' ? 1 : 'any',
  };
}
