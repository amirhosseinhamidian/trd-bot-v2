import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  API_BASE_URL,
  createOptimizationExecution,
  getOptimizationExecution,
  getOptimizationExecutions,
} from '@/lib/api/client';
import type { CreateOptimizationExecutionRequest } from '@/features/optimizations/api/types';

const request: CreateOptimizationExecutionRequest = {
  dataset_id: 'dataset-btc-usdt-1h',
  strategy_name: 'ema-crossover',
  strategy_version: '1.0.0',
  objective: 'excess_return',
  parameter_grid: [
    { name: 'fast_period', values: ['9', '12'] },
    { name: 'slow_period', values: ['21', '26'] },
  ],
  horizon_candles: 1,
  backtest_config: {
    starting_balance: '10000',
    allocation_fraction: '0.10',
    fee_rate: '0.001',
    slippage_rate: '0.0005',
  },
  walk_forward_config: {
    train_candles: 120,
    test_candles: 24,
    step_candles: 24,
    gap_candles: 0,
    mode: 'rolling',
  },
};

afterEach(() => {
  vi.unstubAllGlobals();
});

function jsonResponse(payload: unknown): Response {
  return new Response(JSON.stringify(payload), {
    status: 200,
    headers: {
      'Content-Type': 'application/json',
    },
  });
}

describe('optimization execution client', () => {
  it('queues the complete bounded optimization request', async () => {
    const submission = {
      execution: { execution_id: 'optimization-1234567890abcdef' },
      job: { job_id: 'job-1234567890abcdef' },
      created: true,
    };
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(submission));
    vi.stubGlobal('fetch', fetchMock);

    await expect(createOptimizationExecution(request)).resolves.toEqual(submission);
    expect(fetchMock).toHaveBeenCalledWith(
      `${API_BASE_URL}/api/v1/research/optimization-executions`,
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify(request),
        cache: 'no-store',
      }),
    );
  });

  it('loads the catalog with explicit pagination', async () => {
    const page = {
      items: [],
      total: 0,
      limit: 12,
      offset: 24,
      count: 0,
      has_next: false,
      has_previous: true,
    };
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(page));
    vi.stubGlobal('fetch', fetchMock);

    await expect(getOptimizationExecutions({ limit: 12, offset: 24 })).resolves.toEqual(page);
    expect(fetchMock).toHaveBeenCalledWith(
      `${API_BASE_URL}/api/v1/research/optimization-executions?limit=12&offset=24`,
      expect.objectContaining({
        method: 'GET',
        cache: 'no-store',
      }),
    );
  });

  it('loads an execution by its encoded ID', async () => {
    const execution = { execution_id: 'optimization-1234567890abcdef' };
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(execution));
    vi.stubGlobal('fetch', fetchMock);

    await expect(getOptimizationExecution('optimization-1234567890abcdef')).resolves.toEqual(
      execution,
    );
    expect(fetchMock).toHaveBeenCalledWith(
      `${API_BASE_URL}/api/v1/research/optimization-executions/optimization-1234567890abcdef`,
      expect.objectContaining({
        method: 'GET',
        cache: 'no-store',
      }),
    );
  });
});
