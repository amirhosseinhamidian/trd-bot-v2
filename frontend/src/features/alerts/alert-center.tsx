'use client';

import { useRef, useState } from 'react';

import { PageFrame } from '@/components/platform/page-frame';
import { PageHeader } from '@/components/platform/page-header';
import {
  AdvancedDisclosure,
  Badge,
  Button,
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
  EmptyState,
  ErrorState,
  Pagination,
  Select,
  SelectOption,
  Spinner,
} from '@/components/ui';
import type { BadgeVariant } from '@/components/ui';
import {
  acknowledgeAlert,
  getAlerts,
  getAlertSummary,
  snoozeAlert,
} from '@/features/alerts/api/client';
import type {
  AlertInboxItem,
  AlertInboxStatus,
  AlertInboxSummary,
  AlertSeverity,
} from '@/features/alerts/api/types';
import { getAlertCenterCopy } from '@/features/alerts/alert-center-copy';
import type { Page } from '@/lib/api/core/types';
import type { PlatformLocale } from '@/platform/i18n';

const PAGE_SIZE = 12;
const DEFAULT_SNOOZE_SECONDS = 3600;

type AlertCenterProps = {
  initialPage: Page<AlertInboxItem>;
  initialSummary: AlertInboxSummary;
  locale: PlatformLocale;
};

const statusVariants: Record<AlertInboxStatus, BadgeVariant> = {
  active: 'success',
  snoozed: 'info',
  acknowledged: 'neutral',
  expired: 'danger',
};

const severityVariants: Record<AlertSeverity, BadgeVariant> = {
  info: 'info',
  warning: 'warning',
  critical: 'danger',
};

function localeCode(locale: PlatformLocale): string {
  return locale === 'fa' ? 'fa-IR' : 'en-US';
}

function formatDate(value: string, locale: PlatformLocale): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(localeCode(locale), {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date);
}

function formatPercent(value: string, locale: PlatformLocale): string {
  const number = Number(value);
  if (!Number.isFinite(number)) return value;
  return new Intl.NumberFormat(localeCode(locale), {
    style: 'percent',
    maximumFractionDigits: 2,
  }).format(number);
}

