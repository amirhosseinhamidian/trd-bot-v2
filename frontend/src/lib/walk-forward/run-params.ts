import type { ResearchStrategyName } from '@/lib/api/types';
import { isExecutableResearchStrategyName } from '@/lib/strategies/catalog';

export type WalkForwardRunSearchParams = Record<string, string | string[] | undefined>;

export type WalkForwardRunInitialValues = {
  strategyName?: ResearchStrategyName;
};

function getFirstValue(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

function getStrategyName(value: string | string[] | undefined): ResearchStrategyName | undefined {
  const strategyName = getFirstValue(value)?.trim();

  if (strategyName && isExecutableResearchStrategyName(strategyName)) {
    return strategyName;
  }

  return undefined;
}

export function parseWalkForwardRunSearchParams(
  searchParams: WalkForwardRunSearchParams,
): WalkForwardRunInitialValues {
  const strategyName = getStrategyName(searchParams.strategy);

  return strategyName === undefined ? {} : { strategyName };
}

export function parseWalkForwardExecutionId(
  searchParams: WalkForwardRunSearchParams,
): string | undefined {
  const executionId = getFirstValue(searchParams.execution)?.trim();

  if (executionId === undefined || !/^walk-forward-job-[a-f0-9]{16}$/u.test(executionId)) {
    return undefined;
  }

  return executionId;
}
