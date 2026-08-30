import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import ActivityFeed from '@/components/dashboard/activity-feed';
import type { Page, ResearchActivityItem } from '@/lib/api/types';

vi.mock('@/lib/api/client', () => ({
  getResearchActivity: vi.fn(),
}));

const page: Page<ResearchActivityItem> = {
  items: [
    {
      activity_type: 'experiment',
      resource_id: 'experiment-rsi-000001',
      created_at: '2026-08-30T08:00:00Z',
      label: 'rsi-threshold',
      dataset_id: 'dataset-rsi',
      strategy_name: 'rsi-threshold',
      strategy_version: '1.0.0',
      horizon_candles: 3,
    },
    {
      activity_type: 'dataset',
      resource_id: 'dataset-rsi',
      created_at: '2026-08-30T07:00:00Z',
      label: 'Historical RSI fixture',
      dataset_id: 'dataset-rsi',
      strategy_name: null,
      strategy_version: null,
      horizon_candles: null,
    },
  ],
  total: 2,
  limit: 10,
  offset: 0,
  count: 2,
  has_next: false,
  has_previous: false,
};

describe('ActivityFeed', () => {
  it('presents a registered RSI strategy while preserving dataset labels', () => {
    render(<ActivityFeed initialPage={page} locale="en" />);

    expect(screen.getByText('RSI Threshold')).toBeInTheDocument();
    expect(screen.getByText('v1.0.0')).toBeInTheDocument();
    expect(screen.getByText('Historical RSI fixture')).toBeInTheDocument();
    expect(screen.getByText('experiment-rsi-000001')).toBeInTheDocument();
  });
});
