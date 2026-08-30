import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import CandidateCatalog from '@/components/dashboard/candidate-catalog';
import type { CandidateProjectionSummary, Page } from '@/lib/api/types';

const mocks = vi.hoisted(() => ({
  getCandidateProjections: vi.fn(),
}));

vi.mock('@/lib/api/client', () => ({
  getCandidateProjections: mocks.getCandidateProjections,
}));

function makeCandidate(candidateId: string): CandidateProjectionSummary {
  return {
    candidate_id: candidateId,
    status: 'selected',
    action: 'long',
    pair: {
      base_asset: 'BTC',
      quote_asset: 'USDT',
      market_type: 'spot',
    },
    timeframe: '1h',
    strategy_name: 'rsi-threshold',
    strategy_version: '1.0.0',
    confidence: '0.82',
    signal_score: '0.74',
    created_at: '2026-08-26T10:00:00Z',
    valid_until: '2026-08-26T14:00:00Z',
    occurrence_count: 1,
    latest_journal_id: 'journal-0000000000000001',
    latest_recorded_at: '2026-08-26T12:00:00Z',
    latest_occurrence_type: 'attempted',
    latest_replay_status: 'opened',
    latest_risk_decision: 'approved',
    latest_skip_reason: null,
    selected: true,
    position_id: 'position-0000000000000001',
    exit_reason: 'target',
  };
}

function makeSkippedCandidate(candidateId: string): CandidateProjectionSummary {
  return {
    ...makeCandidate(candidateId),
    status: 'candidate',
    latest_occurrence_type: 'skipped',
    latest_replay_status: null,
    latest_risk_decision: null,
    latest_skip_reason: 'position_opened',
    selected: false,
    position_id: null,
    exit_reason: null,
  };
}

function makePage(
  items: CandidateProjectionSummary[],
  offset: number,
): Page<CandidateProjectionSummary> {
  return {
    items,
    total: 13,
    limit: 12,
    offset,
    count: items.length,
    has_next: offset === 0,
    has_previous: offset > 0,
  };
}

describe('CandidateCatalog', () => {
  beforeEach(() => {
    mocks.getCandidateProjections.mockReset();
  });

  it('renders skipped candidates as not evaluated with an explicit skip reason', () => {
    render(
      <CandidateCatalog
        locale="en"
        initialPage={makePage([makeSkippedCandidate('candidate-skipped')], 0)}
      />,
    );

    expect(screen.getByText('candidate-skipped')).toBeInTheDocument();
    expect(screen.getByText('Skipped')).toBeInTheDocument();
    expect(screen.getAllByText('Not evaluated')).toHaveLength(2);
    expect(screen.getByText('Earlier candidate position opened')).toBeInTheDocument();
  });

  it('loads the next persisted candidate page without exposing trade actions', async () => {
    const user = userEvent.setup();
    const nextPage = makePage([makeCandidate('candidate-next')], 12);

    mocks.getCandidateProjections.mockResolvedValue(nextPage);

    render(
      <CandidateCatalog
        locale="en"
        initialPage={makePage([makeCandidate('candidate-initial')], 0)}
      />,
    );

    expect(screen.getByText('Research candidates')).toBeInTheDocument();
    expect(screen.getByText('Research only')).toBeInTheDocument();
    expect(screen.getByText('candidate-initial')).toBeInTheDocument();
    expect(screen.getByText('RSI Threshold · 1.0.0')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Next' }));

    await waitFor(() => {
      expect(mocks.getCandidateProjections).toHaveBeenCalledWith({
        limit: 12,
        offset: 12,
      });
    });

    expect(await screen.findByText('candidate-next')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /view details and lineage/i })).toHaveAttribute(
      'href',
      '/en/candidates/candidate-next',
    );
    expect(screen.queryByRole('button', { name: /buy|sell|open|close/i })).toBeNull();
  });
});
