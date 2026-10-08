import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import type {
  CandidateComparisonResult,
  CandidateDecisionEvidence,
  CandidateJournalOccurrence,
  CandidateProjectionSummary,
  CandidateRiskCheck,
} from '@/features/candidates/api/types';
import CandidateCatalog from '@/features/candidates/candidate-catalog';
import type { Page } from '@/lib/api/types';

const mocks = vi.hoisted(() => ({
  compareCandidates: vi.fn(),
  getCandidateProjections: vi.fn(),
}));

vi.mock('@/features/candidates/api/client', () => ({
  compareCandidates: mocks.compareCandidates,
  getCandidateProjections: mocks.getCandidateProjections,
}));

const riskCheckNames = [
  'candidate_selectable',
  'portfolio_active',
  'dataset_match',
  'portfolio_capacity',
  'rank_limit',
  'ranking_score',
  'reward_risk',
  'simulated_budget',
] as const;

function makeRiskChecks(rejected: boolean): CandidateRiskCheck[] {
  return riskCheckNames.map((name) =>
    name === 'reward_risk' && rejected
      ? {
          name,
          passed: false,
          actual_value: '1.20',
          limit_value: '1.50',
          reason: 'Reward-to-risk ratio is below the configured floor.',
        }
      : {
          name,
          passed: true,
          actual_value: 'true',
          limit_value: 'true',
          reason: 'Configured risk rule passed.',
        },
  );
}

function makeDecisionEvidence(
  candidateId: string,
  outcome: 'approved' | 'rejected' | 'not_evaluated' = 'approved',
): CandidateDecisionEvidence {
  return {
    evidence_version: 'candidate-decision-evidence-v1',
    candidate_id: candidateId,
    ranking: {
      score_version: 'candidate-ranking-score-v1',
      candidate_id: candidateId,
      rank: 1,
      total_score: '0.818000',
      formula: 'sum(weighted_components)',
      components: [
        {
          name: 'confidence',
          source_component: 'confidence',
          raw_value: '0.820000',
          weight: '0.450000',
          weighted_value: '0.369000',
          formula: 'round_half_up(raw_value * weight, 0.000001)',
        },
        {
          name: 'signal_quality',
          source_component: 'signal_strength',
          raw_value: '0.740000',
          weight: '0.350000',
          weighted_value: '0.259000',
          formula: 'round_half_up(raw_value * weight, 0.000001)',
        },
        {
          name: 'freshness',
          source_component: 'freshness',
          raw_value: '0.950000',
          weight: '0.200000',
          weighted_value: '0.190000',
          formula: 'round_half_up(raw_value * weight, 0.000001)',
        },
      ],
      tie_break: {
        tie_break_version: 'candidate-ranking-tie-break-v1',
        rule: 'total_score_desc_then_candidate_id_asc',
        applied: false,
        tied_candidate_ids: [],
        position_within_tie: null,
      },
    },
    risk_compatibility:
      outcome !== 'not_evaluated'
        ? {
            compatibility_version: 'candidate-risk-compatibility-v1',
            status: 'evaluated',
            affects_ranking_score: false,
            decision: outcome,
            passed_checks: outcome === 'rejected' ? 7 : 8,
            failed_checks: outcome === 'rejected' ? 1 : 0,
            compatibility_fraction: outcome === 'rejected' ? '0.875000' : '1.000000',
            failed_check_names: outcome === 'rejected' ? ['reward_risk'] : [],
            checks: makeRiskChecks(outcome === 'rejected'),
            not_evaluated_reason: null,
          }
        : {
            compatibility_version: 'candidate-risk-compatibility-v1',
            status: 'not_evaluated',
            affects_ranking_score: false,
            decision: null,
            passed_checks: 0,
            failed_checks: 0,
            compatibility_fraction: null,
            failed_check_names: [],
            checks: [],
            not_evaluated_reason: 'position_opened',
          },
  };
}

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
    latest_rank: 1,
    latest_ranking_score: '0.818000',
    latest_decision_evidence: makeDecisionEvidence(candidateId),
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
    latest_decision_evidence: makeDecisionEvidence(candidateId, 'not_evaluated'),
    selected: false,
    position_id: null,
    exit_reason: null,
  };
}

