import type { DatasetTimeframe, TradingPair } from '@/features/datasets/api/types';

export type SignalDirection = 'long' | 'short' | 'neutral';

export type ExperimentSignalSortDirection = 'asc' | 'desc';

export interface StrategyFeature {
  name: string;
  value: string;
}

export interface StrategySignal {
  signal_id: string;
  strategy_name: string;
  strategy_version: string;
  dataset_id: string;
  pair: TradingPair;
  timeframe: DatasetTimeframe;
  candle_open_time: string;
  candle_close_time: string;
  generated_at: string;
  direction: SignalDirection;
  score: string;
  reason: string;
  features: StrategyFeature[];
}
