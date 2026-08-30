import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  API_BASE_URL,
  createEmaCrossoverExperimentExecution,
  createRsiThresholdExperimentExecution,
} from '@/lib/api/client';
import type {
  ExperimentExecution,
  StoredDatasetEMACrossoverRequest,
  StoredDatasetRSIThresholdRequest,
} from '@/lib/api/types';

const emaRequest: StoredDatasetEMACrossoverRequest = {
  dataset_id: 'dataset-btc-usdt-1h',
  fast_period: 9,
  slow_period: 21,
  horizon_candles: 1,
  starting_balance: '10000',
  allocation_fraction: '0.10',
  fee_rate: '0.001',
  slippage_rate: '0.0005',
};

const rsiRequest: StoredDatasetRSIThresholdRequest = {
  dataset_id: 'dataset-btc-usdt-1h',
  period: 14,
  oversold_threshold: '30',
  overbought_threshold: '70',
  horizon_candles: 1,
  starting_balance: '10000',
  allocation_fraction: '0.10',
  fee_rate: '0.001',
  slippage_rate: '0.0005',
};

function buildExecution(strategyName: 'ema-crossover' | 'rsi-threshold'): ExperimentExecution {
  return {
    execution_id: 'execution-1234567890abcdef',
    created_at: '2026-08-30T07:00:00Z',
    updated_at: '2026-08-30T07:00:00Z',
    started_at: null,
    finished_at: null,
    status: 'queued',
    progress_percent: 0,
    dataset_id: emaRequest.dataset_id,
    strategy_name: strategyName,
    strategy_version: '1.0.0',
    parameters:
      strategyName === 'ema-crossover'
        ? {
            fast_period: emaRequest.fast_period,
            slow_period: emaRequest.slow_period,
            horizon_candles: emaRequest.horizon_candles,
            starting_balance: emaRequest.starting_balance,
            allocation_fraction: emaRequest.allocation_fraction,
            fee_rate: emaRequest.fee_rate,
            slippage_rate: emaRequest.slippage_rate,
          }
        : {
            period: rsiRequest.period,
            oversold_threshold: rsiRequest.oversold_threshold,
            overbought_threshold: rsiRequest.overbought_threshold,
            horizon_candles: rsiRequest.horizon_candles,
            starting_balance: rsiRequest.starting_balance,
            allocation_fraction: rsiRequest.allocation_fraction,
            fee_rate: rsiRequest.fee_rate,
            slippage_rate: rsiRequest.slippage_rate,
          },
    experiment_id: null,
    error_code: null,
    error_message: null,
  };
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('experiment execution client', () => {
  it('queues an EMA crossover experiment execution', async () => {
    const execution = buildExecution('ema-crossover');
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(execution), {
        status: 202,
        headers: {
          'Content-Type': 'application/json',
        },
      }),
    );

    vi.stubGlobal('fetch', fetchMock);

    await expect(createEmaCrossoverExperimentExecution(emaRequest)).resolves.toEqual(execution);

    expect(fetchMock).toHaveBeenCalledWith(
      `${API_BASE_URL}/api/v1/research/experiment-executions/ema-crossover`,
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify(emaRequest),
        cache: 'no-store',
      }),
    );
  });

  it('queues an RSI threshold experiment execution', async () => {
    const execution = buildExecution('rsi-threshold');
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(execution), {
        status: 202,
        headers: {
          'Content-Type': 'application/json',
        },
      }),
    );

    vi.stubGlobal('fetch', fetchMock);

    await expect(createRsiThresholdExperimentExecution(rsiRequest)).resolves.toEqual(execution);

    expect(fetchMock).toHaveBeenCalledWith(
      `${API_BASE_URL}/api/v1/research/experiment-executions/rsi-threshold`,
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify(rsiRequest),
        cache: 'no-store',
      }),
    );
  });
});
