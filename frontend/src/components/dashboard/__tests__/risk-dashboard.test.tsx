import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import RiskDashboard from '@/components/dashboard/risk-dashboard';
import type {
  CandidateRiskCheckName,
  RiskDashboardReport,
  SimulatedPortfolioSummary,
} from '@/lib/api/types';

const mocks = vi.hoisted(() => ({
  getRiskDashboard: vi.fn(),
}));

vi.mock('@/lib/api/client', () => ({
  getRiskDashboard: mocks.getRiskDashboard,
}));

const riskChecks: CandidateRiskCheckName[] = [
  'candidate_selectable',
  'portfolio_active',
  'dataset_match',
  'portfolio_capacity',
  'rank_limit',
  'ranking_score',
  'reward_risk',
  'simulated_budget',
];

const portfolio: SimulatedPortfolioSummary = {
  portfolio_id: 'portfolio-1234567890abcdef',
  mode: 'paper',
  status: 'completed',
  dataset_id: 'dataset-btc-hourly',
  created_at: '2026-08-26T10:00:00Z',
  updated_at: '2026-08-26T16:00:00Z',
  starting_cash: '10000',
  cash: '10100',
  equity: '10100',
  fees_paid: '2',
  realized_pnl: '100',
  unrealized_pnl: '0',
  position_count: 1,
  event_count: 5,
};

function makeReport(evaluatedCount = 3): RiskDashboardReport {
  const isEmpty = evaluatedCount === 0;

  return {
    dashboard_version: 'risk-dashboard-v1',
    generated_at: '2026-08-27T10:00:00Z',
    from_time: null,
    to_time: null,
    portfolio_id: null,
    decision_window: 'inclusive_risk_assessment_evaluated_at',
    portfolio_snapshot_rule: 'latest_event_at_or_before_to_time',
    drawdown_window_rule: 'baseline_at_from_time_then_events_in_range',
    decisions: {
      evaluated_count: evaluatedCount,
      approved_count: isEmpty ? 0 : 2,
      rejected_count: isEmpty ? 0 : 1,
      approval_rate: isEmpty ? null : '0.666667',
    },
    rejection_reasons: riskChecks.map((name) => ({
      name,
      rejected_decisions: !isEmpty && name === 'ranking_score' ? 1 : 0,
    })),
    budget: {
      opened_decisions: isEmpty ? 0 : 1,
      allocated_risk_budget: isEmpty ? '0' : '100',
      consumed_risk: isEmpty ? '0' : '80',
      consumption_fraction: isEmpty ? null : '0.8',
    },
    portfolio_risk: {
      latest_event_at: '2026-08-26T16:00:00Z',
      portfolio_count: 1,
      open_position_count: 1,
      total_equity: '10100',
      simulated_exposure: '2000',
      exposure_fraction: '0.19802',
      exposure_limit_fraction: '0.25',
      exposure_within_limit: true,
      largest_pair: {
        base_asset: 'BTC',
        quote_asset: 'USDT',
        market_type: 'spot',
      },
      concentration_exposure: '2000',
      concentration_fraction: '0.19802',
      concentration_limit_fraction: '0.25',
      concentration_within_limit: true,
      max_drawdown_fraction: '0.012',
      drawdown_limit_fraction: '0.01',
      drawdown_within_limit: false,
    },
    decision_events: isEmpty
      ? []
      : [
          {
            event_id: 'risk-event-1111111111111111-2222222222222222',
            journal_id: 'journal-1111111111111111',
            candidate_id: 'candidate-2222222222222222',
            portfolio_id: portfolio.portfolio_id,
            evaluated_at: '2026-08-26T13:00:00Z',
            decision: 'rejected',
            replay_status: 'risk_rejected',
            primary_rejection_reason: 'ranking_score',
            failed_check_names: ['ranking_score', 'reward_risk'],
            risk_budget: '100',
            risk_consumed: '0',
            selected: false,
            position_id: null,
          },
        ],
    interpretation: 'historical_research_only',
  };
}

describe('RiskDashboard', () => {
  beforeEach(() => {
    mocks.getRiskDashboard.mockReset();
  });

  it('renders reconciled reasons, policy caps, and auditable resource links', () => {
    render(<RiskDashboard initialReport={makeReport()} locale="en" portfolios={[portfolio]} />);

    expect(screen.getByText('Research risk dashboard')).toBeInTheDocument();
    expect(screen.getByText('No live order execution')).toBeInTheDocument();
    expect(screen.getByText('66.67%')).toBeInTheDocument();
    expect(screen.getAllByText('Ranking score floor').length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText('Above cap')).toBeInTheDocument();

    expect(
      screen.getByRole('link', { name: 'View candidate and decision lineage' }),
    ).toHaveAttribute('href', '/en/candidates/candidate-2222222222222222#risk-decision');
    expect(screen.getByRole('link', { name: 'View portfolio report' })).toHaveAttribute(
      'href',
      '/en/portfolios/portfolio-1234567890abcdef',
    );
    expect(screen.queryByRole('button', { name: /buy|sell|open|close order/i })).toBeNull();
  });

  it('sends timezone-aware inclusive filter boundaries', async () => {
    const user = userEvent.setup();
    const nextReport = makeReport(0);
    mocks.getRiskDashboard.mockResolvedValue(nextReport);

    render(<RiskDashboard initialReport={makeReport()} locale="en" portfolios={[portfolio]} />);

    const fromValue = '2026-08-26T12:00';
    const toValue = '2026-08-26T14:00';
    fireEvent.change(screen.getByLabelText('From time'), { target: { value: fromValue } });
    fireEvent.change(screen.getByLabelText('To time'), { target: { value: toValue } });

    await user.click(screen.getByRole('button', { name: 'Apply filters' }));

    await waitFor(() => {
      expect(mocks.getRiskDashboard).toHaveBeenCalledWith({
        fromTime: new Date(fromValue).toISOString(),
        toTime: new Date(toValue).toISOString(),
        portfolioId: undefined,
      });
    });
    expect(await screen.findByText('No risk decisions in this scope')).toBeInTheDocument();
  });

  it('rejects an inverted time range before requesting the API', async () => {
    const user = userEvent.setup();

    render(<RiskDashboard initialReport={makeReport()} locale="en" portfolios={[portfolio]} />);

    fireEvent.change(screen.getByLabelText('From time'), {
      target: { value: '2026-08-27T12:00' },
    });
    fireEvent.change(screen.getByLabelText('To time'), {
      target: { value: '2026-08-26T12:00' },
    });
    await user.click(screen.getByRole('button', { name: 'Apply filters' }));

    expect(screen.getByRole('alert')).toHaveTextContent(
      'End time must be equal to or later than start time.',
    );
    expect(mocks.getRiskDashboard).not.toHaveBeenCalled();
  });
});
