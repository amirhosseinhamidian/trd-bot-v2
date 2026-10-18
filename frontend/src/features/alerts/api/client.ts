import { getJson, postJson } from '@/lib/api/core/transport';
import type { Page } from '@/lib/api/core/types';

import type { AlertInboxItem, AlertInboxStatus, AlertInboxSummary, AlertSeverity } from './types';

export interface AlertFilters {
  limit?: number;
  offset?: number;
  status?: AlertInboxStatus;
  severity?: AlertSeverity;
}

const ALERT_CENTER_ACTOR = 'operator:alert-center';

export async function getAlerts(filters: AlertFilters = {}): Promise<Page<AlertInboxItem>> {
  const params = new URLSearchParams();
  params.set('limit', String(filters.limit ?? 12));
  params.set('offset', String(filters.offset ?? 0));
  if (filters.status) params.set('status', filters.status);
  if (filters.severity) params.set('severity', filters.severity);
  return getJson<Page<AlertInboxItem>>(`/api/v1/alerts?${params.toString()}`);
}

export async function getAlertSummary(): Promise<AlertInboxSummary> {
  return getJson<AlertInboxSummary>('/api/v1/alerts/summary');
}

export async function acknowledgeAlert(alertId: string): Promise<AlertInboxItem> {
  return postJson<AlertInboxItem>(`/api/v1/alerts/${encodeURIComponent(alertId)}/acknowledge`, {
    acted_by: ALERT_CENTER_ACTOR,
  });
}

export async function snoozeAlert(
  alertId: string,
  durationSeconds: number,
): Promise<AlertInboxItem> {
  return postJson<AlertInboxItem>(`/api/v1/alerts/${encodeURIComponent(alertId)}/snooze`, {
    acted_by: ALERT_CENTER_ACTOR,
    duration_seconds: durationSeconds,
  });
}
