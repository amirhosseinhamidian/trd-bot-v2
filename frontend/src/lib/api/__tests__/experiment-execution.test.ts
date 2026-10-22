import { afterEach, describe, expect, it, vi } from 'vitest';

import { createExperimentExecution } from '@/features/experiments/api/client';
import type {
  ExperimentExecution,
  ExperimentExecutionSubmission,
  StoredDatasetEMACrossoverExecutionRequest,
  StoredDatasetRSIThresholdExecutionRequest,
} from '@/features/experiments/api/types';
import { API_BASE_URL } from '@/lib/api/core/transport';

const emaRequest: StoredDatasetEMACrossoverExecutionRequest = {
  dataset_id: 'dataset-btc-usdt-1h',
  strategy_name: 'ema-crossover',
  strategy_version: '1.0.0',
  fast_period: 9,
  slow_period: 21,
  horizon_candles: 1,
  starting_balance: '10000',
  allocation_fraction: '0.10',
  fee_rate: '0.001',
  slippage_rate: '0.0005',
};

const rsiRequest: StoredDatasetRSIThresholdExecutionRequest = {
  dataset_id: 'dataset-btc-usdt-1h',
  strategy_name: 'rsi-threshold',
  strategy_version: '1.0.0',
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

function buildSubmission(
  strategyName: 'ema-crossover' | 'rsi-threshold',
): ExperimentExecutionSubmission {
  return {
    ...buildExecution(strategyName),
    created: true,
    job: {
      job_id: 'job-1234567890abcdef1234',
      kind: 'experiment_execution',
      status: 'queued',
      progress_percent: 0,
      attempt_count: 0,
      max_attempts: 3,
      run_after: '2026-08-30T07:00:00Z',
      lease_expires_at: null,
      cancel_requested: false,
      result_reference: null,
      error_code: null,
      error_message: null,
      created_at: '2026-08-30T07:00:00Z',
      updated_at: '2026-08-30T07:00:00Z',
      started_at: null,
      finished_at: null,
    },
  };
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('experiment execution client', () => {
  it('queues an EMA crossover experiment execution', async () => {
    const submission = buildSubmission('ema-crossover');
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(submission), {
        status: 202,
        headers: {
          'Content-Type': 'application/json',
        },
      }),
    );

    vi.stubGlobal('fetch', fetchMock);

    await expect(createExperimentExecution(emaRequest)).resolves.toEqual(submission);

    expect(fetchMock).toHaveBeenCalledWith(
      `${API_BASE_URL}/api/v1/research/experiment-executions`,
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify(emaRequest),
        cache: 'no-store',
      }),
    );
  });

  it('queues an RSI threshold experiment execution', async () => {
    const submission = buildSubmission('rsi-threshold');
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(submission), {
        status: 202,
        headers: {
          'Content-Type': 'application/json',
        },
      }),
    );

    vi.stubGlobal('fetch', fetchMock);

    await expect(createExperimentExecution(rsiRequest)).resolves.toEqual(submission);

    expect(fetchMock).toHaveBeenCalledWith(
      `${API_BASE_URL}/api/v1/research/experiment-executions`,
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify(rsiRequest),
        cache: 'no-store',
      }),
    );
  });
});
