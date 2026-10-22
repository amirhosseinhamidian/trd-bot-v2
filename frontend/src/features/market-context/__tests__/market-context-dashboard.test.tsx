import { render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import type { MarketContextProductView } from '@/features/market-context/api/types';
import MarketContextDashboard from '@/features/market-context/market-context-dashboard';
import type { Page } from '@/lib/api/core/types';

const current: MarketContextProductView = {
  schema_version: 'market-context-product-view-v1',
  evaluated_at: '2026-10-16T12:30:00Z',
  expected_as_of: '2026-10-16T12:00:00Z',
  consumable: true,
  unavailable_reasons: [],
  boundary_lag_seconds: 0,
  seconds_until_expiry: 1860,
  assessment: {
    schema_version: 'market-regime-assessment-v1',
    assessment_id: 'market-regime-1234567890abcdef',
    source: 'kraken-public',
    pair: { base_asset: 'BTC', quote_asset: 'USDT', market_type: 'spot' },
    as_of: '2026-10-16T12:00:00Z',
    input_manifest_id: 'market-context-input-1234567890abcdef',
    input_checksum: '1'.repeat(64),
    feature_set_version: 'market-context-features-v1',
    feature_set_checksum: '2'.repeat(64),
    feature_snapshot_id: 'market-context-features-1234567890abcdef',
    feature_snapshot_checksum: '3'.repeat(64),
    algorithm_version: 'market-regime-v1',
    status: 'ready',
    trend: 'trending_up',
    volatility: 'normal',
    confidence: '0.8250',
    evidence: [
      {
        feature_key: 'trend_slope_1h',
        timeframe: '1h',
        value: '0.010000000000',
        calculation_version: 'normalized-close-slope-v1',
        window_reference_checksums: ['4'.repeat(64), '5'.repeat(64)],
      },
    ],
    issue_codes: [],
    assessed_at: '2026-10-16T12:01:00Z',
    expires_at: '2026-10-16T13:01:00Z',
  },
};

const unavailable: MarketContextProductView = {
  ...current,
  consumable: false,
  unavailable_reasons: ['assessment_expired', 'boundary_mismatch'],
  boundary_lag_seconds: 3600,
  seconds_until_expiry: 0,
  assessment: {
    ...current.assessment,
    assessment_id: 'market-regime-abcdef1234567890',
    source: 'binance-public',
  },
};

const page: Page<MarketContextProductView> = {
  items: [current, unavailable],
  total: 2,
  limit: 12,
  offset: 0,
  count: 2,
  has_next: false,
  has_previous: false,
};

describe('MarketContextDashboard', () => {
  it('keeps the decision summary visible and raw lineage progressively disclosed', () => {
    render(<MarketContextDashboard initialPage={page} locale="en" />);

    expect(screen.getByRole('heading', { name: 'Market context' })).toBeInTheDocument();
    expect(screen.getAllByText('BTC/USDT')).toHaveLength(2);
    expect(screen.getAllByText('Trending up')).toHaveLength(2);
    expect(screen.getAllByText('Normal')).toHaveLength(2);
    expect(screen.getAllByText('82.5%')).toHaveLength(2);
    expect(screen.getByText('The assessment validity window has ended.')).toBeInTheDocument();
    expect(screen.getByText(/not aligned with the current boundary/)).toBeInTheDocument();

    const disclosures = screen
      .getAllByText('Feature evidence')
      .map((title) => title.closest('details'));
    expect(disclosures).toHaveLength(2);
    expect(disclosures.every((item) => item && !item.hasAttribute('open'))).toBe(true);
    expect(screen.getAllByText('Hourly trend slope')).toHaveLength(2);
    expect(screen.getAllByText('market-regime-v1')).toHaveLength(2);
    expect(screen.queryByRole('button', { name: /trade|order|evaluate|retry/i })).toBeNull();
  });

  it('uses responsive cards and exposes confidence through an accessible progressbar', () => {
    render(
      <MarketContextDashboard initialPage={{ ...page, items: [current], total: 1 }} locale="en" />,
    );

    const contextRegion = screen.getByRole('region', { name: 'Market context' });
    expect(contextRegion).toHaveClass('sm:grid-cols-2');
    const progress = screen.getByRole('progressbar', { name: 'Confidence' });
    expect(progress).toHaveAttribute('aria-valuenow', '83');
    const disclosure = screen.getByText('Feature evidence').closest('details');
    expect(disclosure).not.toBeNull();
    expect(within(disclosure!).getByText('2')).toBeInTheDocument();
  });

  it('renders a clear empty state', () => {
    render(
      <MarketContextDashboard
        initialPage={{ ...page, items: [], total: 0, count: 0 }}
        locale="en"
      />,
    );

    expect(screen.getByText('No market context has been recorded')).toBeInTheDocument();
  });
});
