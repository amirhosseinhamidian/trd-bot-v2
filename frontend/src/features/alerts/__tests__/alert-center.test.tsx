import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { AlertInboxItem, AlertInboxSummary } from '@/features/alerts/api/types';
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

afterEach(() => vi.unstubAllGlobals());

describe('AlertCenter', () => {
  it('shows the decision summary, responsive actions, and disclosed lineage', () => {
    render(<AlertCenter initialPage={initialPage} initialSummary={summary} locale="en" />);

    expect(screen.getByRole('heading', { name: 'Alert Center' })).toBeInTheDocument();
    expect(screen.getByText('High-volatility uptrend')).toBeInTheDocument();
    expect(screen.getByText('BTC/USDT')).toBeInTheDocument();
    expect(screen.getByText('Trending up')).toBeInTheDocument();
    expect(screen.getByText('82%')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Acknowledge' })).toHaveClass('min-h-11');
    expect(screen.getByRole('button', { name: 'Snooze' })).toHaveClass('min-h-11');
    expect(screen.getByLabelText('Snooze duration')).toBeInTheDocument();

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
    render(<AlertCenter initialPage={initialPage} initialSummary={summary} locale="en" />);

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
    render(<AlertCenter initialPage={initialPage} initialSummary={summary} locale="en" />);

    fireEvent.change(screen.getByLabelText('Status filter'), { target: { value: 'snoozed' } });

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('status=snoozed'),
        expect.objectContaining({ method: 'GET' }),
      ),
    );
  });

  it('renders a clear empty state', () => {
    render(
      <AlertCenter
        initialPage={{ ...initialPage, items: [], total: 0, count: 0 }}
        initialSummary={{ ...summary, total: 0, active: 0 }}
        locale="en"
      />,
    );

    expect(screen.getByText('No alerts match these filters')).toBeInTheDocument();
  });
});
