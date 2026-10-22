export type ResearchStrategyName = 'ema-crossover' | 'rsi-threshold' | 'sma-crossover';

export type StrategyParameterKind = 'integer' | 'decimal';

export interface StrategyParameterMetadata {
  name: string;
  kind: StrategyParameterKind;
  default_value: string;
  minimum: string | null;
  maximum: string | null;
  minimum_exclusive: boolean;
  maximum_exclusive: boolean;
}

export interface ResearchStrategyMetadata {
  name: string;
  version: string;
  display_name: string;
  description: string;
  parameters: StrategyParameterMetadata[];
  lifecycle_status?: 'active' | 'deprecated';
  supersedes_version?: string | null;
  behavior_fingerprint?: string;
}
