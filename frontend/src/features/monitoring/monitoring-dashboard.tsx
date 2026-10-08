import { PageFrame } from '@/components/platform/page-frame';
import { PageHeader } from '@/components/platform/page-header';
import {
  Badge,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  EmptyState,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui';
import type { BackgroundJobStatus } from '@/features/jobs/api/types';
import type {
  MonitoringOverallStatus,
  MonitoringSummary,
  RecommendationSeverity,
  SystemMetricSample,
} from '@/features/monitoring/api/types';
import { getMonitoringCopy } from '@/features/monitoring/monitoring-copy';
import type { PlatformLocale } from '@/platform/i18n';

type MonitoringDashboardProps = {
  locale: PlatformLocale;
  summary: MonitoringSummary;
};

type BadgeVariant = 'info' | 'success' | 'warning' | 'danger';

const overallStatusVariants: Record<MonitoringOverallStatus, BadgeVariant> = {
  healthy: 'success',
  warning: 'warning',
  critical: 'danger',
};

const severityVariants: Record<RecommendationSeverity, BadgeVariant> = {
  info: 'info',
  warning: 'warning',
  critical: 'danger',
};

const jobStatusVariants: Record<BackgroundJobStatus, BadgeVariant> = {
  queued: 'info',
  running: 'warning',
  succeeded: 'success',
  failed: 'danger',
  cancelled: 'info',
};

const ratioMetricNames = new Set<SystemMetricSample['metric_name']>([
  'api_error_rate',
  'api_repeated_read_ratio',
  'database_pool_utilization',
  'database_cpu_utilization',
  'database_disk_utilization',
  'backtest_failure_rate',
  'invalid_candle_ratio',
  'candle_storage_share',
  'analytical_database_resource_share',
]);

function formatDate(value: string, locale: PlatformLocale): string {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat(locale === 'fa' ? 'fa-IR' : 'en-US', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date);
}

function formatMetricValue(sample: SystemMetricSample, locale: PlatformLocale): string {
  const value = Number(sample.value);

  if (!Number.isFinite(value)) {
    return sample.value;
  }

  const numberLocale = locale === 'fa' ? 'fa-IR' : 'en-US';

  if (sample.unit === 'fraction' || ratioMetricNames.has(sample.metric_name)) {
    return new Intl.NumberFormat(numberLocale, {
      style: 'percent',
      minimumFractionDigits: 0,
      maximumFractionDigits: 2,
    }).format(value);
  }

  const formattedValue = new Intl.NumberFormat(numberLocale, {
    maximumFractionDigits: 3,
  }).format(value);

  if (sample.unit === 'seconds') {
    return locale === 'fa' ? `${formattedValue} ثانیه` : `${formattedValue} seconds`;
  }

  if (sample.unit === 'milliseconds') {
    return `${formattedValue} ms`;
  }

  return `${formattedValue} ${sample.unit}`;
}

function removeDemoPrefix(title: string): string {
  return title.replace(/^\[DEMO\]\s*/u, '');
}

function formatCount(value: number, locale: PlatformLocale): string {
  return new Intl.NumberFormat(locale === 'fa' ? 'fa-IR' : 'en-US').format(value);
}

function formatPercent(value: string | null, locale: PlatformLocale): string {
  if (value === null) {
    return '—';
  }

  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    return value;
  }

  return new Intl.NumberFormat(locale === 'fa' ? 'fa-IR' : 'en-US', {
    style: 'percent',
    maximumFractionDigits: 2,
  }).format(parsed);
}

function formatDuration(value: string | null, locale: PlatformLocale): string {
  if (value === null) {
    return '—';
  }

  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    return value;
  }

  const formatted = new Intl.NumberFormat(locale === 'fa' ? 'fa-IR' : 'en-US', {
    maximumFractionDigits: 2,
  }).format(parsed);
  return locale === 'fa' ? `${formatted} ثانیه` : `${formatted} seconds`;
}

