import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { describe, expect, it } from 'vitest';

import { getMonitoringSummary } from '@/features/monitoring/api/client';
import { getMonitoringSummary as getMonitoringSummaryFacade } from '@/lib/api/client';

describe('monitoring API boundary', () => {
  it('keeps the legacy client facade mapped to the feature-owned adapter', () => {
    expect(getMonitoringSummaryFacade).toBe(getMonitoringSummary);
  });

  it('keeps monitoring ownership outside the legacy facades', () => {
    const clientSource = readFileSync(resolve(process.cwd(), 'src/lib/api/client.ts'), 'utf8');
    const typesSource = readFileSync(resolve(process.cwd(), 'src/lib/api/types.ts'), 'utf8');
    const monitoringClientSource = readFileSync(
      resolve(process.cwd(), 'src/features/monitoring/api/client.ts'),
      'utf8',
    );
    const monitoringTypesSource = readFileSync(
      resolve(process.cwd(), 'src/features/monitoring/api/types.ts'),
      'utf8',
    );

    expect(clientSource).not.toContain('/api/v1/monitoring');
    expect(clientSource).toContain("from '@/features/monitoring/api/client'");
    expect(typesSource).not.toContain('export interface MonitoringSummary');
    expect(typesSource).not.toContain('export interface SystemMetricSample');
    expect(typesSource).not.toContain('export type MonitoringOverallStatus =');
    expect(typesSource).toContain("from '@/features/monitoring/api/types'");
    expect(monitoringClientSource).not.toContain('@/lib/api/client');
    expect(monitoringTypesSource).not.toContain('@/lib/api/types');
  });
});
