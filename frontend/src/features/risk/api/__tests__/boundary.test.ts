import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { describe, expect, it } from 'vitest';

import { getRiskDashboard } from '@/features/risk/api/client';
import { getRiskDashboard as getRiskDashboardFacade } from '@/lib/api/client';

describe('risk API boundary', () => {
  it('keeps the legacy client facade mapped to the feature-owned adapter', () => {
    expect(getRiskDashboardFacade).toBe(getRiskDashboard);
  });

  it('keeps risk ownership outside the legacy facades', () => {
    const clientSource = readFileSync(resolve(process.cwd(), 'src/lib/api/client.ts'), 'utf8');
    const typesSource = readFileSync(resolve(process.cwd(), 'src/lib/api/types.ts'), 'utf8');
    const riskClientSource = readFileSync(
      resolve(process.cwd(), 'src/features/risk/api/client.ts'),
      'utf8',
    );
    const riskTypesSource = readFileSync(
      resolve(process.cwd(), 'src/features/risk/api/types.ts'),
      'utf8',
    );

    expect(clientSource).not.toContain('/api/v1/research/risk');
    expect(clientSource).toContain("from '@/features/risk/api/client'");
    expect(typesSource).not.toContain('export interface RiskDashboardReport');
    expect(typesSource).not.toContain('export interface RiskDecisionEvent');
    expect(typesSource).toContain("from '@/features/risk/api/types'");
    expect(riskClientSource).not.toContain('@/lib/api/client');
    expect(riskTypesSource).not.toContain('@/lib/api/types');
  });
});
