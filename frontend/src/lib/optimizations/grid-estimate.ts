import type { ResearchStrategyMetadata } from '@/features/strategies/api/types';
import {
  findStrategyParameterMetadata,
  isMovingAverageCrossoverStrategyName,
  isStrategyParameterValueValid,
} from '@/lib/strategies/catalog';

export type OptimizationGridEstimate = {
  requestedCombinations: number;
  skippedCombinations: number;
  validTrials: number;
};

export function splitOptimizationGridValues(value: string): string[] {
  return value
    .split(/[,،]/u)
    .map((item) => item.trim())
    .filter(Boolean);
}

export function isOptimizationGridValueValid(
  strategy: ResearchStrategyMetadata,
  parameterName: string,
  value: string,
): boolean {
  const parameter = findStrategyParameterMetadata(strategy, parameterName);

  if (parameter?.kind === 'integer' && !/^[+-]?\d+$/u.test(value)) {
    return false;
  }

  return isStrategyParameterValueValid(strategy, parameterName, value);
}

function isValidCombination(
  strategyName: string,
  parameterNames: string[],
  values: string[],
): boolean {
  if (!isMovingAverageCrossoverStrategyName(strategyName)) {
    return true;
  }

  const fastIndex = parameterNames.indexOf('fast_period');
  const slowIndex = parameterNames.indexOf('slow_period');

  if (fastIndex === -1 || slowIndex === -1) {
    return false;
  }

  return Number(values[slowIndex]) > Number(values[fastIndex]);
}

export function estimateOptimizationGrid(
  strategy: ResearchStrategyMetadata,
  grids: Record<string, string[]>,
): OptimizationGridEstimate | null {
  const parameterNames = strategy.parameters.map((parameter) => parameter.name);
  const valueGroups = parameterNames.map((name) => grids[name] ?? []);

  if (valueGroups.some((values) => values.length === 0)) {
    return null;
  }

  const requestedCombinations = valueGroups.reduce((total, values) => total * values.length, 1);
  let validTrials = 0;

  function countValidCombinations(index: number, values: string[]): void {
    if (index === valueGroups.length) {
      if (isValidCombination(strategy.name, parameterNames, values)) {
        validTrials += 1;
      }
      return;
    }

    valueGroups[index].forEach((value) => {
      countValidCombinations(index + 1, [...values, value]);
    });
  }

  countValidCombinations(0, []);

  return {
    requestedCombinations,
    skippedCombinations: requestedCombinations - validTrials,
    validTrials,
  };
}
