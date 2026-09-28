import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import PositionDetail from '@/components/dashboard/position-detail';
import type { PositionDetailReport } from '@/lib/api/types';

const report: PositionDetailReport = {
  position_detail_version: 'position-detail-v1',
  as_of: '2026-08-26T15:00:00Z',
  dataset_id: 'dataset-123',
  position: {
    position_id: 'position-123',
    portfolio_id: 'portfolio-123',
    pair: { base_asset: 'BTC', quote_asset: 'USDT', market_type: 'spot' },
    side: 'long',
    status: 'closed',
    quantity: '2',
    entry_price: '100',
    opened_at: '2026-08-26T13:00:00Z',
    current_price: '110',
    current_at: '2026-08-26T15:00:00Z',
    reserved_notional: '200',
    entry_fee: '0.20',
    unrealized_pnl: '0',
    exit_price: '110',
    closed_at: '2026-08-26T15:00:00Z',
    exit_fee: '0.22',
    gross_realized_pnl: '20',
    realized_pnl: '19.58',
  },
  lineage_status: 'complete',
  journal_id: 'journal-123',
  candidate: {
    candidate_id: 'candidate-123',
    status: 'selected',
    action: 'long',
    dataset_id: 'dataset-123',
    experiment_id: 'experiment-123',
    signal_id: 'signal-123',
    pair: { base_asset: 'BTC', quote_asset: 'USDT', market_type: 'spot' },
    timeframe: '1h',
    strategy_name: 'rsi-threshold',
    strategy_version: '1.0.0',
    confidence: '0.82',
    signal_score: '0.74',
    created_at: '2026-08-26T12:00:00Z',
    valid_until: '2026-08-26T16:00:00Z',
  },
  decision_evidence: {
    evidence_version: 'candidate-decision-evidence-v1',
    candidate_id: 'candidate-123',
    ranking: {
      score_version: 'candidate-ranking-score-v1',
      candidate_id: 'candidate-123',
      rank: 1,
      total_score: '0.818000',
      formula: 'sum(weighted_components)',
      components: [],
      tie_break: {
        tie_break_version: 'candidate-ranking-tie-break-v1',
        rule: 'total_score_desc_then_candidate_id_asc',
        applied: false,
        tied_candidate_ids: [],
        position_within_tie: null,
      },
    },
    risk_compatibility: {
      compatibility_version: 'candidate-risk-compatibility-v1',
      status: 'evaluated',
      affects_ranking_score: false,
      decision: 'approved',
      passed_checks: 1,
      failed_checks: 0,
      compatibility_fraction: '1',
      failed_check_names: [],
      checks: [
        {
          name: 'candidate_selectable',
          passed: true,
          actual_value: 'true',
          limit_value: 'true',
          reason: 'Candidate is selectable.',
        },
      ],
      not_evaluated_reason: null,
    },
  },
  nodes: [
    ['dataset', 'dataset-123', null],
    ['experiment', 'experiment-123', null],
    ['signal', 'signal-123', null],
    ['candidate', 'candidate-123', null],
    ['risk', null, 'approved'],
    ['position', 'position-123', 'closed'],
    ['exit', 'position-123', 'target'],
  ].map(([kind, resourceId, outcome]) => ({
    kind: kind as PositionDetailReport['nodes'][number]['kind'],
    status: 'available',
    resource_id: resourceId,
    portfolio_id: kind === 'position' || kind === 'exit' ? 'portfolio-123' : null,
    outcome,
    reason: null,
  })),
  events: [
    {
      event_id: 'event-open',
      portfolio_id: 'portfolio-123',
      sequence_number: 2,
      event_type: 'position_opened',
      occurred_at: '2026-08-26T13:00:00Z',
      equity: '999.80',
      position_id: 'position-123',
      price: '100',
      quantity: '2',
      realized_pnl: null,
    },
    {
      event_id: 'event-close',
      portfolio_id: 'portfolio-123',
      sequence_number: 3,
      event_type: 'position_closed',
      occurred_at: '2026-08-26T15:00:00Z',
      equity: '1019.58',
      position_id: 'position-123',
      price: '110',
      quantity: '2',
      realized_pnl: '19.58',
    },
  ],
  interpretation: 'historical_research_only',
};

describe('PositionDetail', () => {
  it('renders immutable accounting, complete lineage, risk evidence, and events', () => {
    render(<PositionDetail locale="en" report={report} />);

    expect(screen.getByText('Simulated position detail')).toBeInTheDocument();
    expect(screen.getByText('Complete lineage')).toBeInTheDocument();
    expect(screen.getAllByText('19.58')).toHaveLength(2);
    expect(screen.getByText('Target reached')).toBeInTheDocument();
    expect(screen.getByText('candidate-ranking-score-v1')).toBeInTheDocument();
    expect(screen.getByText('Candidate is selectable.')).toBeInTheDocument();
    expect(screen.getByText('Position opened')).toBeInTheDocument();
    expect(screen.getByText('Position closed')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Back to portfolio/ })).toHaveAttribute(
      'href',
      '/en/portfolios/portfolio-123',
    );
    expect(screen.queryByRole('button', { name: /buy|sell|open|close/i })).toBeNull();
  });

  it('does not invent missing lineage evidence', () => {
    const unavailable: PositionDetailReport = {
      ...report,
      lineage_status: 'unavailable',
      journal_id: null,
      candidate: null,
      decision_evidence: null,
      nodes: report.nodes.map((node) =>
        ['dataset', 'position'].includes(node.kind)
          ? node
          : {
              ...node,
              status: 'unavailable',
              resource_id: null,
              outcome: null,
              reason: 'lineage_evidence_unavailable',
            },
      ),
    };

    render(<PositionDetail locale="en" report={unavailable} />);

    expect(screen.getByText('Lineage evidence unavailable')).toBeInTheDocument();
    expect(
      screen.getByText('Versioned ranking evidence is unavailable for this record.'),
    ).toBeInTheDocument();
    expect(screen.queryByText('Approved')).toBeNull();
  });
});
