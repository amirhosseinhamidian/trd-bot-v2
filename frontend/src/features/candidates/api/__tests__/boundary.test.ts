import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { describe, expect, it } from 'vitest';

import {
  compareCandidates,
  getCandidateLineage,
  getCandidateProjection,
  getCandidateProjections,
} from '@/features/candidates/api/client';
import {
  compareCandidates as compareCandidatesFacade,
  getCandidateLineage as getCandidateLineageFacade,
  getCandidateProjection as getCandidateProjectionFacade,
  getCandidateProjections as getCandidateProjectionsFacade,
} from '@/lib/api/client';

describe('candidates API boundary', () => {
  it('keeps the legacy client facade mapped to the feature-owned adapter', () => {
    expect(getCandidateProjectionsFacade).toBe(getCandidateProjections);
    expect(compareCandidatesFacade).toBe(compareCandidates);
    expect(getCandidateProjectionFacade).toBe(getCandidateProjection);
    expect(getCandidateLineageFacade).toBe(getCandidateLineage);
  });

  it('keeps candidate ownership outside the legacy facades', () => {
    const clientSource = readFileSync(resolve(process.cwd(), 'src/lib/api/client.ts'), 'utf8');
    const typesSource = readFileSync(resolve(process.cwd(), 'src/lib/api/types.ts'), 'utf8');
    const candidateClientSource = readFileSync(
      resolve(process.cwd(), 'src/features/candidates/api/client.ts'),
      'utf8',
    );
    const candidateTypesSource = readFileSync(
      resolve(process.cwd(), 'src/features/candidates/api/types.ts'),
      'utf8',
    );

    expect(clientSource).not.toContain('/api/v1/research/candidates');
    expect(clientSource).toContain("from '@/features/candidates/api/client'");
    expect(typesSource).not.toContain('export interface CandidateProjectionSummary');
    expect(typesSource).not.toContain('export interface CandidateDecisionEvidence');
    expect(typesSource).not.toContain("export type CandidateStatus = 'candidate'");
    expect(typesSource).toContain("from '@/features/candidates/api/types'");
    expect(candidateClientSource).not.toContain('@/lib/api/client');
    expect(candidateTypesSource).not.toContain('@/lib/api/types');
  });
});
