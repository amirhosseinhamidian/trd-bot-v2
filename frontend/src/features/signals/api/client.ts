import { getJson } from '@/lib/api/core/transport';
import type { Page } from '@/lib/api/types';

import type { ExperimentSignalSortDirection, SignalDirection, StrategySignal } from './types';

export interface ExperimentSignalFilters {
  direction?: SignalDirection;
  candleCloseTimeFrom?: string;
  candleCloseTimeTo?: string;
  sortDirection?: ExperimentSignalSortDirection;
  limit?: number;
  offset?: number;
}

export async function getExperimentSignals(
  experimentId: string,
  filters: ExperimentSignalFilters = {},
): Promise<Page<StrategySignal>> {
  const encodedExperimentId = encodeURIComponent(experimentId);
  const params = new URLSearchParams();

  params.set('limit', String(filters.limit ?? 20));
  params.set('offset', String(filters.offset ?? 0));
  params.set('sort_direction', filters.sortDirection ?? 'desc');

  if (filters.direction) {
    params.set('direction', filters.direction);
  }

  if (filters.candleCloseTimeFrom) {
    params.set('candle_close_time_from', filters.candleCloseTimeFrom);
  }

  if (filters.candleCloseTimeTo) {
    params.set('candle_close_time_to', filters.candleCloseTimeTo);
  }

  return getJson<Page<StrategySignal>>(
    `/api/v1/research/experiments/${encodedExperimentId}/signals?${params.toString()}`,
  );
}

export async function getExperimentSignal(
  experimentId: string,
  signalId: string,
): Promise<StrategySignal> {
  const encodedExperimentId = encodeURIComponent(experimentId);
  const encodedSignalId = encodeURIComponent(signalId);

  return getJson<StrategySignal>(
    `/api/v1/research/experiments/${encodedExperimentId}/signals/${encodedSignalId}`,
  );
}
