import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { PortfolioAnalytics } from '@/features/portfolios/portfolio-analytics';
import type { PortfolioAnalyticsReport } from '@/lib/api/portfolio-analytics';

const chart = vi.hoisted(() => vi.fn());
vi.mock('@/components/charts/historical-line-chart', () => ({
  HistoricalLineChart: (props: unknown) => {
    chart(props);
    return null;
  },
}));

const report: PortfolioAnalyticsReport = {
  analytics_version: 'portfolio-analytics-v1',
  portfolio_id: 'portfolio-1234567890abcdef',
  as_of: '2026-08-26T17:00:00Z',
  starting_equity: '1000',
  ending_equity: '1009.48',
  net_pnl: '9.48',
  return_fraction: '0.00948',
  fees_paid: '0.52',
  closed_net_pnl: '19.58',
  open_gross_unrealized_pnl: '-10',
  open_entry_fees: '0.1',
  open_net_pnl: '-10.1',
  closed_count: 1,
  open_count: 1,
  winning_count: 1,
  losing_count: 0,
  breakeven_count: 0,
  win_rate: '1',
  profit_factor: null,
  profit_factor_status: 'no_losses',
  expectancy: '19.58',
  average_hold_seconds: '7200',
  duration_seconds: '18000',
  max_drawdown_fraction: '0.01',
  max_drawdown_duration_seconds: '7200',
  current_drawdown_duration_seconds: '7200',
  open_exposure: '90',
  exposure_fraction: '0.08915481',
  equity_points: [
    {
      event_id: 'event-1',
      sequence_number: 1,
      timestamp: '2026-08-26T12:00:00Z',
      equity: '1000',
      return_fraction: '0',
      drawdown_fraction: '0',
      drawdown_duration_seconds: '0',
    },
    {
      event_id: 'event-2',
      sequence_number: 2,
      timestamp: '2026-08-26T17:00:00Z',
      equity: '1009.48',
      return_fraction: '0.00948',
      drawdown_fraction: '0.01',
      drawdown_duration_seconds: '7200',
    },
  ],
  trades_by_pair: [
    {
      pair: { base_asset: 'BTC', quote_asset: 'USDT', market_type: 'spot' },
      closed_count: 1,
      open_count: 0,
      net_realized_pnl: '19.58',
      fees_paid: '0.42',
    },
    {
      pair: { base_asset: 'ETH', quote_asset: 'USDT', market_type: 'spot' },
      closed_count: 0,
      open_count: 1,
      net_realized_pnl: '0',
      fees_paid: '0.1',
    },
  ],
  exit_mix: [{ reason: 'unknown', count: 1 }],
  interpretation: 'historical_research_only',
};

describe('PortfolioAnalytics', () => {
  it('shows net fee accounting, pair totals and explicit missing exit evidence', () => {
    render(<PortfolioAnalytics report={report} locale="en" />);
    expect(screen.getByText('Portfolio performance')).toBeInTheDocument();
    expect(screen.getByText(/Net PnL = closed net PnL/)).toBeInTheDocument();
    expect(screen.getByText(/no losing closed trades/)).toBeInTheDocument();
    const pairs = screen.getByRole('table', { name: 'Trades by pair' });
    expect(screen.getByRole('region', { name: 'Trades by pair' })).toHaveAttribute('tabindex', '0');
    expect(within(pairs).getByText('19.58')).toBeInTheDocument();
    expect(within(pairs).getByText('ETH/USDT')).toBeInTheDocument();
    expect(screen.getByText('Unknown: 1')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /buy|sell|order/i })).toBeNull();
  });

  it('plots the same event values as the evidence table using step-after curves', async () => {
    const user = userEvent.setup();
    chart.mockClear();
    render(<PortfolioAnalytics report={report} locale="en" />);
    expect(chart).toHaveBeenCalledWith(
      expect.objectContaining({
        ariaLabel: 'Recorded equity',
        series: [
          expect.objectContaining({
            curve: 'step_after',
            points: report.equity_points.map((point) => ({
              timestamp: point.timestamp,
              value: Number(point.equity),
            })),
          }),
        ],
      }),
    );
    await user.click(screen.getByText('Event values used by the charts'));
    const table = screen.getByRole('table', {
      name: 'Event values used by the charts',
    });
    expect(screen.getByRole('region', { name: 'Event values used by the charts' })).toHaveAttribute(
      'tabindex',
      '0',
    );
    expect(within(table).getByText('1,009.48')).toBeInTheDocument();
    expect(within(table).getByText('0.948%')).toBeInTheDocument();
  });

  it('renders undefined trade metrics explicitly rather than as zero', () => {
    render(
      <PortfolioAnalytics
        locale="en"
        report={{
          ...report,
          closed_count: 0,
          win_rate: null,
          expectancy: null,
          average_hold_seconds: null,
          profit_factor_status: 'no_closed_trades',
          trades_by_pair: [],
          exit_mix: [],
        }}
      />,
    );
    expect(screen.getByText(/No closed trades:/)).toBeInTheDocument();
    expect(screen.getAllByText('Unavailable')).toHaveLength(4);
    expect(screen.queryByText(/no losing closed trades/)).toBeNull();
  });

  it('renders Persian labels and numbers', () => {
    render(<PortfolioAnalytics report={report} locale="fa" />);
    expect(screen.getByText('تحلیل عملکرد پرتفوی')).toBeInTheDocument();
    expect(screen.getByText('نامشخص: ۱')).toBeInTheDocument();
    expect(screen.getByText('سود خالص موقعیت باز')).toBeInTheDocument();
  });
});
