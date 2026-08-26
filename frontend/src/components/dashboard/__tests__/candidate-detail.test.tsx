import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import CandidateDetail from '@/components/dashboard/candidate-detail';
import type { CandidateJournalOccurrence, CandidateProjectionDetail, Page } from '@/lib/api/types';

const mocks = vi.hoisted(() => ({
  getCandidateLineage: vi.fn(),
}));

vi.mock('@/lib/api/client', () => ({
  getCandidateLineage: mocks.getCandidateLineage,
}));

function makeOccurrence(journalId: string, recordedAt: string): CandidateJournalOccurrence {
  return {
    journal_id: journalId,
    recorded_at: recordedAt,
    candidate: {
      candidate_id: 'candidate-1',
      status: 'selected',
      action: 'long',
      dataset_id: 'dataset-1',
      experiment_id: 'experiment-1',
      signal_id: 'signal-1',
      pair: {
        base_asset: 'BTC',
        quote_asset: 'USDT',
        market_type: 'spot',
      },
      timeframe: '1h',
      strategy_name: 'ema-rsi',
      strategy_version: '1',
      confidence: '0.82',
      signal_score: '0.74',
      created_at: '2026-08-26T10:00:00Z',
      valid_until: '2026-08-26T14:00:00Z',
    },
    rank: 1,
    ranking_score: '0.81',
    replay_status: 'opened',
    risk_decision: 'approved',
    selected: true,
    position_id: 'position-1',
    exit_reason: 'target',
  };
}

function makeDetail(): CandidateProjectionDetail {
  const latest = makeOccurrence('journal-1', '2026-08-26T12:00:00Z');

  return {
    candidate: latest.candidate,
    occurrence_count: 2,
    journal_ids: ['journal-1', 'journal-0'],
    latest,
  };
}

function makePage(
  items: CandidateJournalOccurrence[],
  offset: number,
): Page<CandidateJournalOccurrence> {
  return {
    items,
    total: 11,
    limit: 10,
    offset,
    count: items.length,
    has_next: offset === 0,
    has_previous: offset > 0,
  };
}

describe('CandidateDetail', () => {
  beforeEach(() => {
    mocks.getCandidateLineage.mockReset();
  });

  it('renders read-only candidate lineage and loads the next lineage page', async () => {
    const user = userEvent.setup();
    const nextOccurrence = makeOccurrence('journal-next', '2026-08-26T11:00:00Z');

    mocks.getCandidateLineage.mockResolvedValue(makePage([nextOccurrence], 10));

    render(
      <CandidateDetail
        locale="en"
        candidate={makeDetail()}
        initialLineage={makePage([makeOccurrence('journal-initial', '2026-08-26T12:00:00Z')], 0)}
      />,
    );

    expect(screen.getByText('Research lineage')).toBeInTheDocument();
    expect(screen.getByText('journal-initial')).toBeInTheDocument();
    expect(screen.getByText('Research only')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Next' }));

    await waitFor(() => {
      expect(mocks.getCandidateLineage).toHaveBeenCalledWith('candidate-1', {
        limit: 10,
        offset: 10,
      });
    });

    expect(await screen.findByText('journal-next')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /buy|sell|open|close/i })).toBeNull();
  });
});