export default function AlertCenter({ initialPage, initialSummary, locale }: AlertCenterProps) {
  const copy = getAlertCenterCopy(locale);
  const [page, setPage] = useState(initialPage);
  const [summary, setSummary] = useState(initialSummary);
  const [statusFilter, setStatusFilter] = useState<AlertInboxStatus | ''>('');
  const [severityFilter, setSeverityFilter] = useState<AlertSeverity | ''>('');
  const [snoozeDurations, setSnoozeDurations] = useState<Record<string, number>>({});
  const [isLoading, setIsLoading] = useState(false);
  const [hasError, setHasError] = useState(false);
  const [pendingAction, setPendingAction] = useState<{
    alertId: string;
    kind: 'acknowledge' | 'snooze';
  } | null>(null);
  const [actionError, setActionError] = useState(false);
  const requestSequence = useRef(0);

  async function loadPage(
    offset: number,
    nextStatus: AlertInboxStatus | '' = statusFilter,
    nextSeverity: AlertSeverity | '' = severityFilter,
  ): Promise<void> {
    const requestId = ++requestSequence.current;
    setIsLoading(true);
    setHasError(false);
    try {
      const [nextPage, nextSummary] = await Promise.all([
        getAlerts({
          limit: PAGE_SIZE,
          offset,
          status: nextStatus || undefined,
          severity: nextSeverity || undefined,
        }),
        getAlertSummary(),
      ]);
      if (requestId === requestSequence.current) {
        setPage(nextPage);
        setSummary(nextSummary);
      }
    } catch {
      if (requestId === requestSequence.current) setHasError(true);
    } finally {
      if (requestId === requestSequence.current) setIsLoading(false);
    }
  }

  async function runAction(alertId: string, action: 'acknowledge' | 'snooze'): Promise<void> {
    setPendingAction({ alertId, kind: action });
    setActionError(false);
    try {
      if (action === 'acknowledge') {
        await acknowledgeAlert(alertId);
      } else {
        await snoozeAlert(alertId, snoozeDurations[alertId] ?? DEFAULT_SNOOZE_SECONDS);
      }
      await loadPage(page.offset);
    } catch {
      setActionError(true);
    } finally {
      setPendingAction(null);
    }
  }

  const summaryCards: Array<[AlertInboxStatus, number]> = [
    ['active', summary.active],
    ['snoozed', summary.snoozed],
    ['acknowledged', summary.acknowledged],
    ['expired', summary.expired],
  ];

  return (
    <PageFrame>
      <PageHeader
        eyebrow={copy.eyebrow}
        title={copy.title}
        description={copy.description}
        actions={
          <>
            <Badge variant="neutral">{copy.inAppOnly}</Badge>
            <Badge variant="info">
              {copy.total}: {new Intl.NumberFormat(localeCode(locale)).format(summary.total)}
            </Badge>
          </>
        }
      >
        <p className="rounded-2xl border border-app-warning-border bg-app-warning-soft p-4 text-sm leading-7 text-app-warning">
          {copy.disclaimer}
        </p>
      </PageHeader>

      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4" aria-label={copy.total}>
        {summaryCards.map(([status, count]) => (
          <Card key={status}>
            <CardContent className="flex items-center justify-between gap-4 p-5">
              <div>
                <p className="text-sm text-app-muted">{copy.statuses[status]}</p>
                <p className="mt-2 text-3xl font-bold text-app-foreground">
                  {new Intl.NumberFormat(localeCode(locale)).format(count)}
                </p>
              </div>
              <Badge variant={statusVariants[status]}>{copy.statuses[status]}</Badge>
            </CardContent>
          </Card>
        ))}
      </section>

      <Card>
        <CardContent className="grid gap-4 p-5 sm:grid-cols-2">
          <Select
            label={copy.statusFilter}
            value={statusFilter}
            onValueChange={(value) => {
              const next = value as AlertInboxStatus | '';
              setStatusFilter(next);
              void loadPage(0, next, severityFilter);
            }}
          >
            <SelectOption value="">{copy.allStatuses}</SelectOption>
            {Object.keys(copy.statuses).map((status) => (
              <SelectOption key={status} value={status}>
                {copy.statuses[status as AlertInboxStatus]}
              </SelectOption>
            ))}
          </Select>
          <Select
            label={copy.severityFilter}
            value={severityFilter}
            onValueChange={(value) => {
              const next = value as AlertSeverity | '';
              setSeverityFilter(next);
              void loadPage(0, statusFilter, next);
            }}
          >
            <SelectOption value="">{copy.allSeverities}</SelectOption>
            {Object.keys(copy.severities).map((severity) => (
              <SelectOption key={severity} value={severity}>
                {copy.severities[severity as AlertSeverity]}
              </SelectOption>
            ))}
          </Select>
        </CardContent>
      </Card>

      {actionError ? (
        <p
          role="alert"
          className="rounded-xl border border-app-danger-border bg-app-danger-soft p-4 text-sm text-app-danger"
        >
          {copy.actionError}
        </p>
      ) : null}

      <section className="relative min-h-64" aria-busy={isLoading} aria-label={copy.title}>
        {isLoading ? (
          <div className="absolute inset-0 z-20 flex items-center justify-center rounded-2xl bg-app-overlay backdrop-blur-sm">
            <Spinner size="lg" label={copy.loading} className="text-app-accent" />
          </div>
        ) : null}

        {hasError ? (
          <ErrorState
            title={copy.errorTitle}
            description={copy.errorDescription}
            retryLabel={copy.retry}
            onRetry={() => void loadPage(page.offset)}
          />
        ) : page.items.length === 0 ? (
          <EmptyState title={copy.emptyTitle} description={copy.emptyDescription} />
        ) : (
          <div className="grid gap-5 xl:grid-cols-2">
            {page.items.map((item) => {
              const alert = item.alert;
              const source = alert.source;
              const isActing = pendingAction?.alertId === alert.alert_id;
              const isSnoozing = isActing && pendingAction.kind === 'snooze';
              const isAcknowledging = isActing && pendingAction.kind === 'acknowledge';
              return (
                <Card key={alert.alert_id} className="overflow-hidden">
                  <CardHeader className="border-b border-app-border">
                    <div className="flex flex-wrap items-start justify-between gap-4">
                      <div className="min-w-0 flex-1">
                        <CardTitle>{alert.title}</CardTitle>
                        <CardDescription className="mt-2">{alert.message}</CardDescription>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        <Badge variant={severityVariants[alert.severity]}>
                          {copy.severities[alert.severity]}
                        </Badge>
                        <Badge variant={statusVariants[item.status]}>
                          {copy.statuses[item.status]}
                        </Badge>
                      </div>
                    </div>
                  </CardHeader>

                  <CardContent className="space-y-5 pt-6">
                    <dl className="grid gap-4 text-sm sm:grid-cols-2">
                      <div>
                        <dt className="text-xs text-app-muted">{copy.pair}</dt>
                        <dd dir="ltr" className="mt-1 text-left font-semibold">
                          {source.pair.base_asset}/{source.pair.quote_asset}
                        </dd>
                      </div>
                      <div>
                        <dt className="text-xs text-app-muted">{copy.source}</dt>
                        <dd dir="ltr" className="mt-1 text-left break-all">
                          {source.source}
                        </dd>
                      </div>
                      <div>
                        <dt className="text-xs text-app-muted">{copy.trend}</dt>
                        <dd className="mt-1 font-medium">{copy.trends[source.trend]}</dd>
                      </div>
                      <div>
                        <dt className="text-xs text-app-muted">{copy.volatilityLabel}</dt>
                        <dd className="mt-1 font-medium">{copy.volatility[source.volatility]}</dd>
                      </div>
                      <div>
                        <dt className="text-xs text-app-muted">{copy.confidence}</dt>
                        <dd dir="ltr" className="mt-1 text-left font-medium">
                          {formatPercent(source.confidence, locale)}
                        </dd>
                      </div>
                      <div>
                        <dt className="text-xs text-app-muted">{copy.createdAt}</dt>
                        <dd className="mt-1">{formatDate(alert.created_at, locale)}</dd>
                      </div>
                      <div>
                        <dt className="text-xs text-app-muted">{copy.expiresAt}</dt>
                        <dd className="mt-1">{formatDate(alert.expires_at, locale)}</dd>
                      </div>
                      {item.state.snoozed_until ? (
                        <div>
                          <dt className="text-xs text-app-muted">{copy.snoozedUntil}</dt>
                          <dd className="mt-1">{formatDate(item.state.snoozed_until, locale)}</dd>
                        </div>
                      ) : null}
                      {item.state.acknowledged_at ? (
                        <>
                          <div>
                            <dt className="text-xs text-app-muted">{copy.acknowledgedAt}</dt>
                            <dd className="mt-1">
                              {formatDate(item.state.acknowledged_at, locale)}
                            </dd>
                          </div>
                          <div>
                            <dt className="text-xs text-app-muted">{copy.acknowledgedBy}</dt>
                            <dd dir="ltr" className="mt-1 text-left break-all">
                              {item.state.acknowledged_by}
                            </dd>
                          </div>
                        </>
                      ) : null}
                    </dl>

                    <AdvancedDisclosure
                      title={copy.technicalDetails}
                      description={copy.technicalDescription}
                    >
                      <dl className="grid gap-4 text-xs sm:grid-cols-2">
                        {[
                          [copy.alertId, alert.alert_id],
                          [copy.rule, `${alert.rule.rule_id} / v${alert.rule.rule_version}`],
                          [copy.assessment, source.source_event_id],
                          [copy.checksum, alert.draft_checksum],
                        ].map(([label, value]) => (
                          <div key={label} className="min-w-0">
                            <dt className="text-app-muted">{label}</dt>
                            <dd dir="ltr" className="mt-1 text-left font-mono break-all">
                              {value}
                            </dd>
                          </div>
                        ))}
                      </dl>
                    </AdvancedDisclosure>
                  </CardContent>

                  {item.can_acknowledge || item.can_snooze ? (
                    <CardFooter className="flex-col items-stretch sm:flex-row sm:items-end">
                      {item.can_snooze ? (
                        <Select
                          label={copy.snoozeDuration}
                          value={String(snoozeDurations[alert.alert_id] ?? DEFAULT_SNOOZE_SECONDS)}
                          disabled={isActing}
                          containerClassName="sm:max-w-48"
                          onValueChange={(value) =>
                            setSnoozeDurations((current) => ({
                              ...current,
                              [alert.alert_id]: Number(value),
                            }))
                          }
                        >
                          {Object.entries(copy.durations).map(([seconds, label]) => (
                            <SelectOption key={seconds} value={seconds}>
                              {label}
                            </SelectOption>
                          ))}
                        </Select>
                      ) : null}
                      <div className="flex flex-col gap-2 sm:ms-auto sm:flex-row">
                        {item.can_snooze ? (
                          <Button
                            variant="secondary"
                            disabled={isActing}
                            isLoading={isSnoozing}
                            loadingText={copy.snoozing}
                            onClick={() => void runAction(alert.alert_id, 'snooze')}
                          >
                            {copy.snooze}
                          </Button>
                        ) : null}
                        {item.can_acknowledge ? (
                          <Button
                            disabled={isActing}
                            isLoading={isAcknowledging}
                            loadingText={copy.acknowledging}
                            onClick={() => void runAction(alert.alert_id, 'acknowledge')}
                          >
                            {copy.acknowledge}
                          </Button>
                        ) : null}
                      </div>
                    </CardFooter>
                  ) : null}
                </Card>
              );
            })}
          </div>
        )}
      </section>

      {page.total > page.limit ? (
        <Pagination
          locale={locale}
          isLoading={isLoading}
          limit={page.limit}
          offset={page.offset}
          total={page.total}
          pageLabel={copy.pagination.label}
          previousLabel={copy.pagination.previous}
          nextLabel={copy.pagination.next}
          onOffsetChange={(offset) => void loadPage(offset)}
        />
      ) : null}
    </PageFrame>
  );
}
