import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { describe, expect, it } from 'vitest';

import { getResearchActivity, getResearchOverview } from '@/features/overview/api/client';
import {
  getResearchActivity as getResearchActivityFacade,
  getResearchOverview as getResearchOverviewFacade,
} from '@/lib/api/client';

describe('overview API boundary', () => {
  it('keeps the legacy client facade mapped to the feature-owned adapter', () => {
    expect(getResearchOverviewFacade).toBe(getResearchOverview);
    expect(getResearchActivityFacade).toBe(getResearchActivity);
  });

  it('keeps overview ownership outside the legacy facades', () => {
    const clientSource = readFileSync(resolve(process.cwd(), 'src/lib/api/client.ts'), 'utf8');
    const typesSource = readFileSync(resolve(process.cwd(), 'src/lib/api/types.ts'), 'utf8');
    const overviewClientSource = readFileSync(
      resolve(process.cwd(), 'src/features/overview/api/client.ts'),
      'utf8',
    );
    const overviewTypesSource = readFileSync(
      resolve(process.cwd(), 'src/features/overview/api/types.ts'),
      'utf8',
    );

    expect(clientSource).not.toContain('/api/v1/research/overview');
    expect(clientSource).toContain("from '@/features/overview/api/client'");
    expect(typesSource).not.toContain('export interface ResearchOverview');
    expect(typesSource).not.toContain('export interface ResearchActivityItem');
    expect(typesSource).not.toContain('export type ResearchStage =');
    expect(typesSource).toContain("from '@/features/overview/api/types'");
    expect(overviewClientSource).not.toContain('@/lib/api/client');
    expect(overviewTypesSource).not.toContain('@/lib/api/types');
  });
});