export default function MonitoringDashboard({ locale, summary }: MonitoringDashboardProps) {
  const copy = getMonitoringCopy(locale);
  const isDemoRecommendation = (title: string) => title.startsWith('[DEMO]');
  const operations = summary.operations;

  return (
    <PageFrame>
      <PageHeader
        eyebrow={copy.eyebrow}
        title={copy.title}
        description={copy.description}
        actions={
          <Badge variant={overallStatusVariants[summary.overall_status]}>
            {copy.overallStatus}: {copy.statuses[summary.overall_status]}
          </Badge>
        }
      >
        <div className="rounded-2xl border border-app-info-border bg-app-info-soft px-5 py-4 text-sm leading-7 text-app-info">
          {copy.capacityPlanningOnly}
        </div>
      </PageHeader>

      {operations ? (
        <Card>
          <CardHeader>
            <CardTitle>{copy.operations}</CardTitle>
            <CardDescription>{copy.operationsDescription}</CardDescription>
          </CardHeader>

          <CardContent className="space-y-6">
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
              <article className="rounded-2xl border border-app-border bg-app-surface-muted p-5">
                <p className="text-sm font-medium text-app-foreground">{copy.queue}</p>
                <p className="mt-4 text-2xl font-bold text-app-foreground">
                  {formatCount(operations.jobs.total_count, locale)}
                </p>
                <p className="mt-3 text-xs leading-6 text-app-muted">
                  {copy.queued}: {formatCount(operations.jobs.queued_count, locale)} ·{' '}
                  {copy.running}: {formatCount(operations.jobs.running_count, locale)} ·{' '}
                  {copy.stuck}: {formatCount(operations.jobs.stuck_count, locale)}
                </p>
              </article>

              <article className="rounded-2xl border border-app-border bg-app-surface-muted p-5">
                <p className="text-sm font-medium text-app-foreground">{copy.providers}</p>
                <p className="mt-4 text-2xl font-bold text-app-foreground">
                  {formatCount(operations.connections.total_count, locale)}
                </p>
                <p className="mt-3 text-xs leading-6 text-app-muted">
                  {copy.healthy}: {formatCount(operations.connections.healthy_count, locale)} ·{' '}
                  {copy.unhealthy}: {formatCount(operations.connections.unhealthy_count, locale)} ·{' '}
                  {copy.untested}: {formatCount(operations.connections.untested_count, locale)}
                </p>
                {operations.connections.latest_error_code ? (
                  <p dir="ltr" className="mt-2 text-left text-xs text-app-danger">
                    {operations.connections.latest_error_code}
                  </p>
                ) : null}
                <p className="mt-2 text-xs leading-5 text-app-muted">
                  {copy.latestTest}:{' '}
                  {operations.connections.latest_tested_at
                    ? formatDate(operations.connections.latest_tested_at, locale)
                    : copy.noData}
                </p>
              </article>

              <article className="rounded-2xl border border-app-border bg-app-surface-muted p-5">
                <p className="text-sm font-medium text-app-foreground">{copy.imports}</p>
                <p dir="ltr" className="mt-4 text-left text-2xl font-bold text-app-foreground">
                  {formatPercent(operations.imports.failure_rate, locale)}
                </p>
                <p className="mt-3 text-xs leading-6 text-app-muted">
                  {copy.failed}: {formatCount(operations.imports.failed_count, locale)} ·{' '}
                  {copy.succeeded}: {formatCount(operations.imports.succeeded_count, locale)} ·{' '}
                  {copy.recentSample}: {formatCount(operations.imports.sample_size, locale)}
                </p>
                <dl className="mt-2 space-y-1 text-xs leading-5 text-app-muted">
                  <div>
                    <dt className="inline">{copy.latestSuccess}: </dt>
                    <dd className="inline">
                      {operations.imports.latest_success_at
                        ? formatDate(operations.imports.latest_success_at, locale)
                        : copy.noData}
                    </dd>
                  </div>
                  <div>
                    <dt className="inline">{copy.latestFailure}: </dt>
                    <dd className="inline">
                      {operations.imports.latest_failure_at
                        ? formatDate(operations.imports.latest_failure_at, locale)
                        : copy.noData}
                      {operations.imports.latest_failure_code
                        ? ` · ${operations.imports.latest_failure_code}`
                        : ''}
                    </dd>
                  </div>
                </dl>
              </article>

              <article className="rounded-2xl border border-app-border bg-app-surface-muted p-5">
                <p className="text-sm font-medium text-app-foreground">{copy.averageDuration}</p>
                <p dir="ltr" className="mt-4 text-left text-2xl font-bold text-app-foreground">
                  {formatDuration(operations.jobs.average_duration_seconds, locale)}
                </p>
                <p className="mt-3 text-xs leading-6 text-app-muted">
                  {copy.recentSample}:{' '}
                  {formatCount(operations.jobs.recent_terminal_sample_size, locale)}
                </p>
              </article>
            </div>

            <div className="grid gap-4 lg:grid-cols-[minmax(0,2fr)_minmax(16rem,1fr)]">
              <div className="overflow-hidden rounded-2xl border border-app-border">
                <div className="border-b border-app-border bg-app-surface-muted px-5 py-4">
                  <h3 className="font-semibold text-app-foreground">{copy.recentJobs}</h3>
                  <p className="mt-1 text-xs leading-5 text-app-muted">
                    {copy.recentJobsDescription}
                  </p>
                </div>

                {operations.jobs.recent_jobs.length === 0 ? (
                  <p className="px-5 py-8 text-sm text-app-muted">{copy.noRecentJobs}</p>
                ) : (
                  <>
                    <ul
                      aria-label={copy.recentJobs}
                      className="space-y-3 p-4 md:hidden"
                      data-testid="recent-jobs-mobile-list"
                    >
                      {operations.jobs.recent_jobs.map((job) => (
                        <li
                          key={job.job_id}
                          className="min-w-0 rounded-xl border border-app-border bg-app-surface p-4"
                        >
                          <div className="flex min-w-0 items-start justify-between gap-3">
                            <p
                              dir="ltr"
                              className="min-w-0 text-left font-mono text-xs break-all text-app-foreground"
                            >
                              <span className="sr-only">{copy.jobId}: </span>
                              {job.job_id}
                            </p>

                            <Badge className="shrink-0" variant={jobStatusVariants[job.status]}>
                              <span className="sr-only">{copy.status}: </span>
                              {copy.jobStatuses[job.status]}
                            </Badge>
                          </div>

                          <dl className="mt-4 grid gap-3 text-xs sm:grid-cols-2">
                            <div className="min-w-0">
                              <dt className="text-app-muted">{copy.kind}</dt>
                              <dd
                                dir="ltr"
                                className="mt-1 text-left break-all text-app-foreground"
                              >
                                {job.kind}
                              </dd>
                            </div>
                            <div>
                              <dt className="text-app-muted">{copy.progress}</dt>
                              <dd
                                dir="ltr"
                                className="mt-1 text-left font-semibold text-app-foreground tabular-nums"
                              >
                                {job.progress_percent}%
                              </dd>
                            </div>
                            <div className="min-w-0">
                              <dt className="text-app-muted">{copy.error}</dt>
                              <dd
                                dir="ltr"
                                className="mt-1 text-left break-all text-app-foreground"
                              >
                                {job.error_code ?? '—'}
                              </dd>
                            </div>
                            <div>
                              <dt className="text-app-muted">{copy.updatedAt}</dt>
                              <dd className="mt-1 text-app-foreground">
                                {formatDate(job.updated_at, locale)}
                              </dd>
                            </div>
                          </dl>
                        </li>
                      ))}
                    </ul>

                    <div className="hidden min-w-0 md:block" data-testid="recent-jobs-table">
                      <Table
                        scrollLabel={copy.recentJobs}
                        className="min-w-[52rem]"
                        containerClassName="rounded-none border-0"
                      >
                        <TableHeader>
                          <TableRow>
                            <TableHead>{copy.jobId}</TableHead>
                            <TableHead>{copy.kind}</TableHead>
                            <TableHead>{copy.status}</TableHead>
                            <TableHead>{copy.progress}</TableHead>
                            <TableHead>{copy.error}</TableHead>
                            <TableHead>{copy.updatedAt}</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {operations.jobs.recent_jobs.map((job) => (
                            <TableRow key={job.job_id}>
                              <TableCell dir="ltr" className="font-mono text-xs">
                                {job.job_id}
                              </TableCell>
                              <TableCell dir="ltr" className="text-xs">
                                {job.kind}
                              </TableCell>
                              <TableCell>
                                <Badge variant={jobStatusVariants[job.status]}>
                                  {copy.jobStatuses[job.status]}
                                </Badge>
                              </TableCell>
                              <TableCell dir="ltr">{job.progress_percent}%</TableCell>
                              <TableCell dir="ltr" className="text-xs">
                                {job.error_code ?? '—'}
                              </TableCell>
                              <TableCell>{formatDate(job.updated_at, locale)}</TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </div>
                  </>
                )}
              </div>

              <div className="rounded-2xl border border-app-border bg-app-surface-muted p-5">
                <h3 className="font-semibold text-app-foreground">{copy.failureReasons}</h3>
                {operations.jobs.failure_reasons.length === 0 ? (
                  <p className="mt-4 text-sm leading-6 text-app-muted">{copy.noFailureReasons}</p>
                ) : (
                  <dl className="mt-4 space-y-3">
                    {operations.jobs.failure_reasons.map((reason) => (
                      <div
                        key={reason.error_code}
                        className="flex items-center justify-between gap-4 border-b border-app-border pb-3 last:border-0 last:pb-0"
                      >
                        <dt dir="ltr" className="text-left font-mono text-xs text-app-muted">
                          {reason.error_code}
                        </dt>
                        <dd className="font-semibold text-app-foreground">
                          {formatCount(reason.count, locale)}
                        </dd>
                      </div>
                    ))}
                  </dl>
                )}
              </div>
            </div>
          </CardContent>
        </Card>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle>{copy.latestMetrics}</CardTitle>
          <CardDescription>{copy.latestMetricsDescription}</CardDescription>
        </CardHeader>

        <CardContent>
          {summary.latest_metrics.length === 0 ? (
            <EmptyState title={copy.emptyMetricsTitle} description={copy.emptyMetricsDescription} />
          ) : (
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {summary.latest_metrics.map((sample) => (
                <article
                  key={sample.sample_id}
                  className="rounded-2xl border border-app-border bg-app-surface-muted p-5"
                >
                  <div className="flex items-start justify-between gap-4">
                    <p className="text-sm leading-6 font-medium text-app-foreground">
                      {copy.metrics[sample.metric_name]}
                    </p>

                    <span className="h-2.5 w-2.5 shrink-0 rounded-full bg-app-accent" />
                  </div>

                  <p dir="ltr" className="mt-5 text-left text-2xl font-bold text-app-foreground">
                    {formatMetricValue(sample, locale)}
                  </p>

                  <dl className="mt-5 space-y-2 border-t border-app-border pt-4 text-xs">
                    <div className="flex items-center justify-between gap-4">
                      <dt className="text-app-muted">{copy.source}</dt>
                      <dd dir="ltr" className="text-app-foreground">
                        {sample.source}
                      </dd>
                    </div>

                    <div className="flex items-center justify-between gap-4">
                      <dt className="text-app-muted">{copy.recordedAt}</dt>
                      <dd className="text-app-foreground">
                        {formatDate(sample.recorded_at, locale)}
                      </dd>
                    </div>
                  </dl>
                </article>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{copy.recommendations}</CardTitle>
          <CardDescription>{copy.recommendationsDescription}</CardDescription>
        </CardHeader>

        <CardContent>
          {summary.active_recommendations.length === 0 ? (
            <EmptyState
              title={copy.emptyRecommendationsTitle}
              description={copy.emptyRecommendationsDescription}
            />
          ) : (
            <div className="grid gap-4 lg:grid-cols-2">
              {summary.active_recommendations.map((recommendation) => (
                <article
                  key={recommendation.recommendation_id}
                  className="rounded-2xl border border-app-border bg-app-surface-muted p-5"
                >
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <Badge variant={severityVariants[recommendation.severity]}>
                      {copy.severities[recommendation.severity]}
                    </Badge>

                    {isDemoRecommendation(recommendation.title) ? (
                      <Badge variant="info">{copy.demoEvidence}</Badge>
                    ) : null}
                  </div>

                  <h3 className="mt-5 text-base leading-7 font-semibold text-app-foreground">
                    {removeDemoPrefix(recommendation.title)}
                  </h3>

                  <p className="mt-3 text-sm text-app-muted">
                    {copy.candidates[recommendation.candidate]}
                  </p>
                </article>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </PageFrame>
  );
}
