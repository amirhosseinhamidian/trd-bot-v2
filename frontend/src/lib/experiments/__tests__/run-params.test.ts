import { describe, expect, it } from 'vitest';

import type { ExperimentSummary } from '@/lib/api/types';
import {
  buildExperimentRerunHref,
  parseExperimentExecutionId,
  parseExperimentRunSearchParams,
} from '@/lib/experiments/run-params';

const experiment: ExperimentSummary = {
  experiment_id: 'experiment-ema-btc',
  created_at: '2026-08-25T12:00:00Z',
  dataset_id: 'dataset-btc-usdt-1h',
  strategy_name: 'ema-crossover',
  strategy_version: '1.0.0',
  horizon_candles: 3,
  parameters: [
    {
      name: 'fast_period',
      value: '12',
    },
    {
      name: 'slow_period',
      value: '34',
    },
    {
      name: 'starting_balance',
      value: '25000',
    },
    {
      name: 'allocation_fraction',
      value: '0.20',
    },
    {
      name: 'fee_rate',
      value: '0.002',
    },
    {
      name: 'slippage_rate',
      value: '0.0008',
    },
  ],
  generated_signals: 4,
  total_trades: 2,
  net_pnl: '500',
  total_return: '0.02',
  win_rate: '0.5',
  max_drawdown_fraction: '0.01',
  profit_factor: '1.5',
  benchmark_type: 'buy_and_hold',
  benchmark_return: '0.01',
  excess_return: '0.01',
  benchmark_max_drawdown_fraction: '0.02',
  max_drawdown_fraction_delta: '-0.01',
  strategy_has_lower_drawdown: true,
  comparison_outcome: 'strategy',
};

const rsiExperiment: ExperimentSummary = {
  ...experiment,
  experiment_id: 'experiment-rsi-btc',
  strategy_name: 'rsi-threshold',
  parameters: [
    {
      name: 'period',
      value: '14',
    },
    {
      name: 'oversold_threshold',
      value: '30',
    },
    {
      name: 'overbought_threshold',
      value: '70',
    },
    {
      name: 'starting_balance',
      value: '25000',
    },
    {
      name: 'allocation_fraction',
      value: '0.20',
    },
    {
      name: 'fee_rate',
      value: '0.002',
    },
    {
      name: 'slippage_rate',
      value: '0.0008',
    },
  ],
};

describe('experiment run parameters', () => {
  it('builds a localized rerun URL from an experiment', () => {
    const href = buildExperimentRerunHref(experiment, 'en');

    const url = new URL(href, 'http://localhost');

    expect(url.pathname).toBe('/en/experiments');

    expect(Object.fromEntries(url.searchParams.entries())).toEqual({
      dataset_id: 'dataset-btc-usdt-1h',
      horizon_candles: '3',
      strategy: 'ema-crossover',
      fast_period: '12',
      slow_period: '34',
      starting_balance: '25000',
      allocation_fraction: '0.20',
      fee_rate: '0.002',
      slippage_rate: '0.0008',
    });
  });

  it('builds an RSI rerun URL with strategy-specific parameters', () => {
    const href = buildExperimentRerunHref(rsiExperiment, 'fa');
    const url = new URL(href, 'http://localhost');

    expect(url.pathname).toBe('/fa/experiments');
    expect(Object.fromEntries(url.searchParams.entries())).toEqual({
      dataset_id: 'dataset-btc-usdt-1h',
      horizon_candles: '3',
      strategy: 'rsi-threshold',
      rsi_period: '14',
      oversold_threshold: '30',
      overbought_threshold: '70',
      starting_balance: '25000',
      allocation_fraction: '0.20',
      fee_rate: '0.002',
      slippage_rate: '0.0008',
    });
  });

  it('parses valid RSI rerun values', () => {
    expect(
      parseExperimentRunSearchParams({
        dataset_id: 'dataset-btc-usdt-1h',
        strategy: 'rsi-threshold',
        rsi_period: '14',
        oversold_threshold: '30',
        overbought_threshold: '70',
      }),
    ).toEqual({
      datasetId: 'dataset-btc-usdt-1h',
      strategyName: 'rsi-threshold',
      rsiPeriod: '14',
      oversoldThreshold: '30',
      overboughtThreshold: '70',
    });
  });

  it('parses valid rerun values', () => {
    expect(
      parseExperimentRunSearchParams({
        dataset_id: 'dataset-btc-usdt-1h',
        strategy: 'ema-crossover',
        fast_period: '12',
        slow_period: '34',
        horizon_candles: '3',
        starting_balance: '25000',
        allocation_fraction: '0.20',
        fee_rate: '0.002',
        slippage_rate: '0.0008',
      }),
    ).toEqual({
      datasetId: 'dataset-btc-usdt-1h',
      strategyName: 'ema-crossover',
      fastPeriod: '12',
      slowPeriod: '34',
      horizonCandles: '3',
      startingBalance: '25000',
      allocationFraction: '0.20',
      feeRate: '0.002',
      slippageRate: '0.0008',
    });
  });

  it('ignores invalid and unsafe query values', () => {
    expect(
      parseExperimentRunSearchParams({
        dataset_id: '   ',
        strategy: 'unknown',
        fast_period: '1',
        slow_period: '2',
        rsi_period: '1',
        oversold_threshold: '50',
        overbought_threshold: '50',
        horizon_candles: '0',
        starting_balance: '-100',
        allocation_fraction: '2',
        fee_rate: '1',
        slippage_rate: '-0.1',
      }),
    ).toEqual({});
  });

  it('accepts the first value when Next.js provides an array', () => {
    expect(
      parseExperimentRunSearchParams({
        dataset_id: ['dataset-first', 'dataset-second'],
        fast_period: ['9', '100'],
      }),
    ).toEqual({
      datasetId: 'dataset-first',
      fastPeriod: '9',
    });
  });

  it('parses a valid experiment execution ID', () => {
    expect(
      parseExperimentExecutionId({
        execution: 'execution-1234567890abcdef',
      }),
    ).toBe('execution-1234567890abcdef');
  });

  it('accepts the first execution ID from an array', () => {
    expect(
      parseExperimentExecutionId({
        execution: ['execution-1234567890abcdef', 'execution-fedcba0987654321'],
      }),
    ).toBe('execution-1234567890abcdef');
  });

  it('ignores an invalid experiment execution ID', () => {
    expect(
      parseExperimentExecutionId({
        execution: 'invalid-execution',
      }),
    ).toBeUndefined();
  });

  it('ignores an execution ID with an invalid length', () => {
    expect(
      parseExperimentExecutionId({
        execution: 'execution-1234',
      }),
    ).toBeUndefined();
  });

  it('ignores an execution ID containing uppercase characters', () => {
    expect(
      parseExperimentExecutionId({
        execution: 'execution-1234567890ABCDEF',
      }),
    ).toBeUndefined();
  });
});
