import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { ComponentProps } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type {
  AlertExpirySummary,
  AlertInboxItem,
  AlertInboxSummary,
  AlertOutcomeRecord,
  AlertOutcomeSummary,
  AlertPublicationPolicy,
  AlertSimulationSummary,
  AlertSimulationView,
} from '@/features/alerts/api/types';
import AlertCenter from '@/features/alerts/alert-center';
import type { Page } from '@/lib/api/core/types';

const alertId = 'alert-1234567890abcdef';

const active: AlertInboxItem = {
  schema_version: 'alert-inbox-item-v1',
  status: 'active',
  evaluated_at: '2026-10-17T12:25:00Z',
  seconds_until_expiry: 1500,
  seconds_until_unsnooze: 0,
  can_acknowledge: true,
  can_snooze: true,
  state: {
    schema_version: 'alert-inbox-state-v1',
    alert_id: alertId,
    acknowledged_at: null,
    acknowledged_by: null,
    snoozed_until: null,
    snoozed_by: null,
    updated_at: '2026-10-17T12:20:00Z',
  },
  alert: {
    schema_version: 'alert-draft-v1',
    alert_id: alertId,
    deduplication_key: `alert-dedupe-${'1'.repeat(64)}`,
    delivery_channel: 'in_app',
    severity: 'warning',
    title: 'High-volatility uptrend',
    message: 'BTC/USDT is trending up with high volatility.',
    created_at: '2026-10-17T12:20:00Z',
    expires_at: '2026-10-17T12:50:00Z',
    draft_checksum: '2'.repeat(64),
    rule: {
      schema_version: 'alert-rule-reference-v1',
      rule_id: 'alert-rule-1234567890abcdef',
      rule_version: 1,
      state: 'enabled',
      severity: 'warning',
      expires_after_seconds: 1800,
      definition_checksum: '3'.repeat(64),
    },
    source: {
      schema_version: 'market-context-alert-source-v1',
      reference_id: 'alert-source-1234567890abcdef',
      source_kind: 'market_context',
      source_event_id: 'market-regime-1234567890abcdef',
      source_event_schema_version: 'market-regime-assessment-v1',
      source_event_checksum: '4'.repeat(64),
      source: 'kraken-public',
      pair: { base_asset: 'BTC', quote_asset: 'USDT', market_type: 'spot' },
      event_time: '2026-10-17T12:00:00Z',
      assessed_at: '2026-10-17T12:01:00Z',
      expires_at: '2026-10-17T13:01:00Z',
      evaluated_at: '2026-10-17T12:20:00Z',
      expected_as_of: '2026-10-17T12:00:00Z',
      assessment_status: 'ready',
      trend: 'trending_up',
      volatility: 'high',
      confidence: '0.82',
      consumable: true,
      unavailable_reasons: [],
      reference_checksum: '5'.repeat(64),
    },
  },
};

const initialPage: Page<AlertInboxItem> = {
  items: [active],
  total: 1,
  limit: 12,
  offset: 0,
  count: 1,
  has_next: false,
  has_previous: false,
};

const summary: AlertInboxSummary = {
  schema_version: 'alert-inbox-summary-v1',
  evaluated_at: '2026-10-17T12:25:00Z',
  total: 1,
  active: 1,
  snoozed: 0,
  acknowledged: 0,
  expired: 0,
};

const publicationPolicy: AlertPublicationPolicy = {
  schema_version: 'alert-publication-policy-v1',
  policy_id: 'alert-publication-policy-default',
  policy_version: 1,
  quiet_hours_enabled: true,
  quiet_hours_start_minute: 1320,
  quiet_hours_end_minute: 420,
  timezone_name: 'Asia/Tehran',
  critical_bypass_quiet_hours: true,
  updated_by: 'operator:alert-center',
  updated_at: '2026-10-17T12:00:00Z',
  policy_checksum: '6'.repeat(64),
};

