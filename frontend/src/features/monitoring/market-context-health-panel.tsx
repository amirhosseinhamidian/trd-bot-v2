import { Badge, Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui';
import type { BadgeVariant } from '@/components/ui';
import type { BackgroundJobStatus } from '@/features/jobs/api/types';
import type {
  MarketContextFreshnessStatus,
  MarketContextMonitoringOverallStatus,
  MarketContextMonitoringSummary,
  MarketContextStreamHealthStatus,
} from '@/features/monitoring/api/types';
import { getMarketContextHealthCopy } from '@/features/monitoring/market-context-health-copy';
import type { PlatformLocale } from '@/platform/i18n';

type MarketContextHealthPanelProps = {
  locale: PlatformLocale;
  summary: MarketContextMonitoringSummary;
};

const overallVariants: Record<MarketContextMonitoringOverallStatus, BadgeVariant> = {
  healthy: 'success',
  warning: 'warning',
  critical: 'danger',
  no_data: 'neutral',
};

const healthVariants: Record<MarketContextStreamHealthStatus, BadgeVariant> = {
  healthy: 'success',
  degraded: 'danger',
  no_data: 'neutral',
};

const freshnessVariants: Record<MarketContextFreshnessStatus, BadgeVariant> = {
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

function formatDate(value: string | null, locale: PlatformLocale): string {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(locale === 'fa' ? 'fa-IR' : 'en-US', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date);
}

export function MarketContextHealthPanel({ locale, summary }: MarketContextHealthPanelProps) {
  const copy = getMarketContextHealthCopy(locale);

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
              {copy.healthy}: {formatCount(summary.healthy_count, locale)} · {copy.degraded}:{' '}
              {formatCount(summary.degraded_count, locale)}
            </p>
          </article>

          <article className="rounded-2xl border border-app-border bg-app-surface-muted p-5">
            <p className="text-sm font-medium text-app-foreground">{copy.stale}</p>
            <p className="mt-3 text-2xl font-bold text-app-foreground">
              {formatCount(summary.stale_count, locale)}
            </p>
            <p className="mt-2 text-xs leading-6 text-app-muted">
              {copy.noData}: {formatCount(summary.no_data_count, locale)} · {copy.boundaryLag}:{' '}
              {formatCount(summary.backlog.lagging_streams, locale)}
            </p>
          </article>

          <article className="rounded-2xl border border-app-border bg-app-surface-muted p-5">
            <p className="text-sm font-medium text-app-foreground">{copy.activeJobs}</p>
            <p className="mt-3 text-2xl font-bold text-app-foreground">
              {formatCount(summary.backlog.queued_jobs + summary.backlog.running_jobs, locale)}
            </p>
            <p className="mt-2 text-xs leading-6 text-app-muted">
              {copy.queued}: {formatCount(summary.backlog.queued_jobs, locale)} · {copy.running}:{' '}
              {formatCount(summary.backlog.running_jobs, locale)}
            </p>
          </article>

          <article className="rounded-2xl border border-app-border bg-app-surface-muted p-5">
            <p className="text-sm font-medium text-app-foreground">{copy.retryAndFailure}</p>
            <p className="mt-3 text-2xl font-bold text-app-foreground">
              {formatCount(summary.backlog.retrying_jobs, locale)}
            </p>
            <p className="mt-2 text-xs leading-6 text-app-muted">
              {copy.failed}: {formatCount(summary.backlog.failed_streams, locale)} · {copy.noData}:{' '}
              {formatCount(summary.backlog.missing_assessments, locale)}
            </p>
          </article>
        </div>

        <section aria-labelledby="market-context-stream-health">
          <h3 id="market-context-stream-health" className="font-semibold text-app-foreground">
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
                  key={`${stream.source}:${stream.pair.base_asset}:${stream.pair.quote_asset}`}
                  className="min-w-0 rounded-2xl border border-app-border bg-app-surface-muted p-5"
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0">
                      <h4 dir="ltr" className="text-left font-semibold text-app-foreground">
                        {stream.pair.base_asset}/{stream.pair.quote_asset}
                      </h4>
                      <p dir="ltr" className="mt-1 text-left text-xs break-all text-app-muted">
                        {copy.source}: {stream.source}
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

                  <dl className="mt-5 grid gap-4 text-xs sm:grid-cols-2">
                    <div>
                      <dt className="text-app-muted">{copy.expectedBoundary}</dt>
                      <dd className="mt-1 text-app-foreground">
                        {formatDate(stream.expected_as_of, locale)}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-app-muted">{copy.assessmentBoundary}</dt>
                      <dd className="mt-1 text-app-foreground">
                        {formatDate(stream.latest_assessment_as_of, locale)}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-app-muted">{copy.assessmentAge}</dt>
                      <dd dir="ltr" className="mt-1 text-left text-app-foreground tabular-nums">
                        {stream.assessment_age_seconds === null
                          ? '—'
                          : `${formatCount(stream.assessment_age_seconds, locale)} ${copy.seconds}`}
                      </dd>
                    </div>
                    <div>
                      <dt className="text-app-muted">{copy.boundaryLag}</dt>
                      <dd dir="ltr" className="mt-1 text-left text-app-foreground tabular-nums">
                        {stream.boundary_lag_seconds === null
                          ? '—'
                          : `${formatCount(stream.boundary_lag_seconds, locale)} ${copy.seconds}`}
                      </dd>
                    </div>
                    <div className="min-w-0">
                      <dt className="text-app-muted">{copy.assessment}</dt>
                      <dd dir="ltr" className="mt-1 text-left break-all text-app-foreground">
                        {stream.latest_assessment_id ?? '—'}
                      </dd>
                      {stream.latest_assessment_status ? (
                        <p className="mt-1 text-app-muted">
                          {copy.assessmentStatuses[stream.latest_assessment_status]} ·{' '}
                          {copy.expiresAt}: {formatDate(stream.expires_at, locale)}
                        </p>
                      ) : null}
                    </div>
                    <div className="min-w-0">
                      <dt className="text-app-muted">{copy.versions}</dt>
                      <dd dir="ltr" className="mt-1 text-left break-all text-app-foreground">
                        {stream.feature_set_version ?? '—'} · {stream.algorithm_version ?? '—'}
                      </dd>
                    </div>
                  </dl>

                  {stream.latest_job_id && stream.latest_job_status ? (
                    <div className="mt-5 rounded-xl border border-app-border bg-app-surface p-4">
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div className="min-w-0">
                          <p className="text-xs text-app-muted">{copy.latestJob}</p>
                          <p
                            dir="ltr"
                            className="mt-1 text-left font-mono text-xs break-all text-app-foreground"
                          >
                            {stream.latest_job_id}
                          </p>
                        </div>
                        <Badge variant={jobVariants[stream.latest_job_status]}>
                          {copy.jobStatuses[stream.latest_job_status]}
                        </Badge>
                      </div>
                      <p className="mt-3 text-xs text-app-muted">
                        {copy.attempts}: {formatCount(stream.latest_job_attempt_count ?? 0, locale)}
                        /{formatCount(stream.latest_job_max_attempts ?? 0, locale)} ·{' '}
                        {copy.updatedAt}: {formatDate(stream.latest_job_updated_at, locale)}
                      </p>
                      {stream.latest_job_error_code ? (
                        <p dir="ltr" className="mt-2 text-left text-xs break-all text-app-danger">
                          {stream.latest_job_error_code}
                        </p>
                      ) : null}
                    </div>
                  ) : null}

                  {stream.issue_codes.length > 0 ? (
                    <div className="mt-4">
                      <p className="text-xs text-app-muted">{copy.issues}</p>
                      <div className="mt-2 flex flex-wrap gap-2">
                        {stream.issue_codes.map((issue) => (
                          <Badge key={issue} variant="warning">
                            {copy.issueLabels[issue]}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  ) : null}
                </article>
              ))}
            </div>
          )}
        </section>
      </CardContent>
    </Card>
  );
}
