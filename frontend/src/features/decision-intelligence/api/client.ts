import { ApiRequestError, getJson } from '@/lib/api/core/transport';
import type { Page } from '@/lib/api/core/types';

import type {
  DecisionEvaluationDetail,
  DecisionEvaluationSummary,
  DecisionMode,
  DecisionStage,
} from './types';

export interface DecisionEvaluationFilters {
  strategyName?: string;
  strategyVersion?: string;
  signalId?: string;
  candidateId?: string;
  portfolioId?: string;
  stage?: DecisionStage;
  mode?: DecisionMode;
  limit?: number;
  offset?: number;
}

function buildParams(filters: DecisionEvaluationFilters): URLSearchParams {
  const params = new URLSearchParams();
  const mappings: Array<[string, string | number | undefined]> = [
    ['strategy_name', filters.strategyName],
    ['strategy_version', filters.strategyVersion],
    ['signal_id', filters.signalId],
    ['candidate_id', filters.candidateId],
    ['portfolio_id', filters.portfolioId],
    ['stage', filters.stage],
    ['mode', filters.mode],
    ['limit', filters.limit],
    ['offset', filters.offset],
  ];
  for (const [key, value] of mappings) {
    if (value !== undefined) {
      params.set(key, String(value));
    }
  }
  return params;
}

export async function getDecisionEvaluations(
  filters: DecisionEvaluationFilters = {},
): Promise<Page<DecisionEvaluationSummary>> {
  const params = buildParams({ limit: 20, offset: 0, ...filters });
  return getJson<Page<DecisionEvaluationSummary>>(
    `/api/v1/decision-intelligence/evaluations?${params.toString()}`,
  );
}

export async function getLatestDecisionEvaluation(
  filters: DecisionEvaluationFilters = {},
): Promise<DecisionEvaluationDetail | null> {
  const params = buildParams(filters);
  const query = params.toString();
  try {
    return await getJson<DecisionEvaluationDetail>(
      `/api/v1/decision-intelligence/evaluations/latest${query ? `?${query}` : ''}`,
    );
  } catch (error) {
    if (error instanceof ApiRequestError && error.status === 404) {
      return null;
    }
    throw error;
  }
}

export async function getDecisionEvaluation(
  evaluationId: string,
): Promise<DecisionEvaluationDetail> {
  return getJson<DecisionEvaluationDetail>(
    `/api/v1/decision-intelligence/evaluations/${encodeURIComponent(evaluationId)}`,
  );
}