const expirySummary: AlertExpirySummary = {
  schema_version: 'alert-expiry-summary-v1',
  evaluated_at: '2026-10-17T12:25:00Z',
  expired_total: 2,
  materialized_total: 1,
  pending_total: 1,
};

const simulationSummary: AlertSimulationSummary = {
  schema_version: 'alert-simulation-summary-v1',
  evaluated_at: '2026-10-17T12:25:00Z',
  total: 0,
  paper: 0,
  shadow: 0,
  observing: 0,
  awaiting_outcome: 0,
};

const outcomeSummary: AlertOutcomeSummary = {
  schema_version: 'alert-outcome-summary-v1',
  evaluated_at: '2026-10-17T12:25:00Z',
  completed: 0,
  awaiting_outcome: 0,
  confirmed: 0,
  neutral: 0,
  false_positive: 0,
  drifted: 0,
  paper: 0,
  shadow: 0,
  false_positive_rate: '0',
  drift_rate: '0',
  average_directional_return: '0',
};

const confirmedOutcome: AlertOutcomeRecord = {
  schema_version: 'alert-outcome-v1',
  outcome_id: 'alert-outcome-1234567890abcdef',
  simulation_id: 'alert-simulation-1234567890abcdef',
  simulation_checksum: '7'.repeat(64),
  alert_id: alertId,
  alert_checksum: '2'.repeat(64),
  mode: 'paper',
  expected_trend: 'trending_up',
  observed_trend: 'trending_up',
  reference_price: '100',
  end_price: '101',
  high_price: '102',
  low_price: '99',
  raw_return: '0.01',
  directional_return: '0.01',
  max_favorable_excursion: '0.02',
  max_adverse_excursion: '-0.01',
  classification: 'confirmed',
  false_positive: false,
  drifted: false,
  policy_version: 'alert-outcome-policy-v1',
  policy_checksum: '8'.repeat(64),
  classification_threshold: '0.005',
  observed_at: '2026-10-17T13:26:00Z',
  recorded_at: '2026-10-17T13:26:00Z',
  recorded_by: 'operator:alert-center',
  offline_only: true,
  external_order_submission_allowed: false,
  record_checksum: '9'.repeat(64),
};

const paperSimulation: AlertSimulationView = {
  schema_version: 'alert-simulation-view-v1',
  status: 'observing',
  evaluated_at: '2026-10-17T12:25:00Z',
  seconds_remaining: 3600,
  simulation: {
    schema_version: 'alert-simulation-v1',
    simulation_id: 'alert-simulation-1234567890abcdef',
    alert_id: alertId,
    alert_checksum: '2'.repeat(64),
    source_reference_id: 'alert-source-1234567890abcdef',
    source_reference_checksum: '5'.repeat(64),
    rule_id: 'alert-rule-1234567890abcdef',
    rule_version: 1,
    rule_definition_checksum: '3'.repeat(64),
    mode: 'paper',
    expected_trend: 'trending_up',
    horizon_seconds: 3600,
    started_at: '2026-10-17T12:25:00Z',
    ends_at: '2026-10-17T13:25:00Z',
    started_by: 'operator:alert-center',
    offline_only: true,
    external_order_submission_allowed: false,
    record_checksum: '7'.repeat(64),
  },
};

function renderAlertCenter(
  overrides: Partial<ComponentProps<typeof AlertCenter>> = {},
): ReturnType<typeof render> {
  return render(
    <AlertCenter
      initialPage={initialPage}
      initialSummary={summary}
      initialPolicy={publicationPolicy}
      initialExpirySummary={expirySummary}
      initialSimulations={[]}
      initialSimulationSummary={simulationSummary}
      initialOutcomes={[]}
      initialOutcomeSummary={outcomeSummary}
      locale="en"
      {...overrides}
    />,
  );
}

afterEach(() => vi.unstubAllGlobals());

