import { getJson, postJson } from '@/lib/api/core/transport';
import type { Page } from '@/lib/api/types';

import type {
  CandidateComparisonResult,
  CandidateJournalOccurrence,
  CandidateProjectionDetail,
  CandidateProjectionSummary,
} from './types';

export interface CandidateProjectionFilters {
  limit?: number;
  offset?: number;
}

export async function getCandidateProjections(
  filters: CandidateProjectionFilters = {},
): Promise<Page<CandidateProjectionSummary>> {
  const params = new URLSearchParams();
  params.set('limit', String(filters.limit ?? 12));
  params.set('offset', String(filters.offset ?? 0));

  return getJson<Page<CandidateProjectionSummary>>(
    `/api/v1/research/candidates?${params.toString()}`,
  );
}

export async function compareCandidates(
  candidateIds: string[],
): Promise<CandidateComparisonResult> {
  return postJson<CandidateComparisonResult>('/api/v1/research/candidates/compare', {
    candidate_ids: candidateIds,
  });
}

export async function getCandidateProjection(
  candidateId: string,
): Promise<CandidateProjectionDetail> {
  return getJson<CandidateProjectionDetail>(
    `/api/v1/research/candidates/${encodeURIComponent(candidateId)}`,
  );
}

export async function getCandidateLineage(
  candidateId: string,
  filters: CandidateProjectionFilters = {},
): Promise<Page<CandidateJournalOccurrence>> {
  const params = new URLSearchParams();
  params.set('limit', String(filters.limit ?? 10));
  params.set('offset', String(filters.offset ?? 0));

  return getJson<Page<CandidateJournalOccurrence>>(
    `/api/v1/research/candidates/${encodeURIComponent(candidateId)}/lineage?${params.toString()}`,
  );
}
