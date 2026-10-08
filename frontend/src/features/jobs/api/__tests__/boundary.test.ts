import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { describe, expect, it } from 'vitest';

import { getBackgroundJob } from '@/features/jobs/api/client';
import { getBackgroundJob as getBackgroundJobFacade } from '@/lib/api/client';

describe('jobs API boundary', () => {
  it('keeps the legacy client facade mapped to the feature-owned adapter', () => {
    expect(getBackgroundJobFacade).toBe(getBackgroundJob);
  });

  it('keeps job ownership outside the legacy facades', () => {
    const clientSource = readFileSync(resolve(process.cwd(), 'src/lib/api/client.ts'), 'utf8');
    const typesSource = readFileSync(resolve(process.cwd(), 'src/lib/api/types.ts'), 'utf8');
    const jobsClientSource = readFileSync(
      resolve(process.cwd(), 'src/features/jobs/api/client.ts'),
      'utf8',
    );
    const jobsTypesSource = readFileSync(
      resolve(process.cwd(), 'src/features/jobs/api/types.ts'),
      'utf8',
    );

    expect(clientSource).not.toContain('/api/v1/jobs');
    expect(clientSource).toContain("from '@/features/jobs/api/client'");
    expect(typesSource).not.toContain('export interface BackgroundJobSummary');
    expect(typesSource).not.toContain('export type BackgroundJobKind =');
    expect(typesSource).toContain("from '@/features/jobs/api/types'");
    expect(jobsClientSource).not.toContain('@/lib/api/client');
    expect(jobsTypesSource).not.toContain('@/lib/api/types');
  });
});
