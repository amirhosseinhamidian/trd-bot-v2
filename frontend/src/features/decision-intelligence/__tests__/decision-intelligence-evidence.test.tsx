import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import type { DecisionEvaluationDetail } from '@/features/decision-intelligence/api/types';
import DecisionIntelligenceEvidence from '@/features/decision-intelligence/decision-intelligence-evidence';

const evaluationId = 'decision-evaluation-1234567890abcdef';
const outcomes = [
  'strategy_evaluation',
  'candidate_ranking',
  'risk_gate',
  'portfolio_simulation',
].map((stage, index) => ({
  outcome_id: `decision-outcome-${String(index).padStart(16, '0')}`,
  evaluation_id: evaluationId,
  stage,
  disposition: 'accepted',
  reason_codes: [],
  evaluated_at: '2026-10-21T10:00:00Z',
}));

const evidence = {
  summary: {
    evaluation_id: evaluationId,
    mode: 'shadow',
    requested_at: '2026-10-21T10:00:00Z',
    dataset_id: 'dataset-1',
    pair: { base_asset: 'BTC', quote_asset: 'USDT', market_type: 'spot' },
    timeframe: '1h',
    strategy_name: 'ema-crossover',
    strategy_version: '1.0.0',
    market_context_assessment_id: 'market-regime-1234567890abcdef',
    latest_stage: 'portfolio_simulation',
    disposition: 'accepted',
    reason_codes: [],
    completed_stage_count: 4,
    signal_count: 1,
    top_candidate_id: 'decision-candidate-1234567890abcdef',
    risk_decision: 'approved',
    portfolio_recommendation: 'accept',
    portfolio_id: 'portfolio-1234567890abcdef',
    offline_only: true,
    external_order_submission_allowed: false,
  },
  intent: {
    evaluation_id: evaluationId,
    mode: 'shadow',
    requested_at: '2026-10-21T10:00:00Z',
    dataset: { dataset_id: 'dataset-1', reference_checksum: 'a'.repeat(64) },
    strategy: {
      strategy_name: 'ema-crossover',
      strategy_version: '1.0.0',
      reference_checksum: 'b'.repeat(64),
    },
    market_context: {
      assessment_id: 'market-regime-1234567890abcdef',
      trend: 'bullish',
      volatility: 'normal',
      confidence: '0.8',
      reference_checksum: 'c'.repeat(64),
    },
    policy: { policy_id: 'policy-1', policy_version: 1, definition_checksum: 'd'.repeat(64) },
    intent_checksum: 'e'.repeat(64),
    offline_only: true,
    external_order_submission_allowed: false,
  },
  outcomes,
  strategy_evaluation: null,
  candidate_ranking: null,
  risk_gate: null,
  portfolio_intelligence: {
    outcome: outcomes[3],
    recommendation: 'accept',
    analysis: {
      snapshot: {
        portfolio_id: 'portfolio-1234567890abcdef',
        equity: '10000',
        open_positions: [],
      },
      exposure: {
        current_exposure_fraction: '0.1',
        projected_exposure_fraction: '0.2',
        projected_asset_concentration_fraction: '0.15',
      },
      correlation: {
        status: 'not_applicable',
        maximum_absolute_correlation: null,
        evidence: 'No existing position.',
      },
      scenarios: [{ shock_fraction: '-0.1', projected_equity: '9900', loss_fraction: '0.01' }],
      checks: [
        {
          name: 'projected_exposure',
          passed: true,
          actual_value: '0.2',
          limit_value: '0.25',
          explanation: 'Inside the cap.',
        },
      ],
      exit_recommendations: [],
    },
  },
} as DecisionEvaluationDetail;

describe('DecisionIntelligenceEvidence', () => {
  it('renders the explicit offline boundary and all stage outcomes', () => {
    render(<DecisionIntelligenceEvidence evidence={evidence} focus="strategy" locale="en" />);

    expect(screen.getByRole('heading', { name: 'Decision Intelligence' })).toBeInTheDocument();
    expect(screen.getByText('Offline only')).toBeInTheDocument();
    expect(screen.getByText('No order submission')).toBeInTheDocument();
    expect(screen.getAllByText('Accepted')).toHaveLength(4);
    expect(screen.getByText('80%')).toBeInTheDocument();
  });

  it('renders limited portfolio evidence without implying execution', () => {
    render(<DecisionIntelligenceEvidence evidence={evidence} focus="portfolio" locale="en" />);

    expect(screen.getByText('20%')).toBeInTheDocument();
    expect(screen.getByText('15%')).toBeInTheDocument();
    expect(screen.getByText('projected_exposure')).toBeInTheDocument();
    expect(screen.getByText('No risk- or regime-based exit is recommended.')).toBeInTheDocument();
  });

  it('renders a neutral empty state when no lineage is linked', () => {
    render(<DecisionIntelligenceEvidence evidence={null} focus="signal" locale="en" />);

    expect(
      screen.getByText('No Decision Intelligence evidence is linked to this resource yet.'),
    ).toBeInTheDocument();
  });
});
