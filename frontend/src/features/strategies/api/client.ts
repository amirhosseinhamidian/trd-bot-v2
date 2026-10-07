import { getJson } from '@/lib/api/core/transport';

import type { ResearchStrategyMetadata } from './types';

export async function getResearchStrategies(): Promise<ResearchStrategyMetadata[]> {
  return getJson<ResearchStrategyMetadata[]>('/api/v1/research/strategies');
}

export async function getResearchStrategyVersion(
  strategyName: string,
  version: string,
): Promise<ResearchStrategyMetadata> {
  return getJson<ResearchStrategyMetadata>(
    `/api/v1/research/strategies/${encodeURIComponent(strategyName)}/versions/${encodeURIComponent(version)}`,
  );
}

export async function getResearchStrategyVersions(
  strategyName: string,
): Promise<ResearchStrategyMetadata[]> {
  return getJson<ResearchStrategyMetadata[]>(
    `/api/v1/research/strategies/${encodeURIComponent(strategyName)}/versions`,
  );
}
