import { render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import type {
  MarketDataMonitoringSummary,
  MonitoringSummary,
} from '@/features/monitoring/api/types';
import MonitoringDashboard from '@/features/monitoring/monitoring-dashboard';

const summary: MonitoringSummary = {
  overall_status: 'critical',
  latest_metrics: [],
  active_recommendations: [],
  interpretation: 'capacity_planning_only',
  operations: {
    summary_version: 'operational-monitoring-v1',
    generated_at: '2026-09-28T12:00:00Z',
    connections: {
      total_count: 2,
      enabled_count: 1,
      healthy_count: 1,
      unhealthy_count: 1,
      untested_count: 0,
      latest_tested_at: '2026-09-28T11:55:00Z',
      latest_error_at: '2026-09-28T11:55:00Z',
      latest_error_code: 'provider_unavailable',
    },
    imports: {
      sample_size: 4,
      succeeded_count: 3,
      failed_count: 1,
      failure_rate: '0.25',
      latest_success_at: '2026-09-28T11:40:00Z',
      latest_failure_at: '2026-09-28T11:50:00Z',
      latest_failure_code: 'provider_unavailable',
    },
    jobs: {
      total_count: 7,
      queued_count: 2,
      running_count: 1,
      stuck_count: 1,
      succeeded_count: 3,
      failed_count: 1,
      cancelled_count: 0,
      recent_terminal_sample_size: 4,
      average_duration_seconds: '12.5',
      latest_success_at: '2026-09-28T11:40:00Z',
      latest_failure_at: '2026-09-28T11:50:00Z',
      failure_reasons: [{ error_code: 'job_handler_failed', count: 1 }],
      recent_jobs: [
        {
          job_id: 'job-1234567890abcdef1234',
          kind: 'market_data_import',
          status: 'failed',
          progress_percent: 75,
          attempt_count: 2,
          max_attempts: 2,
          run_after: '2026-09-28T11:30:00Z',
          lease_expires_at: null,
          cancel_requested: false,
          result_reference: null,
          error_code: 'job_handler_failed',
          created_at: '2026-09-28T11:30:00Z',
          updated_at: '2026-09-28T11:50:00Z',
          started_at: '2026-09-28T11:35:00Z',
          finished_at: '2026-09-28T11:50:00Z',
        },
      ],
    },
  },
};

const marketData: MarketDataMonitoringSummary = {
  schema_version: 'market-data-monitoring-v1',
  generated_at: '2026-10-14T12:10:00Z',
  overall_status: 'warning',
  stream_count: 1,
  healthy_count: 0,
  degraded_count: 1,
  stale_count: 1,
  no_data_count: 0,
  paused_count: 0,
  backlog: {
    poll_jobs: 2,
    replay_jobs: 1,
    overdue_watchlists: 1,
    finalization_windows: 3,
    unrequested_revisions: 0,
    pending_replays: 1,
    failed_replays: 0,
    completed_revisions: 4,
  },
  streams: [
    {
      watchlist_id: 'market-watch-1234567890abcdef',
      pair: { base_asset: 'BTC', quote_asset: 'USDT', market_type: 'spot' },
      timeframe: '1h',
      watchlist_state: 'active',
      health_status: 'degraded',
      freshness_status: 'stale',
      provider_routes: [
        {
          ordinal: 1,
          provider_id: 'kraken-public',
          connection_id: 'market-data-connection-kraken',
          connection_state: 'enabled',
          health_status: 'healthy',
          last_tested_at: '2026-10-14T12:00:00Z',
          last_error_code: null,
        },
        {
          ordinal: 2,
          provider_id: 'binance-public',
          connection_id: 'market-data-connection-binance',
          connection_state: 'enabled',
          health_status: 'healthy',
          last_tested_at: '2026-10-14T12:00:00Z',
          last_error_code: null,
        },
      ],
      selected_provider_id: 'kraken-public',
      latest_poll_status: 'succeeded',
      latest_poll_completed_at: '2026-10-14T12:01:00Z',
      latest_poll_error_code: null,
      latest_finalized_window_end: '2026-10-14T10:00:00Z',
      latest_watermark_time: '2026-10-14T11:55:00Z',
      data_age_seconds: 7800,
      lag_seconds: 4200,
      freshness_target_seconds: 600,
      poll_overdue_seconds: 60,
      finalization_backlog_count: 3,
    },
  ],
  recent_replays: [
    {
      replay_id: 'market-replay-1234567890abcdef',
      decision_id: 'market-decision-1234567890abcdef',
      window_id: 'market-window-1234567890abcdef',
      reason: 'late_arrival',
      requested_by: 'operator:test',
      requested_at: '2026-10-14T12:08:00Z',
      job_id: 'job-abcdef12345678901234',
      job_status: 'running',
      error_code: null,
      revision_id: null,
      revision_kind: null,
      revised_version: null,
      completed_at: null,
    },
  ],
};

describe('MonitoringDashboard', () => {
  it('renders persisted operational health without recovery mutations', () => {
    render(<MonitoringDashboard locale="en" marketData={marketData} summary={summary} />);

    expect(screen.getByText('Operational health')).toBeInTheDocument();
    expect(screen.getByText('25%')).toBeInTheDocument();
    expect(screen.getByText('provider_unavailable')).toBeInTheDocument();
    expect(screen.getAllByText('job_handler_failed').length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByText('job-1234567890abcdef1234')).toHaveLength(2);
    expect(screen.getByText(/Overall status: Critical/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /retry|cancel/i })).toBeNull();
  });

  it('renders recent jobs as mobile cards and a labeled desktop table', () => {
    render(<MonitoringDashboard locale="en" marketData={marketData} summary={summary} />);

    const mobileList = screen.getByTestId('recent-jobs-mobile-list');
    const mobileJob = within(mobileList).getByRole('listitem');
    const desktopTable = screen.getByTestId('recent-jobs-table');
    const scrollRegion = within(desktopTable).getByRole('region', { name: 'Recent jobs' });

    expect(mobileList).toHaveClass('md:hidden');
    expect(mobileJob).toHaveClass('min-w-0');
    expect(within(mobileJob).getByText('job-1234567890abcdef1234')).toHaveClass(
      'min-w-0',
      'break-all',
    );
    expect(within(mobileJob).getByText('market_data_import')).toHaveClass('break-all');
    expect(desktopTable).toHaveClass('hidden', 'min-w-0', 'md:block');
    expect(scrollRegion).toHaveAttribute('tabindex', '0');
    expect(scrollRegion).toHaveClass('overflow-x-auto', 'rounded-none', 'border-0');
    expect(within(desktopTable).getByRole('table')).toHaveClass('min-w-[52rem]');
  });

  it('renders legacy capacity summaries without an operations block', () => {
    render(
      <MonitoringDashboard
        locale="en"
        marketData={marketData}
        summary={{ ...summary, operations: null }}
      />,
    );

    expect(screen.queryByText('Operational health')).toBeNull();
    expect(screen.getByText('System architecture monitoring')).toBeInTheDocument();
  });

  it('renders read-only market-data freshness, lag, backlog, and replay state', () => {
    render(<MonitoringDashboard locale="en" marketData={marketData} summary={summary} />);

    expect(screen.getByText('Market data health')).toBeInTheDocument();
    expect(screen.getByText(/Market data status: Needs review/)).toBeInTheDocument();
    expect(screen.getByText('BTC/USDT · 1h')).toBeInTheDocument();
    expect(screen.getByText('4,200 seconds')).toBeInTheDocument();
    expect(screen.getByText('market-replay-1234567890abcdef')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /replay|retry|trade|order/i })).toBeNull();
  });
});
