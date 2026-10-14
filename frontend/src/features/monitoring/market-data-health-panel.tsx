import { Badge, Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui';
import type { BadgeVariant } from '@/components/ui';
import type { BackgroundJobStatus } from '@/features/jobs/api/types';
import type {
  MarketDataFreshnessStatus,
  MarketDataMonitoringOverallStatus,
  MarketDataMonitoringSummary,
  MarketDataStreamHealthStatus,
} from '@/features/monitoring/api/types';
import { getMarketDataHealthCopy } from '@/features/monitoring/market-data-health-copy';
import type { PlatformLocale } from '@/platform/i18n';

type MarketDataHealthPanelProps = {
  locale: PlatformLocale;
  summary: MarketDataMonitoringSummary;
};

const overallVariants: Record<MarketDataMonitoringOverallStatus, BadgeVariant> = {
  healthy: 'success',
  warning: 'warning',
  critical: 'danger',
  no_data: 'neutral',
};

const healthVariants: Record<MarketDataStreamHealthStatus, BadgeVariant> = {
  healthy: 'success',
  degraded: 'danger',
  paused: 'neutral',
  no_data: 'warning',
};

const freshnessVariants: Record<MarketDataFreshnessStatus, BadgeVariant> = {
  fresh: 'success',
  stale: 'danger',
  no_data: 'neutral',
};

const jobVariants: Record<BackgroundJobStatus, BadgeVariant> = {
  queued: 'info',
  running: 'warning',
  succeeded: 'success',
  failed: 'danger',
  cancelled: 'neutral',
};

function formatCount(value: number, locale: PlatformLocale): string {
  return new Intl.NumberFormat(locale === 'fa' ? 'fa-IR' : 'en-US').format(value);
}

function formatDate(value: string | null, locale: PlatformLocale, fallback: string): string {
  if (!value) {
    return fallback;
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat(locale === 'fa' ? 'fa-IR' : 'en-US', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date);
}

function formatSeconds(value: number | null, locale: PlatformLocale, suffix: string): string {
  if (value === null) {
    return '—';
  }
  return `${formatCount(value, locale)} ${suffix}`;
}

export function MarketDataHealthPanel({ locale, summary }: MarketDataHealthPanelProps) {
  const copy = getMarketDataHealthCopy(locale);

  return (
    <Card>
      <CardHeader className="gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <CardTitle>{copy.title}</CardTitle>
          <CardDescription>{copy.description}</CardDescription>
        </div>
        <Badge className="shrink-0" variant={overallVariants[summary.overall_status]}>
          {copy.overallStatus}: {copy.overallStatuses[summary.overall_status]}
        </Badge>
      </CardHeader>

      <CardContent className="space-y-6">
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <article className="rounded-2xl border border-app-border bg-app-surface-muted p-5">
            <p className="text-sm font-medium text-app-foreground">{copy.streams}</p>
            <p className="mt-3 text-2xl font-bold text-app-foreground">
              {formatCount(summary.stream_count, locale)}
            </p>
            <p className="mt-2 text-xs leading-6 text-app-muted">
              {copy.healthyStreams}: {formatCount(summary.healthy_count, locale)} ·{' '}
              {copy.degradedStreams}: {formatCount(summary.degraded_count, locale)}
            </p>
          </article>

          <article className="rounded-2xl border border-app-border bg-app-surface-muted p-5">
            <p className="text-sm font-medium text-app-foreground">{copy.staleStreams}</p>
            <p className="mt-3 text-2xl font-bold text-app-foreground">
              {formatCount(summary.stale_count, locale)}
            </p>
            <p className="mt-2 text-xs leading-6 text-app-muted">
              {copy.noData}: {formatCount(summary.no_data_count, locale)}
            </p>
          </article>

          <article className="rounded-2xl border border-app-border bg-app-surface-muted p-5">
            <p className="text-sm font-medium text-app-foreground">{copy.pollingBacklog}</p>
            <p className="mt-3 text-2xl font-bold text-app-foreground">
              {formatCount(summary.backlog.poll_jobs, locale)}
            </p>
            <p className="mt-2 text-xs leading-6 text-app-muted">
              {copy.overdue}: {formatCount(summary.backlog.overdue_watchlists, locale)} ·{' '}
              {copy.finalization}: {formatCount(summary.backlog.finalization_windows, locale)}
            </p>
          </article>

          <article className="rounded-2xl border border-app-border bg-app-surface-muted p-5">
            <p className="text-sm font-medium text-app-foreground">{copy.replayBacklog}</p>
            <p className="mt-3 text-2xl font-bold text-app-foreground">
              {formatCount(summary.backlog.replay_jobs, locale)}
            </p>
            <p className="mt-2 text-xs leading-6 text-app-muted">
              {copy.pending}: {formatCount(summary.backlog.pending_replays, locale)} · {copy.failed}
              : {formatCount(summary.backlog.failed_replays, locale)}
            </p>
          </article>
        </div>

        <section aria-labelledby="market-data-stream-health">
          <h3 id="market-data-stream-health" className="font-semibold text-app-foreground">
            {copy.streamHealth}
          </h3>

          {summary.streams.length === 0 ? (
            <p className="mt-4 rounded-2xl border border-app-border p-5 text-sm text-app-muted">
              {copy.noStreams}
            </p>
          ) : (
            <div className="mt-4 grid gap-4 xl:grid-cols-2">
              {summary.streams.map((stream) => (
                <article
                  key={stream.watchlist_id}
                  className="min-w-0 rounded-2xl border border-app-border bg-app-surface-muted p-5"
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0">
                      <h4 dir="ltr" className="text-left font-semibold text-app-foreground">
                        {stream.pair.base_asset}/{stream.pair.quote_asset} · {stream.timeframe}
                      </h4>
                      <p
                        dir="ltr"
                        className="mt-1 text-left font-mono text-xs break-all text-app-muted"
                      >
                        {stream.watchlist_id}
                      </p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <Badge variant={healthVariants[stream.health_status]}>
                        {copy.healthStatuses[stream.health_status]}
                      </Badge>
                      <Badge variant={freshnessVariants[stream.freshness_status]}>
                        {copy.freshnessStatuses[stream.freshness_status]}
                      </Badge>
                    </div>
                  </div>

                  <dl className="mt-5 grid gap-4 text-sm sm:grid-cols-2">
                    <div className="min-w-0">
                      <dt className="text-app-muted">{copy.selectedProvider}</dt>
                      <dd dir="ltr" className="mt-1 text-left break-all text-app-foreground">
                        {stream.selected_provider_id ?? copy.unavailable}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-app-muted">{copy.latestFinalized}</dt>
                      <dd className="mt-1 text-app-foreground">
                        {formatDate(stream.latest_finalized_window_end, locale, copy.noData)}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-app-muted">{copy.lag}</dt>
                      <dd dir="ltr" className="mt-1 text-left text-app-foreground tabular-nums">
                        {formatSeconds(stream.lag_seconds, locale, copy.seconds)}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-app-muted">{copy.target}</dt>
                      <dd dir="ltr" className="mt-1 text-left text-app-foreground tabular-nums">
                        {formatSeconds(stream.freshness_target_seconds, locale, copy.seconds)}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-app-muted">{copy.latestPoll}</dt>
                      <dd className="mt-1 text-app-foreground">
                        {formatDate(stream.latest_poll_completed_at, locale, copy.noData)}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-app-muted">{copy.pollOverdue}</dt>
                      <dd dir="ltr" className="mt-1 text-left text-app-foreground tabular-nums">
                        {stream.poll_overdue_seconds === 0
                          ? copy.current
                          : formatSeconds(stream.poll_overdue_seconds, locale, copy.seconds)}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-app-muted">{copy.finalizationBacklog}</dt>
                      <dd className="mt-1 text-app-foreground">
                        {formatCount(stream.finalization_backlog_count, locale)}
                      </dd>
                    </div>
                  </dl>

                  <div className="mt-5 border-t border-app-border pt-4">
                    <p className="text-xs font-medium text-app-muted">{copy.providerRoutes}</p>
                    <div className="mt-3 flex flex-wrap gap-2">
                      {stream.provider_routes.map((route) => (
                        <Badge
                          key={route.connection_id}
                          variant={route.health_status === 'healthy' ? 'success' : 'danger'}
                        >
                          <span dir="ltr" className="break-all">
                            {route.ordinal}. {route.provider_id} ·{' '}
                            {route.health_status ?? copy.unavailable}
                          </span>
                        </Badge>
                      ))}
                    </div>
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>

        <section aria-labelledby="market-data-replay-health">
          <h3 id="market-data-replay-health" className="font-semibold text-app-foreground">
            {copy.recentReplays}
          </h3>
          <p className="mt-1 text-xs leading-5 text-app-muted">{copy.recentReplaysDescription}</p>

          {summary.recent_replays.length === 0 ? (
            <p className="mt-4 rounded-2xl border border-app-border p-5 text-sm text-app-muted">
              {copy.noReplays}
            </p>
          ) : (
            <ul className="mt-4 grid gap-3 lg:grid-cols-2">
              {summary.recent_replays.map((replay) => (
                <li
                  key={replay.replay_id}
                  className="min-w-0 rounded-2xl border border-app-border bg-app-surface-muted p-5"
                >
                  <div className="flex min-w-0 items-start justify-between gap-3">
                    <p dir="ltr" className="min-w-0 text-left font-mono text-xs break-all">
                      {replay.replay_id}
                    </p>
                    <Badge className="shrink-0" variant={jobVariants[replay.job_status]}>
                      {copy.jobStatuses[replay.job_status]}
                    </Badge>
                  </div>
                  <dl className="mt-4 grid gap-3 text-xs sm:grid-cols-2">
                    <div>
                      <dt className="text-app-muted">{copy.reason}</dt>
                      <dd dir="ltr" className="mt-1 text-left break-all text-app-foreground">
                        {replay.reason}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-app-muted">{copy.requestedAt}</dt>
                      <dd className="mt-1 text-app-foreground">
                        {formatDate(replay.requested_at, locale, copy.noData)}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-app-muted">{copy.revision}</dt>
                      <dd dir="ltr" className="mt-1 text-left break-all text-app-foreground">
                        {replay.revision_id ?? '—'}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-app-muted">{copy.version}</dt>
                      <dd className="mt-1 text-app-foreground">
                        {replay.revised_version === null
                          ? '—'
                          : formatCount(replay.revised_version, locale)}
                      </dd>
                    </div>
                  </dl>
                  {replay.error_code ? (
                    <p
                      dir="ltr"
                      className="mt-3 text-left font-mono text-xs break-all text-app-danger"
                    >
                      {replay.error_code}
                    </p>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
        </section>
      </CardContent>
    </Card>
  );
}
