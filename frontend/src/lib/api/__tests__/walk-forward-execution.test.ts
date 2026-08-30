import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  API_BASE_URL,
  createEmaCrossoverWalkForwardExecution,
  createRsiThresholdWalkForwardExecution,
  getWalkForwardExecution,
} from '@/lib/api/client';
import type {
  StoredDatasetEMACrossoverWalkForwardRequest,
  StoredDatasetRSIThresholdWalkForwardRequest,
  WalkForwardExecution,
} from '@/lib/api/types';

const request: StoredDatasetEMACrossoverWalkForwardRequest = {
  dataset_id: 'dataset-btc-usdt-1h',
  fast_period: 9,
  slow_period: 21,
  horizon_candles: 1,
  starting_balance: '10000',
  allocation_fraction: '0.10',
  fee_rate: '0.001',
  slippage_rate: '0.0005',
  train_candles: 120,
  test_candles: 24,
  step_candles: 24,
  gap_candles: 0,
  mode: 'rolling',
};

const execution: WalkForwardExecution = {
  execution_id: 'walk-forward-job-1234567890abcdef',
  created_at: '2026-08-26T12:00:00Z',
  updated_at: '2026-08-26T12:00:01Z',
  started_at: null,
  finished_at: null,
  status: 'queued',
  progress_percent: 0,
  dataset_id: request.dataset_id,
  strategy_name: 'ema-crossover',
  strategy_version: '1.0.0',
  parameters: {
    fast_period: request.fast_period,
    slow_period: request.slow_period,
    horizon_candles: request.horizon_candles,
    starting_balance: request.starting_balance,
    allocation_fraction: request.allocation_fraction,
    fee_rate: request.fee_rate,
    slippage_rate: request.slippage_rate,
  },
  walk_forward_config: {
    train_candles: request.train_candles,
    test_candles: request.test_candles,
    step_candles: request.step_candles,
    gap_candles: request.gap_candles,
    mode: request.mode,
  },
  total_folds: 5,
  completed_folds: 0,
  walk_forward_run_id: null,
  error_code: null,
  error_message: null,
};

const rsiRequest: StoredDatasetRSIThresholdWalkForwardRequest = {
  dataset_id: 'dataset-btc-usdt-1h',
  period: 14,
  oversold_threshold: '30',
  overbought_threshold: '70',
  horizon_candles: 1,
  starting_balance: '10000',
  allocation_fraction: '0.10',
  fee_rate: '0.001',
  slippage_rate: '0.0005',
  train_candles: 120,
  test_candles: 24,
  step_candles: 24,
  gap_candles: 0,
  mode: 'rolling',
};

const rsiExecution: WalkForwardExecution = {
  ...execution,
  strategy_name: 'rsi-threshold',
  parameters: {
    period: rsiRequest.period,
    oversold_threshold: rsiRequest.oversold_threshold,
    overbought_threshold: rsiRequest.overbought_threshold,
    horizon_candles: rsiRequest.horizon_candles,
    starting_balance: rsiRequest.starting_balance,
    allocation_fraction: rsiRequest.allocation_fraction,
    fee_rate: rsiRequest.fee_rate,
    slippage_rate: rsiRequest.slippage_rate,
  },
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('walk-forward execution client', () => {
  it('queues an EMA crossover walk-forward execution', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(execution), {
        status: 201,
        headers: {
          'Content-Type': 'application/json',
        },
      }),
    );

    vi.stubGlobal('fetch', fetchMock);

    await expect(createEmaCrossoverWalkForwardExecution(request)).resolves.toEqual(execution);

    expect(fetchMock).toHaveBeenCalledTimes(1);

    const [url, options] = fetchMock.mock.calls[0] as [string, RequestInit];

    expect(url).toBe(`${API_BASE_URL}/api/v1/research/walk-forward-executions/ema-crossover`);

    expect(options).toEqual(
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify(request),
        cache: 'no-store',
      }),
    );

    expect(options.headers).toEqual(
      expect.objectContaining({
        Accept: 'application/json',
        'Content-Type': 'application/json',
      }),
    );
  });

  it('queues an RSI threshold walk-forward execution', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(rsiExecution), {
        status: 202,
        headers: {
          'Content-Type': 'application/json',
        },
      }),
    );

    vi.stubGlobal('fetch', fetchMock);

    await expect(createRsiThresholdWalkForwardExecution(rsiRequest)).resolves.toEqual(rsiExecution);

    expect(fetchMock).toHaveBeenCalledWith(
      `${API_BASE_URL}/api/v1/research/walk-forward-executions/rsi-threshold`,
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify(rsiRequest),
        cache: 'no-store',
      }),
    );
  });

  it('loads a walk-forward execution by its encoded ID', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(execution), {
        status: 200,
        headers: {
          'Content-Type': 'application/json',
        },
      }),
    );

    vi.stubGlobal('fetch', fetchMock);

    await expect(getWalkForwardExecution('walk-forward-job-1234567890abcdef')).resolves.toEqual(
      execution,
    );

    expect(fetchMock).toHaveBeenCalledWith(
      `${API_BASE_URL}/api/v1/research/walk-forward-executions/walk-forward-job-1234567890abcdef`,
      expect.objectContaining({
        method: 'GET',
        cache: 'no-store',
      }),
    );
  });
});
