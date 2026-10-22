import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  getDecisionEvaluations,
  getLatestDecisionEvaluation,
} from '@/features/decision-intelligence/api/client';
import { API_BASE_URL } from '@/lib/api/core/transport';

function jsonResponse(value: unknown, status = 200): Response {
  return new Response(JSON.stringify(value), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('Decision Intelligence client', () => {
  it('encodes exact lineage filters for the latest evidence', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ summary: {} }));
    vi.stubGlobal('fetch', fetchMock);

    await getLatestDecisionEvaluation({
      strategyName: 'ema-crossover',
      strategyVersion: '1.0.0',
      stage: 'risk_gate',
      mode: 'shadow',
    });

    expect(String(fetchMock.mock.calls[0]?.[0])).toBe(
      `${API_BASE_URL}/api/v1/decision-intelligence/evaluations/latest?strategy_name=ema-crossover&strategy_version=1.0.0&stage=risk_gate&mode=shadow`,
    );
  });

  it('models missing linked evidence as null', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({ detail: 'not found' }, 404)));

    await expect(
      getLatestDecisionEvaluation({ signalId: 'signal-1234567890abcdef' }),
    ).resolves.toBeNull();
  });

  it('applies stable pagination defaults to the summary collection', async () => {
    const page = {
      items: [],
      total: 0,
      limit: 20,
      offset: 0,
      count: 0,
      has_next: false,
      has_previous: false,
    };
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(page));
    vi.stubGlobal('fetch', fetchMock);

    await expect(
      getDecisionEvaluations({ portfolioId: 'portfolio-1234567890abcdef' }),
    ).resolves.toEqual(page);
    expect(String(fetchMock.mock.calls[0]?.[0])).toBe(
      `${API_BASE_URL}/api/v1/decision-intelligence/evaluations?portfolio_id=portfolio-1234567890abcdef&limit=20&offset=0`,
    );
  });
});
