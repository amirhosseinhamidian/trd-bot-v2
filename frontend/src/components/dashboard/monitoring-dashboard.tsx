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
} from '@/components/ui';
import type {
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

export default function MonitoringDashboard({ locale, summary }: MonitoringDashboardProps) {
  const copy = getMonitoringCopy(locale);
  const isDemoRecommendation = (title: string) => title.startsWith('[DEMO]');

  return (
    <div className="space-y-8">
      <section>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-xs font-semibold tracking-[0.25em] text-cyan-400 uppercase">
              {copy.eyebrow}
            </p>

            <h1 className="mt-3 text-3xl font-bold tracking-tight text-white sm:text-4xl">
              {copy.title}
            </h1>
          </div>

          <Badge variant={overallStatusVariants[summary.overall_status]}>
            {copy.overallStatus}: {copy.statuses[summary.overall_status]}
          </Badge>
        </div>

        <p className="mt-3 max-w-3xl text-sm leading-7 text-slate-400 sm:text-base">
          {copy.description}
        </p>

        <div className="mt-5 rounded-2xl border border-blue-400/20 bg-blue-400/5 px-5 py-4 text-sm leading-7 text-blue-200">
          {copy.capacityPlanningOnly}
        </div>
      </section>

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
                  className="rounded-2xl border border-slate-800 bg-slate-950/50 p-5"
                >
                  <div className="flex items-start justify-between gap-4">
                    <p className="text-sm leading-6 font-medium text-slate-300">
                      {copy.metrics[sample.metric_name]}
                    </p>

                    <span className="h-2.5 w-2.5 shrink-0 rounded-full bg-cyan-400" />
                  </div>

                  <p dir="ltr" className="mt-5 text-left text-2xl font-bold text-white">
                    {formatMetricValue(sample, locale)}
                  </p>

                  <dl className="mt-5 space-y-2 border-t border-slate-800 pt-4 text-xs">
                    <div className="flex items-center justify-between gap-4">
                      <dt className="text-slate-500">{copy.source}</dt>
                      <dd dir="ltr" className="text-slate-300">
                        {sample.source}
                      </dd>
                    </div>

                    <div className="flex items-center justify-between gap-4">
                      <dt className="text-slate-500">{copy.recordedAt}</dt>
                      <dd className="text-slate-300">{formatDate(sample.recorded_at, locale)}</dd>
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
                  className="rounded-2xl border border-slate-800 bg-slate-950/50 p-5"
                >
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <Badge variant={severityVariants[recommendation.severity]}>
                      {copy.severities[recommendation.severity]}
                    </Badge>

                    {isDemoRecommendation(recommendation.title) ? (
                      <Badge variant="info">{copy.demoEvidence}</Badge>
                    ) : null}
                  </div>

                  <h3 className="mt-5 text-base leading-7 font-semibold text-white">
                    {removeDemoPrefix(recommendation.title)}
                  </h3>

                  <p className="mt-3 text-sm text-slate-400">
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
