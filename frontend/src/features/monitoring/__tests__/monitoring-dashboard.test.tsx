import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import type { MonitoringSummary } from '@/features/monitoring/api/types';
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

describe('MonitoringDashboard', () => {
  it('renders persisted operational health without recovery mutations', () => {
    render(<MonitoringDashboard locale="en" summary={summary} />);

    expect(screen.getByText('Operational health')).toBeInTheDocument();
    expect(screen.getByText('25%')).toBeInTheDocument();
    expect(screen.getByText('provider_unavailable')).toBeInTheDocument();
    expect(screen.getAllByText('job_handler_failed').length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText('job-1234567890abcdef1234')).toBeInTheDocument();
    expect(screen.getByText(/Overall status: Critical/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /retry|cancel/i })).toBeNull();
  });

  it('renders legacy capacity summaries without an operations block', () => {
    render(<MonitoringDashboard locale="en" summary={{ ...summary, operations: null }} />);

    expect(screen.queryByText('Operational health')).toBeNull();
    expect(screen.getByText('System architecture monitoring')).toBeInTheDocument();
  });
});
