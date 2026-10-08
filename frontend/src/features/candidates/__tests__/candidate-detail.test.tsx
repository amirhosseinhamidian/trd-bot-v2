import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import type {
  CandidateDecisionLineage,
  CandidateJournalOccurrence,
  CandidateProjectionDetail,
} from '@/features/candidates/api/types';
import CandidateDetail from '@/features/candidates/candidate-detail';
import type { Page } from '@/lib/api/types';

const mocks = vi.hoisted(() => ({
  getCandidateLineage: vi.fn(),
}));

vi.mock('@/features/candidates/api/client', () => ({
  getCandidateLineage: mocks.getCandidateLineage,
}));

function makeOccurrence(journalId: string, recordedAt: string): CandidateJournalOccurrence {
  return {
    journal_id: journalId,
    recorded_at: recordedAt,
    evaluated_at: recordedAt,
    portfolio_id: 'portfolio-0000000000000001',
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
      strategy_name: 'rsi-threshold',
      strategy_version: '1.0.0',
      confidence: '0.82',
      signal_score: '0.74',
      created_at: '2026-08-26T10:00:00Z',
      valid_until: '2026-08-26T14:00:00Z',
    },
    rank: 1,
    ranking_score: '0.81',
    occurrence_type: 'attempted',
    replay_status: 'opened',
    risk_decision: 'approved',
    skip_reason: null,
    selected: true,
    position_id: 'position-1',
    exit_reason: 'target',
    decision_evidence: null,
  };
}

function makeSkippedOccurrence(journalId: string, recordedAt: string): CandidateJournalOccurrence {
  const attempted = makeOccurrence(journalId, recordedAt);

  return {
    ...attempted,
    candidate: {
      ...attempted.candidate,
      status: 'candidate',
    },
    occurrence_type: 'skipped',
    replay_status: null,
    risk_decision: null,
    skip_reason: 'position_opened',
    selected: false,
    position_id: null,
    exit_reason: null,
  };
}

function makeDetail(): CandidateProjectionDetail {
  const latest = makeOccurrence('journal-1', '2026-08-26T12:00:00Z');

  return makeDetailForOccurrence(latest);
}

function makeDecisionLineage(occurrence: CandidateJournalOccurrence): CandidateDecisionLineage {
  const hasPosition = occurrence.position_id !== null;

  return {
    lineage_version: 'candidate-decision-lineage-v1',
    journal_id: occurrence.journal_id,
    nodes: [
      {
        kind: 'dataset',
        status: 'available',
        resource_id: occurrence.candidate.dataset_id,
        portfolio_id: null,
        outcome: null,
        reason: null,
      },
      {
        kind: 'experiment',
        status: 'available',
        resource_id: occurrence.candidate.experiment_id,
        portfolio_id: null,
        outcome: null,
        reason: null,
      },
      {
        kind: 'signal',
        status: 'available',
        resource_id: occurrence.candidate.signal_id,
        portfolio_id: null,
        outcome: null,
        reason: null,
      },
      {
        kind: 'candidate',
        status: 'available',
        resource_id: occurrence.candidate.candidate_id,
        portfolio_id: null,
        outcome: null,
        reason: null,
      },
      {
        kind: 'risk',
        status: occurrence.risk_decision ? 'available' : 'not_evaluated',
        resource_id: null,
        portfolio_id: null,
        outcome: occurrence.risk_decision,
        reason: occurrence.skip_reason,
      },
      {
        kind: 'position',
        status: hasPosition ? 'available' : 'not_created',
        resource_id: occurrence.position_id,
        portfolio_id: occurrence.portfolio_id,
        outcome: null,
        reason: hasPosition ? null : (occurrence.replay_status ?? occurrence.skip_reason),
      },
      {
        kind: 'exit',
        status: occurrence.exit_reason ? 'available' : 'not_created',
        resource_id: occurrence.position_id,
        portfolio_id: occurrence.portfolio_id,
        outcome: occurrence.exit_reason,
        reason: occurrence.exit_reason ? null : 'position_not_created',
      },
    ],
  };
}

function makeDetailForOccurrence(latest: CandidateJournalOccurrence): CandidateProjectionDetail {
  return {
    candidate: latest.candidate,
    occurrence_count: 1,
    journal_ids: [latest.journal_id],
    rank_history: [
      {
        journal_id: latest.journal_id,
        recorded_at: latest.recorded_at,
        rank: latest.rank,
        ranking_score: latest.ranking_score,
        selected: latest.selected,
        evidence_available: latest.decision_evidence !== null,
      },
    ],
    decision_lineage: makeDecisionLineage(latest),
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

  it('renders skipped detail and lineage without fabricated evaluation outcomes', () => {
    const skipped = makeSkippedOccurrence('journal-skipped', '2026-08-26T12:00:00Z');
    const detail = makeDetailForOccurrence(skipped);

    render(
      <CandidateDetail locale="en" candidate={detail} initialLineage={makePage([skipped], 0)} />,
    );

    expect(screen.getAllByText('Skipped').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('Not evaluated').length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByText('Earlier candidate position opened').length).toBeGreaterThanOrEqual(
      1,
    );
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
    expect(screen.getByRole('heading', { name: 'RSI Threshold' })).toBeInTheDocument();
    expect(screen.getByText('RSI Threshold · 1.0.0')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'View source: dataset-1' })).toHaveAttribute(
      'href',
      '/en/datasets/dataset-1',
    );
    expect(screen.getByRole('link', { name: 'View source: experiment-1' })).toHaveAttribute(
      'href',
      '/en/experiments/experiment-1',
    );
    expect(screen.getByRole('link', { name: 'View source: signal-1' })).toHaveAttribute(
      'href',
      '/en/signals/experiment-1/signal-1',
    );
    expect(screen.getAllByRole('link', { name: 'View source: position-1' })[0]).toHaveAttribute(
      'href',
      '/en/portfolios/portfolio-0000000000000001/positions/position-1',
    );

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

  it('shows rejected candidates without fabricating position or exit resources', () => {
    const attempted = makeOccurrence('journal-rejected', '2026-08-26T12:00:00Z');
    const rejected: CandidateJournalOccurrence = {
      ...attempted,
      candidate: { ...attempted.candidate, status: 'candidate' },
      replay_status: 'risk_rejected',
      risk_decision: 'rejected',
      selected: false,
      position_id: null,
      exit_reason: null,
    };

    render(
      <CandidateDetail
        locale="en"
        candidate={makeDetailForOccurrence(rejected)}
        initialLineage={makePage([rejected], 0)}
      />,
    );

    expect(screen.getAllByText('Rejected').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('Not created yet')).toHaveLength(2);
    expect(screen.queryByRole('link', { name: /position-1/i })).toBeNull();
  });
});
