import { afterEach, describe, expect, it, vi } from 'vitest';

import { getRiskDashboard } from '@/features/risk/api/client';
import type { RiskDashboardReport } from '@/features/risk/api/types';
import { API_BASE_URL } from '@/lib/api/core/transport';

const report = {
  dashboard_version: 'risk-dashboard-v1',
  generated_at: '2026-08-27T10:00:00Z',
  from_time: null,
  to_time: null,
  portfolio_id: null,
  decision_window: 'inclusive_risk_assessment_evaluated_at',
  portfolio_snapshot_rule: 'latest_event_at_or_before_to_time',
  drawdown_window_rule: 'baseline_at_from_time_then_events_in_range',
  decisions: {
    evaluated_count: 0,
    approved_count: 0,
    rejected_count: 0,
    approval_rate: null,
  },
  rejection_reasons: [],
  budget: {
    opened_decisions: 0,
    allocated_risk_budget: '0',
    consumed_risk: '0',
    consumption_fraction: null,
  },
  portfolio_risk: {
    latest_event_at: null,
    portfolio_count: 0,
    open_position_count: 0,
    total_equity: '0',
    simulated_exposure: '0',
    exposure_fraction: null,
    exposure_limit_fraction: '0.25',
    exposure_within_limit: null,
    largest_pair: null,
    concentration_exposure: '0',
    concentration_fraction: null,
    concentration_limit_fraction: '0.25',
    concentration_within_limit: null,
    max_drawdown_fraction: null,
    drawdown_limit_fraction: '0.01',
    drawdown_within_limit: null,
  },
  decision_events: [],
  interpretation: 'historical_research_only',
} satisfies RiskDashboardReport;

function jsonResponse(value: unknown): Response {
  return new Response(JSON.stringify(value), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('risk dashboard client', () => {
  it('loads the unfiltered dashboard without a trailing query marker', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(report));
    vi.stubGlobal('fetch', fetchMock);

    await expect(getRiskDashboard()).resolves.toEqual(report);

    expect(fetchMock).toHaveBeenCalledWith(
      `${API_BASE_URL}/api/v1/research/risk`,
      expect.objectContaining({ method: 'GET', cache: 'no-store' }),
    );
  });

  it('encodes inclusive time boundaries and the portfolio filter', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(report));
    vi.stubGlobal('fetch', fetchMock);

    await getRiskDashboard({
      fromTime: '2026-08-26T12:00:00.000Z',
      toTime: '2026-08-26T14:00:00.000Z',
      portfolioId: 'portfolio-1234567890abcdef',
    });

    expect(String(fetchMock.mock.calls[0]?.[0])).toBe(
      `${API_BASE_URL}/api/v1/research/risk?from_time=2026-08-26T12%3A00%3A00.000Z&to_time=2026-08-26T14%3A00%3A00.000Z&portfolio_id=portfolio-1234567890abcdef`,
    );
  });
});