describe('AlertCenter', () => {
  it('shows the decision summary, responsive actions, and disclosed lineage', () => {
    renderAlertCenter();

    expect(screen.getByRole('heading', { name: 'Alert Center' })).toBeInTheDocument();
    expect(screen.getByText('High-volatility uptrend')).toBeInTheDocument();
    expect(screen.getByText('BTC/USDT')).toBeInTheDocument();
    expect(screen.getByText('Trending up')).toBeInTheDocument();
    expect(screen.getByText('82%')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Acknowledge' })).toHaveClass('min-h-11');
    expect(screen.getByRole('button', { name: 'Snooze' })).toHaveClass('min-h-11');
    expect(screen.getByLabelText('Snooze duration')).toBeInTheDocument();
    expect(screen.getByLabelText('Enable quiet hours')).toBeChecked();
    expect(screen.getByLabelText('Time zone')).toHaveValue('Asia/Tehran');
    expect(screen.getByRole('button', { name: 'Record pending expiries' })).toBeEnabled();
    expect(screen.getByRole('button', { name: 'Start Paper' })).toHaveClass('min-h-11');
    expect(screen.getByRole('button', { name: 'Start Shadow' })).toHaveClass('min-h-11');
    expect(screen.getByText('No live order')).toBeInTheDocument();

    const disclosure = screen.getByText('Lineage and technical details').closest('details');
    expect(disclosure).not.toBeNull();
    expect(within(disclosure!).getByText(alertId)).toBeInTheDocument();
    expect(disclosure).not.toHaveAttribute('open');
  });

  it('acknowledges an alert and refreshes page and summary state', async () => {
    const user = userEvent.setup();
    const acknowledged: AlertInboxItem = {
      ...active,
      status: 'acknowledged',
      can_acknowledge: false,
      can_snooze: false,
      state: {
        ...active.state,
        acknowledged_at: '2026-10-17T12:26:00Z',
        acknowledged_by: 'operator:alert-center',
        updated_at: '2026-10-17T12:26:00Z',
      },
    };
    const refreshedPage = { ...initialPage, items: [acknowledged] };
    const refreshedSummary = { ...summary, active: 0, acknowledged: 1 };
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (init?.method === 'POST') {
        return new Response(JSON.stringify(acknowledged), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        });
      }
      const payload = url.endsWith('/summary') ? refreshedSummary : refreshedPage;
      return new Response(JSON.stringify(payload), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    });
    vi.stubGlobal('fetch', fetchMock);
    renderAlertCenter();

    await user.click(screen.getByRole('button', { name: 'Acknowledge' }));

    await waitFor(() =>
      expect(screen.queryByRole('button', { name: 'Acknowledge' })).not.toBeInTheDocument(),
    );
    expect(screen.getAllByText('Acknowledged').length).toBeGreaterThan(0);
    expect(screen.getByText('operator:alert-center')).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining(`/api/v1/alerts/${alertId}/acknowledge`),
      expect.objectContaining({ method: 'POST' }),
    );
  });

  it('reloads the catalog when an accessible status filter changes', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const payload = String(input).endsWith('/summary') ? summary : initialPage;
      return new Response(JSON.stringify(payload), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    });
    vi.stubGlobal('fetch', fetchMock);
    renderAlertCenter();

    fireEvent.change(screen.getByLabelText('Status filter'), { target: { value: 'snoozed' } });

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('status=snoozed'),
        expect.objectContaining({ method: 'GET' }),
      ),
    );
  });

  it('renders a clear empty state', () => {
    renderAlertCenter({
      initialPage: { ...initialPage, items: [], total: 0, count: 0 },
      initialSummary: { ...summary, total: 0, active: 0 },
    });

    expect(screen.getByText('No alerts match these filters')).toBeInTheDocument();
  });

  it('saves a versioned quiet-hours policy', async () => {
    const user = userEvent.setup();
    const updated = { ...publicationPolicy, policy_version: 2, timezone_name: 'UTC' };
    const fetchMock = vi.fn(
      async () =>
        new Response(JSON.stringify(updated), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
    );
    vi.stubGlobal('fetch', fetchMock);
    renderAlertCenter();

    await user.clear(screen.getByLabelText('Time zone'));
    await user.type(screen.getByLabelText('Time zone'), 'UTC');
    await user.click(screen.getByRole('button', { name: 'Save policy' }));

    await screen.findByText('Publication policy saved successfully.');
    expect(screen.getByText(/Policy version:/)).toHaveTextContent('2');
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/alerts/publication-policy'),
      expect.objectContaining({
        method: 'POST',
        body: expect.stringContaining('"timezone_name":"UTC"'),
      }),
    );
  });

  it('materializes pending expiry evidence and refreshes its summary', async () => {
    const user = userEvent.setup();
    const swept = {
      schema_version: 'alert-expiry-sweep-v1',
      evaluated_at: expirySummary.evaluated_at,
      recorded_by: 'operator:alert-center',
      recorded_count: 1,
      expiry_ids: ['alert-expiry-1234567890abcdef'],
      remaining_pending: 0,
    };
    const refreshed = { ...expirySummary, materialized_total: 2, pending_total: 0 };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify(swept), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify(refreshed), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      );
    vi.stubGlobal('fetch', fetchMock);
    renderAlertCenter();

    await user.click(screen.getByRole('button', { name: 'Record pending expiries' }));

    await screen.findByText('Expiry lifecycle updated.');
    expect(screen.getByRole('button', { name: 'Record pending expiries' })).toBeDisabled();
  });

  it('starts an idempotent offline paper evaluation from an alert', async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          schema_version: 'alert-simulation-start-result-v1',
          created: true,
          view: paperSimulation,
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      ),
    );
    vi.stubGlobal('fetch', fetchMock);
    renderAlertCenter();

    await user.click(screen.getByRole('button', { name: 'Start Paper' }));

    await screen.findByText('Paper · Observing');
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining(`/api/v1/alerts/${alertId}/simulations`),
      expect.objectContaining({
        method: 'POST',
        body: expect.stringContaining('"mode":"paper"'),
      }),
    );
  });

  it('records an immutable outcome for a completed simulation and refreshes analytics', async () => {
    const user = userEvent.setup();
    const awaitingSimulation: AlertSimulationView = {
      ...paperSimulation,
      status: 'awaiting_outcome',
      seconds_remaining: 0,
      simulation: {
        ...paperSimulation.simulation,
        started_at: '2026-10-17T11:00:00Z',
        ends_at: '2026-10-17T12:00:00Z',
      },
    };
    const refreshedSummary: AlertOutcomeSummary = {
      ...outcomeSummary,
      completed: 1,
      confirmed: 1,
      paper: 1,
      average_directional_return: '0.01',
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            schema_version: 'alert-outcome-record-result-v1',
            created: true,
            outcome: confirmedOutcome,
          }),
          { status: 200, headers: { 'Content-Type': 'application/json' } },
        ),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify(refreshedSummary), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      );
    vi.stubGlobal('fetch', fetchMock);
    renderAlertCenter({
      initialSimulations: [awaitingSimulation],
      initialSimulationSummary: {
        ...simulationSummary,
        total: 1,
        paper: 1,
        awaiting_outcome: 1,
      },
      initialOutcomeSummary: { ...outcomeSummary, awaiting_outcome: 1 },
    });

    await user.type(screen.getByLabelText('Start price'), '100');
    await user.type(screen.getByLabelText('End price'), '101');
    await user.type(screen.getByLabelText('High price'), '102');
    await user.type(screen.getByLabelText('Low price'), '99');
    fireEvent.change(screen.getByLabelText('Observed trend'), {
      target: { value: 'trending_up' },
    });
    await user.click(screen.getByRole('button', { name: 'Record offline outcome' }));

    await screen.findByText('Paper · Confirmed');
    expect(screen.getByText('Directional return: 1%')).toBeInTheDocument();
    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      expect.stringContaining(
        '/api/v1/alerts/simulations/alert-simulation-1234567890abcdef/outcome',
      ),
      expect.objectContaining({
        method: 'POST',
        body: expect.stringContaining('"reference_price":"100"'),
      }),
    );
  });
});
