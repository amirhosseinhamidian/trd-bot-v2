import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { describe, expect, it } from 'vitest';

import {
  getResearchStrategies,
  getResearchStrategyVersion,
  getResearchStrategyVersions,
} from '@/features/strategies/api/client';
import {
  getResearchStrategies as getResearchStrategiesFacade,
  getResearchStrategyVersion as getResearchStrategyVersionFacade,
  getResearchStrategyVersions as getResearchStrategyVersionsFacade,
} from '@/lib/api/client';

describe('strategies API boundary', () => {
  it('keeps the legacy client facade mapped to the feature-owned adapter', () => {
    expect(getResearchStrategiesFacade).toBe(getResearchStrategies);
    expect(getResearchStrategyVersionFacade).toBe(getResearchStrategyVersion);
    expect(getResearchStrategyVersionsFacade).toBe(getResearchStrategyVersions);
  });

  it('keeps strategy endpoints and metadata types outside the legacy facades', () => {
    const clientSource = readFileSync(resolve(process.cwd(), 'src/lib/api/client.ts'), 'utf8');
    const typesSource = readFileSync(resolve(process.cwd(), 'src/lib/api/types.ts'), 'utf8');
    const strategyClientSource = readFileSync(
      resolve(process.cwd(), 'src/features/strategies/api/client.ts'),
      'utf8',
    );
    const strategyTypesSource = readFileSync(
      resolve(process.cwd(), 'src/features/strategies/api/types.ts'),
      'utf8',
    );

    expect(clientSource).not.toContain('/api/v1/research/strategies');
    expect(clientSource).toContain("from '@/features/strategies/api/client'");
    expect(typesSource).not.toContain('export interface ResearchStrategyMetadata');
    expect(typesSource).toContain("from '@/features/strategies/api/types'");
    expect(strategyClientSource).not.toContain('@/lib/api/client');
    expect(strategyTypesSource).not.toContain('@/lib/api/types');
  });
});
