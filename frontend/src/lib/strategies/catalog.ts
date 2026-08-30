import type {
  ResearchStrategyMetadata,
  ResearchStrategyName,
  StrategyParameterMetadata,
} from '@/lib/api/types';

const EXECUTABLE_STRATEGY_NAMES = new Set<ResearchStrategyName>(['ema-crossover', 'rsi-threshold']);

export function isExecutableResearchStrategyName(name: string): name is ResearchStrategyName {
  return EXECUTABLE_STRATEGY_NAMES.has(name as ResearchStrategyName);
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
