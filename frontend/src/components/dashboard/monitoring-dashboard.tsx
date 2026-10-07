import { getMonitoringCopy } from '@/components/dashboard/monitoring-copy';
import type { DashboardLocale } from '@/components/dashboard/dashboard-copy';
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
import type {
  BackgroundJobStatus,
  MonitoringOverallStatus,
  MonitoringSummary,
  RecommendationSeverity,
  SystemMetricSample,
} from '@/lib/api/types';

type MonitoringDashboardProps = {
  locale: DashboardLocale;
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

function formatDate(value: string, locale: DashboardLocale): string {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat(locale === 'fa' ? 'fa-IR' : 'en-US', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date);
}

function formatMetricValue(sample: SystemMetricSample, locale: DashboardLocale): string {
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

function formatCount(value: number, locale: DashboardLocale): string {
  return new Intl.NumberFormat(locale === 'fa' ? 'fa-IR' : 'en-US').format(value);
}

function formatPercent(value: string | null, locale: DashboardLocale): string {
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

function formatDuration(value: string | null, locale: DashboardLocale): string {
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
    <div className="space-y-8">
      <section>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-xs font-semibold tracking-[0.25em] text-app-accent uppercase">
              {copy.eyebrow}
            </p>

            <h1 className="mt-3 text-3xl font-bold tracking-tight text-app-foreground sm:text-4xl">
              {copy.title}
            </h1>
          </div>

          <Badge variant={overallStatusVariants[summary.overall_status]}>
            {copy.overallStatus}: {copy.statuses[summary.overall_status]}
          </Badge>
        </div>

        <p className="mt-3 max-w-3xl text-sm leading-7 text-app-muted sm:text-base">
          {copy.description}
        </p>

        <div className="mt-5 rounded-2xl border border-app-info-border bg-app-info-soft px-5 py-4 text-sm leading-7 text-app-info">
          {copy.capacityPlanningOnly}
        </div>
      </section>

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
                  <Table>
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
    </div>
  );
}
