import type {
  MarketContextAssessmentStatus,
  MarketContextFreshnessStatus,
  MarketContextHealthIssueCode,
  MarketContextMonitoringOverallStatus,
  MarketContextStreamHealthStatus,
} from '@/features/monitoring/api/types';
import type { BackgroundJobStatus } from '@/features/jobs/api/types';
import type { PlatformLocale } from '@/platform/i18n';

export type MarketContextHealthCopy = {
  title: string;
  description: string;
  overallStatus: string;
  overallStatuses: Record<MarketContextMonitoringOverallStatus, string>;
  streams: string;
  healthy: string;
  degraded: string;
  stale: string;
  noData: string;
  activeJobs: string;
  queued: string;
  running: string;
  retryAndFailure: string;
  retrying: string;
  failed: string;
  streamHealth: string;
  noStreams: string;
  source: string;
  expectedBoundary: string;
  assessmentBoundary: string;
  assessmentAge: string;
  boundaryLag: string;
  assessment: string;
  expiresAt: string;
  versions: string;
  latestJob: string;
  attempts: string;
  updatedAt: string;
  issues: string;
  seconds: string;
  healthStatuses: Record<MarketContextStreamHealthStatus, string>;
  freshnessStatuses: Record<MarketContextFreshnessStatus, string>;
  assessmentStatuses: Record<MarketContextAssessmentStatus, string>;
  jobStatuses: Record<BackgroundJobStatus, string>;
  issueLabels: Record<MarketContextHealthIssueCode, string>;
};

const copies: Record<PlatformLocale, MarketContextHealthCopy> = {
  en: {
    title: 'Market context health',
    description: 'Read-only freshness, boundary alignment, and durable evaluation state.',
    overallStatus: 'Context status',
    overallStatuses: {
      healthy: 'Healthy',
      warning: 'Needs review',
      critical: 'Critical',
      no_data: 'No data',
    } satisfies Record<MarketContextMonitoringOverallStatus, string>,
    streams: 'Context streams',
    healthy: 'Healthy',
    degraded: 'Degraded',
    stale: 'Stale',
    noData: 'No data',
    activeJobs: 'Active evaluations',
    queued: 'Queued',
    running: 'Running',
    retryAndFailure: 'Retries and failures',
    retrying: 'Retrying',
    failed: 'Failed streams',
    streamHealth: 'Source and pair health',
    noStreams: 'No market-context assessment or evaluation has been recorded yet.',
    source: 'Source',
    expectedBoundary: 'Expected boundary',
    assessmentBoundary: 'Assessment boundary',
    assessmentAge: 'Assessment age',
    boundaryLag: 'Boundary lag',
    assessment: 'Assessment',
    expiresAt: 'Expires',
    versions: 'Versions',
    latestJob: 'Latest evaluation job',
    attempts: 'Attempts',
    updatedAt: 'Updated',
    issues: 'Signals',
    seconds: 'seconds',
    healthStatuses: {
      healthy: 'Healthy',
      degraded: 'Degraded',
      no_data: 'No data',
    } satisfies Record<MarketContextStreamHealthStatus, string>,
    freshnessStatuses: {
      fresh: 'Fresh',
      stale: 'Stale',
      no_data: 'No data',
    } satisfies Record<MarketContextFreshnessStatus, string>,
    assessmentStatuses: {
      ready: 'Ready',
      insufficient_data: 'Insufficient data',
      stale: 'Stale',
    } satisfies Record<MarketContextAssessmentStatus, string>,
    jobStatuses: {
      queued: 'Queued',
      running: 'Running',
      succeeded: 'Succeeded',
      failed: 'Failed',
      cancelled: 'Cancelled',
    } satisfies Record<BackgroundJobStatus, string>,
    issueLabels: {
      assessment_expired: 'Assessment expired',
      assessment_missing: 'Assessment missing',
      assessment_not_ready: 'Assessment not ready',
      boundary_lagging: 'Boundary lagging',
      evaluation_failed: 'Evaluation failed',
      evaluation_pending: 'Evaluation pending',
      evaluation_retrying: 'Evaluation retrying',
    } satisfies Record<MarketContextHealthIssueCode, string>,
  },
  fa: {
    title: 'سلامت زمینه بازار',
    description: 'نمایش فقط‌خواندنی تازگی، هم‌ترازی مرز زمانی و وضعیت ارزیابی پایدار.',
    overallStatus: 'وضعیت زمینه',
    overallStatuses: {
      healthy: 'سالم',
      warning: 'نیازمند بررسی',
      critical: 'بحرانی',
      no_data: 'بدون داده',
    },
    streams: 'جریان‌های زمینه',
    healthy: 'سالم',
    degraded: 'افت‌کرده',
    stale: 'کهنه',
    noData: 'بدون داده',
    activeJobs: 'ارزیابی‌های فعال',
    queued: 'در صف',
    running: 'در حال اجرا',
    retryAndFailure: 'تلاش مجدد و خطا',
    retrying: 'تلاش مجدد',
    failed: 'جریان خطادار',
    streamHealth: 'سلامت منبع و جفت‌ارز',
    noStreams: 'هنوز ارزیابی یا job زمینه بازار ثبت نشده است.',
    source: 'منبع',
    expectedBoundary: 'مرز مورد انتظار',
    assessmentBoundary: 'مرز ارزیابی',
    assessmentAge: 'سن ارزیابی',
    boundaryLag: 'عقب‌ماندگی مرز',
    assessment: 'ارزیابی',
    expiresAt: 'انقضا',
    versions: 'نسخه‌ها',
    latestJob: 'آخرین job ارزیابی',
    attempts: 'تعداد تلاش',
    updatedAt: 'آخرین تغییر',
    issues: 'نشانه‌ها',
    seconds: 'ثانیه',
    healthStatuses: {
      healthy: 'سالم',
      degraded: 'افت‌کرده',
      no_data: 'بدون داده',
    },
    freshnessStatuses: {
      fresh: 'تازه',
      stale: 'کهنه',
      no_data: 'بدون داده',
    },
    assessmentStatuses: {
      ready: 'آماده',
      insufficient_data: 'داده ناکافی',
      stale: 'کهنه',
    },
    jobStatuses: {
      queued: 'در صف',
      running: 'در حال اجرا',
      succeeded: 'موفق',
      failed: 'ناموفق',
      cancelled: 'لغوشده',
    },
    issueLabels: {
      assessment_expired: 'ارزیابی منقضی شده',
      assessment_missing: 'ارزیابی موجود نیست',
      assessment_not_ready: 'ارزیابی آماده نیست',
      boundary_lagging: 'مرز زمانی عقب است',
      evaluation_failed: 'ارزیابی ناموفق بود',
      evaluation_pending: 'ارزیابی در انتظار است',
      evaluation_retrying: 'ارزیابی دوباره تلاش می‌شود',
    },
  },
};

export function getMarketContextHealthCopy(locale: PlatformLocale): MarketContextHealthCopy {
  return copies[locale];
}
