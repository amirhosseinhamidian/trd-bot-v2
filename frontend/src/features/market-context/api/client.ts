import { getJson } from '@/lib/api/core/transport';
import type { Page } from '@/lib/api/core/types';

import type { MarketContextProductView } from './types';

export interface MarketContextFilters {
  limit?: number;
  offset?: number;
  source?: string;
  baseAsset?: string;
  quoteAsset?: string;
  marketType?: 'spot';
}

export async function getMarketContexts(
  filters: MarketContextFilters = {},
): Promise<Page<MarketContextProductView>> {
  const params = new URLSearchParams();
  params.set('limit', String(filters.limit ?? 12));
  params.set('offset', String(filters.offset ?? 0));
  if (filters.source) params.set('source', filters.source);
  if (filters.baseAsset) params.set('base_asset', filters.baseAsset);
  if (filters.quoteAsset) params.set('quote_asset', filters.quoteAsset);
  if (filters.marketType) params.set('market_type', filters.marketType);
  return getJson<Page<MarketContextProductView>>(`/api/v1/market-context?${params.toString()}`);
}

export async function getMarketContextAssessment(
  assessmentId: string,
): Promise<MarketContextProductView> {
  return getJson<MarketContextProductView>(
    `/api/v1/market-context/${encodeURIComponent(assessmentId)}`,
  );
}
