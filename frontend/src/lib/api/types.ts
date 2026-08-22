export type ResearchStage =
  | "empty"
  | "data_available"
  | "experiments_available"
  | "walk_forward_available";

export type ResearchActivityType =
  | "dataset"
  | "experiment"
  | "walk_forward_run";

export interface TradingPair {
  base_asset: string;
  quote_asset: string;
  market_type: string;
}

export interface DatasetSummary {
  dataset_id: string;
  schema_version: number;
  name: string;
  source: string;
  pair: TradingPair;
  timeframe: string;
  start_time: string;
  end_time: string;
  created_at: string;
  candle_count: number;
  checksum: string;
}

export interface ExperimentParameter {
  name: string;
  value: string;
}

export interface ExperimentSummary {
  experiment_id: string;
  created_at: string;
  dataset_id: string;
  strategy_name: string;
  strategy_version: string;
  horizon_candles: number;
  parameters: ExperimentParameter[];
  generated_signals: number;
  total_trades: number;
  net_pnl: string;
  total_return: string;
  win_rate: string | null;
  max_drawdown_fraction: string;
  profit_factor: string | null;
  benchmark_type: "buy_and_hold";
  benchmark_return: string;
  excess_return: string;
  benchmark_max_drawdown_fraction: string;
  max_drawdown_fraction_delta: string;
  strategy_has_lower_drawdown: boolean;
  comparison_outcome:
    | "strategy"
    | "benchmark"
    | "tie";
}

export interface WalkForwardRunSummary {
  execution_id: string;
  created_at: string;
  source_dataset_id: string;
  plan_id: string;
  strategy_name: string;
  strategy_version: string;
  horizon_candles: number;
  total_folds: number;
  total_signals: number;
  folds_with_trades: number;
  strategy_wins: number;
  benchmark_wins: number;
  ties: number;
  average_strategy_return: string;
  average_benchmark_return: string;
  average_excess_return: string;
  worst_max_drawdown_fraction: string;
}

export interface AcceptancePolicy {
  minimum_total_trades: number;
  minimum_excess_return: string;
  maximum_drawdown_fraction: string;
}

export interface AcceptancePolicyPreset {
  preset_id: string;
  name: string;
  version: number;
  description: string;
  policy: AcceptancePolicy;
  interpretation: "historical_research_only";
}

export interface ResearchOverview {
  dataset_count: number;
  experiment_count: number;
  walk_forward_run_count: number;
  acceptance_policy_preset_count: number;
  research_stage: ResearchStage;
  acceptance_policy_presets:
    AcceptancePolicyPreset[];
  latest_dataset: DatasetSummary | null;
  latest_experiment: ExperimentSummary | null;
  latest_walk_forward_run:
    WalkForwardRunSummary | null;
}

export interface ResearchActivityItem {
  activity_type: ResearchActivityType;
  resource_id: string;
  created_at: string;
  label: string;
  dataset_id: string;
  strategy_name: string | null;
  strategy_version: string | null;
  horizon_candles: number | null;
}

export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
  count: number;
  has_next: boolean;
  has_previous: boolean;
}
