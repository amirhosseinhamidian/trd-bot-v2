import type { DashboardLocale } from '@/components/dashboard/dashboard-copy';
import type {
  ArchitectureCandidate,
  MonitoringOverallStatus,
  RecommendationSeverity,
  SystemMetricName,
} from '@/lib/api/types';

export type MonitoringCopy = {
  eyebrow: string;
  title: string;
  description: string;
  capacityPlanningOnly: string;
  overallStatus: string;
  latestMetrics: string;
  latestMetricsDescription: string;
  recommendations: string;
  recommendationsDescription: string;
  emptyMetricsTitle: string;
  emptyMetricsDescription: string;
  emptyRecommendationsTitle: string;
  emptyRecommendationsDescription: string;
  demoEvidence: string;
  source: string;
  recordedAt: string;
  statuses: Record<MonitoringOverallStatus, string>;
  severities: Record<RecommendationSeverity, string>;
  candidates: Record<ArchitectureCandidate, string>;
  metrics: Record<SystemMetricName, string>;
};

const copies: Record<DashboardLocale, MonitoringCopy> = {
  fa: {
    eyebrow: 'Infrastructure capacity monitoring',
    title: 'پایش معماری سیستم',
    description:
      'متریک‌های عملیاتی را بررسی کنید و تنها زمانی درباره افزودن Redis، TimescaleDB یا ClickHouse تصمیم بگیرید که شواهد پایدار ثبت شده باشد.',
    capacityPlanningOnly:
      'این پیشنهادها فقط برای برنامه‌ریزی ظرفیت و معماری نرم‌افزار هستند و پیشنهاد مالی یا معاملاتی محسوب نمی‌شوند.',
    overallStatus: 'وضعیت کلی',
    latestMetrics: 'آخرین متریک‌ها',
    latestMetricsDescription: 'جدیدترین نمونه ثبت‌شده برای هر شاخص عملیاتی',
    recommendations: 'پیشنهادهای فعال معماری',
    recommendationsDescription: 'پیشنهادهایی که از چند پنجره متوالی شواهد عبور کرده‌اند',
    emptyMetricsTitle: 'هنوز متریکی ثبت نشده است',
    emptyMetricsDescription: 'Collector یا اسکریپت داده نمایشی را اجرا کنید.',
    emptyRecommendationsTitle: 'پیشنهاد فعالی وجود ندارد',
    emptyRecommendationsDescription: 'در حال حاضر شواهد پایداری برای تغییر معماری ثبت نشده است.',
    demoEvidence: 'داده نمایشی',
    source: 'منبع',
    recordedAt: 'زمان ثبت',
    statuses: {
      healthy: 'سالم',
      warning: 'نیازمند بررسی',
      critical: 'بحرانی',
    },
    severities: {
      info: 'اطلاعاتی',
      warning: 'هشدار',
      critical: 'بحرانی',
    },
    candidates: {
      postgresql_tuning: 'بهینه‌سازی PostgreSQL',
      redis: 'بررسی Redis',
      timescaledb: 'بررسی TimescaleDB',
      clickhouse: 'بررسی ClickHouse',
    },
    metrics: {
      api_request_latency_p95: 'تأخیر P95 درخواست‌های API',
      api_error_rate: 'نرخ خطای API',
      api_repeated_read_ratio: 'نسبت خواندن‌های تکراری API',
      database_query_latency_p95: 'تأخیر P95 کوئری دیتابیس',
      database_pool_utilization: 'مصرف Connection Pool',
      database_cpu_utilization: 'مصرف CPU دیتابیس',
      database_disk_utilization: 'مصرف دیسک دیتابیس',
      job_queue_wait_p95: 'زمان انتظار P95 صف پردازش',
      backtest_failure_rate: 'نرخ شکست Backtest',
      market_data_lag: 'تأخیر داده بازار',
      invalid_candle_ratio: 'نسبت کندل‌های نامعتبر',
      candle_storage_share: 'سهم کندل‌ها از فضای ذخیره‌سازی',
      time_series_query_latency_p95: 'تأخیر P95 کوئری‌های سری زمانی',
      analytical_query_latency_p95: 'تأخیر P95 کوئری‌های تحلیلی',
      analytical_database_resource_share: 'سهم تحلیل از منابع دیتابیس',
    },
  },
  en: {
    eyebrow: 'Infrastructure capacity monitoring',
    title: 'System architecture monitoring',
    description:
      'Review operational metrics and consider Redis, TimescaleDB, or ClickHouse only after sustained evidence has been recorded.',
    capacityPlanningOnly:
      'These recommendations are only for software architecture and capacity planning. They are not financial or trading recommendations.',
    overallStatus: 'Overall status',
    latestMetrics: 'Latest metrics',
    latestMetricsDescription: 'Most recent recorded sample for each operational metric',
    recommendations: 'Active architecture recommendations',
    recommendationsDescription:
      'Recommendations supported by evidence across consecutive evaluation windows',
    emptyMetricsTitle: 'No metrics recorded yet',
    emptyMetricsDescription: 'Run a collector or the monitoring demo seed script.',
    emptyRecommendationsTitle: 'No active recommendations',
    emptyRecommendationsDescription:
      'No sustained evidence currently supports an architecture change.',
    demoEvidence: 'Demo evidence',
    source: 'Source',
    recordedAt: 'Recorded at',
    statuses: {
      healthy: 'Healthy',
      warning: 'Needs review',
      critical: 'Critical',
    },
    severities: {
      info: 'Information',
      warning: 'Warning',
      critical: 'Critical',
    },
    candidates: {
      postgresql_tuning: 'PostgreSQL tuning',
      redis: 'Evaluate Redis',
      timescaledb: 'Evaluate TimescaleDB',
      clickhouse: 'Evaluate ClickHouse',
    },
    metrics: {
      api_request_latency_p95: 'API request latency P95',
      api_error_rate: 'API error rate',
      api_repeated_read_ratio: 'Repeated API read ratio',
      database_query_latency_p95: 'Database query latency P95',
      database_pool_utilization: 'Database pool utilization',
      database_cpu_utilization: 'Database CPU utilization',
      database_disk_utilization: 'Database disk utilization',
      job_queue_wait_p95: 'Job queue wait P95',
      backtest_failure_rate: 'Backtest failure rate',
      market_data_lag: 'Market data lag',
      invalid_candle_ratio: 'Invalid candle ratio',
      candle_storage_share: 'Candle storage share',
      time_series_query_latency_p95: 'Time-series query latency P95',
      analytical_query_latency_p95: 'Analytical query latency P95',
      analytical_database_resource_share: 'Analytical database resource share',
    },
  },
};

export function getMonitoringCopy(locale: DashboardLocale): MonitoringCopy {
  return copies[locale];
}