function makeRejectedCandidate(candidateId: string): CandidateProjectionSummary {
  return {
    ...makeCandidate(candidateId),
    status: 'candidate',
    latest_replay_status: 'risk_rejected',
    latest_risk_decision: 'rejected',
    latest_decision_evidence: makeDecisionEvidence(candidateId, 'rejected'),
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

function makeComparisonOccurrence(
  candidate: CandidateProjectionSummary,
): CandidateJournalOccurrence {
  return {
    journal_id: candidate.latest_journal_id,
    recorded_at: candidate.latest_recorded_at,
    evaluated_at: candidate.latest_recorded_at,
    portfolio_id: 'portfolio-0000000000000001',
    candidate: {
      candidate_id: candidate.candidate_id,
      status: candidate.status,
      action: candidate.action,
      dataset_id: 'dataset-1',
      experiment_id: 'experiment-1',
      signal_id: 'signal-1',
      pair: candidate.pair,
      timeframe: candidate.timeframe,
      strategy_name: candidate.strategy_name,
      strategy_version: candidate.strategy_version,
      confidence: candidate.confidence,
      signal_score: candidate.signal_score,
      created_at: candidate.created_at,
      valid_until: candidate.valid_until,
    },
    rank: candidate.latest_rank,
    ranking_score: candidate.latest_ranking_score,
    occurrence_type: candidate.latest_occurrence_type,
    replay_status: candidate.latest_replay_status,
    risk_decision: candidate.latest_risk_decision,
    skip_reason: candidate.latest_skip_reason,
    selected: candidate.selected,
    position_id: candidate.position_id,
    exit_reason: candidate.exit_reason,
    decision_evidence: candidate.latest_decision_evidence,
  };
}

describe('CandidateCatalog', () => {
  beforeEach(() => {
    mocks.compareCandidates.mockReset();
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
    expect(screen.getAllByText('Not evaluated').length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByText('Earlier candidate position opened').length).toBeGreaterThanOrEqual(
      1,
    );
  });

  it('shows versioned score contributions and post-ranking risk evidence', () => {
    render(
      <CandidateCatalog
        locale="en"
        initialPage={makePage([makeRejectedCandidate('candidate-explained')], 0)}
      />,
    );

    expect(screen.getByText('Why this rank?')).toBeInTheDocument();
    expect(screen.getByText(/candidate-ranking-score-v1/)).toBeInTheDocument();
    expect(screen.getByText('Signal quality')).toBeInTheDocument();
    expect(screen.getByText('87.5% · 7/8')).toBeInTheDocument();
    expect(screen.getByText('Reward to risk')).toBeInTheDocument();
    expect(
      screen.getByText('Reward-to-risk ratio is below the configured floor.'),
    ).toBeInTheDocument();
    expect(screen.getByText(/does not affect the ranking score/i)).toBeInTheDocument();
  });

  it('marks legacy records when breakdown evidence is unavailable', () => {
    const legacy = makeCandidate('candidate-legacy');
    legacy.latest_decision_evidence = null;

    render(<CandidateCatalog locale="en" initialPage={makePage([legacy], 0)} />);

    expect(
      screen.getByText('Breakdown evidence is unavailable for this legacy record'),
    ).toBeInTheDocument();
  });

  it('compares same-journal candidates side by side including rejection evidence', async () => {
    const user = userEvent.setup();
    const selected = makeCandidate('candidate-selected');
    const rejected = makeRejectedCandidate('candidate-rejected');
    const comparison: CandidateComparisonResult = {
      journal_id: selected.latest_journal_id,
      compared_candidates: 2,
      entries: [
        {
          comparison_position: 1,
          occurrence: makeComparisonOccurrence(selected),
        },
        {
          comparison_position: 2,
          occurrence: makeComparisonOccurrence(rejected),
        },
      ],
      interpretation: 'historical_research_only',
    };
    mocks.compareCandidates.mockResolvedValue(comparison);

    render(<CandidateCatalog locale="en" initialPage={makePage([selected, rejected], 0)} />);

    const checkboxes = screen.getAllByRole('checkbox', { name: 'Select for comparison' });
    await user.click(checkboxes[0]);
    await user.click(checkboxes[1]);
    await user.click(screen.getByRole('button', { name: 'Compare candidates' }));

    await waitFor(() => {
      expect(mocks.compareCandidates).toHaveBeenCalledWith([
        'candidate-selected',
        'candidate-rejected',
      ]);
    });
    expect(await screen.findByText('Side-by-side breakdown')).toBeInTheDocument();
    expect(screen.getByText('journal-0000000000000001')).toBeInTheDocument();
    expect(screen.getAllByText('Rejected').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('Reward to risk').length).toBeGreaterThanOrEqual(1);
    expect(
      screen.getAllByText('Reward-to-risk ratio is below the configured floor.').length,
    ).toBeGreaterThanOrEqual(1);
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
