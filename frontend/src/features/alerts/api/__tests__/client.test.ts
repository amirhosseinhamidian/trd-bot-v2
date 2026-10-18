import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  acknowledgeAlert,
  getAlertExpirySummary,
  getAlertPublicationPolicy,
  getAlerts,
  getAlertSummary,
  snoozeAlert,
  sweepExpiredAlerts,
  updateAlertPublicationPolicy,
} from '@/features/alerts/api/client';
import type { AlertInboxItem, AlertInboxSummary } from '@/features/alerts/api/types';
import { API_BASE_URL } from '@/lib/api/core/transport';
import type { Page } from '@/lib/api/core/types';

const item = { alert: { alert_id: 'alert-1234567890abcdef' } } as AlertInboxItem;
const page = { items: [item], total: 1, limit: 12, offset: 0, count: 1 } as Page<AlertInboxItem>;
const summary = { total: 1, active: 1 } as AlertInboxSummary;

afterEach(() => vi.unstubAllGlobals());

describe('Alert Center client', () => {
  it('loads filtered alerts and the summary as uncached reads', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify(page), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify(summary), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      );
    vi.stubGlobal('fetch', fetchMock);

    await expect(
      getAlerts({ limit: 12, offset: 0, status: 'active', severity: 'warning' }),
    ).resolves.toEqual(page);
    await expect(getAlertSummary()).resolves.toEqual(summary);

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      `${API_BASE_URL}/api/v1/alerts?limit=12&offset=0&status=active&severity=warning`,
      expect.objectContaining({ method: 'GET', cache: 'no-store' }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      `${API_BASE_URL}/api/v1/alerts/summary`,
      expect.objectContaining({ method: 'GET', cache: 'no-store' }),
    );
  });

  it('posts sanitized acknowledge and snooze commands', async () => {
    const fetchMock = vi.fn().mockImplementation(() =>
      Promise.resolve(
        new Response(JSON.stringify(item), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      ),
    );
    vi.stubGlobal('fetch', fetchMock);

    await acknowledgeAlert('alert/id');
    await snoozeAlert('alert/id', 3600);

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      `${API_BASE_URL}/api/v1/alerts/alert%2Fid/acknowledge`,
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ acted_by: 'operator:alert-center' }),
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      `${API_BASE_URL}/api/v1/alerts/alert%2Fid/snooze`,
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ acted_by: 'operator:alert-center', duration_seconds: 3600 }),
      }),
    );
  });

  it('reads and mutates publication policy and expiry lifecycle endpoints', async () => {
    const payload = { policy_version: 2 };
    const fetchMock = vi.fn().mockImplementation(() =>
      Promise.resolve(
        new Response(JSON.stringify(payload), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      ),
    );
    vi.stubGlobal('fetch', fetchMock);

    await getAlertPublicationPolicy();
    await updateAlertPublicationPolicy({
      quiet_hours_enabled: true,
      quiet_hours_start_minute: 1320,
      quiet_hours_end_minute: 420,
      timezone_name: 'Asia/Tehran',
      critical_bypass_quiet_hours: true,
    });
    await getAlertExpirySummary();
    await sweepExpiredAlerts(25);

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      `${API_BASE_URL}/api/v1/alerts/publication-policy`,
      expect.objectContaining({ method: 'GET', cache: 'no-store' }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      `${API_BASE_URL}/api/v1/alerts/publication-policy`,
      expect.objectContaining({
        method: 'POST',
        body: expect.stringContaining('"timezone_name":"Asia/Tehran"'),
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      `${API_BASE_URL}/api/v1/alerts/expiry`,
      expect.objectContaining({ method: 'GET', cache: 'no-store' }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      4,
      `${API_BASE_URL}/api/v1/alerts/expiry/sweep`,
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ acted_by: 'operator:alert-center', limit: 25 }),
      }),
    );
  });
});
