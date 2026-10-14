import type {
  MarketDataFreshnessStatus,
  MarketDataMonitoringOverallStatus,
  MarketDataStreamHealthStatus,
} from '@/features/monitoring/api/types';
import type { BackgroundJobStatus } from '@/features/jobs/api/types';
import type { PlatformLocale } from '@/platform/i18n';

export type MarketDataHealthCopy = {
  title: string;
  description: string;
  overallStatus: string;
  streams: string;
  healthyStreams: string;
  degradedStreams: string;
  staleStreams: string;
  pollingBacklog: string;
  replayBacklog: string;
  overdue: string;
  finalization: string;
  pending: string;
  failed: string;
  streamHealth: string;
  noStreams: string;
  selectedProvider: string;
  latestFinalized: string;
  latestPoll: string;
  lag: string;
  target: string;
  pollOverdue: string;
  finalizationBacklog: string;
  providerRoutes: string;
  unavailable: string;
  recentReplays: string;
  recentReplaysDescription: string;
  noReplays: string;
  reason: string;
  requestedAt: string;
  revision: string;
  version: string;
  noData: string;
  current: string;
  seconds: string;
  overallStatuses: Record<MarketDataMonitoringOverallStatus, string>;
  healthStatuses: Record<MarketDataStreamHealthStatus, string>;
  freshnessStatuses: Record<MarketDataFreshnessStatus, string>;
  jobStatuses: Record<BackgroundJobStatus, string>;
};

const copies: Record<PlatformLocale, MarketDataHealthCopy> = {
  fa: {
    title: 'سلامت داده بازار',
    description:
      'نمای خواندنی از تازگی کندل‌های نهایی، تأخیر، backlog و چرخه replay؛ بدون payload، هویت worker یا اکشن معاملاتی',
    overallStatus: 'وضعیت داده بازار',
    streams: 'جریان‌ها',
    healthyStreams: 'سالم',
    degradedStreams: 'نیازمند بررسی',
    staleStreams: 'قدیمی',
    pollingBacklog: 'backlog دریافت',
    replayBacklog: 'backlog بازپخش',
    overdue: 'موعد گذشته',
    finalization: 'در انتظار نهایی‌سازی',
    pending: 'در انتظار نتیجه',
    failed: 'ناموفق',
    streamHealth: 'سلامت جریان‌ها',
    noStreams: 'هنوز جریان داده‌ای در watchlist ثبت نشده است.',
    selectedProvider: 'منبع انتخاب‌شده',
    latestFinalized: 'آخرین کندل نهایی',
    latestPoll: 'آخرین دریافت',
    lag: 'تأخیر',
    target: 'هدف تازگی',
    pollOverdue: 'تأخیر دریافت',
    finalizationBacklog: 'صف نهایی‌سازی',
    providerRoutes: 'مسیرهای منبع',
    unavailable: 'ثبت‌نشده',
    recentReplays: 'بازپخش‌های اخیر',
    recentReplaysDescription:
      'وضعیت job و revision ماندگار؛ جزئیات خطا فقط به‌صورت کد امن نمایش داده می‌شود.',
    noReplays: 'هنوز replayای ثبت نشده است.',
    reason: 'علت',
    requestedAt: 'زمان درخواست',
    revision: 'revision',
    version: 'نسخه',
    noData: 'داده‌ای نیست',
    current: 'به‌روز',
    seconds: 'ثانیه',
    overallStatuses: {
      healthy: 'سالم',
      warning: 'نیازمند بررسی',
      critical: 'بحرانی',
      no_data: 'بدون داده',
    },
    healthStatuses: {
      healthy: 'سالم',
      degraded: 'اختلال',
      paused: 'متوقف',
      no_data: 'بدون داده',
    },
    freshnessStatuses: {
      fresh: 'تازه',
      stale: 'قدیمی',
      no_data: 'بدون داده',
    },
    jobStatuses: {
      queued: 'در صف',
      running: 'در حال اجرا',
      succeeded: 'موفق',
      failed: 'ناموفق',
      cancelled: 'لغوشده',
    },
  },
  en: {
    title: 'Market data health',
    description:
      'Read-only finalized-candle freshness, lag, backlog, and replay lifecycle without payloads, worker identity, or trading actions',
    overallStatus: 'Market data status',
    streams: 'Streams',
    healthyStreams: 'Healthy',
    degradedStreams: 'Needs review',
    staleStreams: 'Stale',
    pollingBacklog: 'Polling backlog',
    replayBacklog: 'Replay backlog',
    overdue: 'Overdue',
    finalization: 'Awaiting finalization',
    pending: 'Awaiting result',
    failed: 'Failed',
    streamHealth: 'Stream health',
    noStreams: 'No market-data streams are on the watchlist yet.',
    selectedProvider: 'Selected provider',
    latestFinalized: 'Latest finalized candle',
    latestPoll: 'Latest poll',
    lag: 'Lag',
    target: 'Freshness target',
    pollOverdue: 'Poll overdue',
    finalizationBacklog: 'Finalization backlog',
    providerRoutes: 'Provider routes',
    unavailable: 'Not recorded',
    recentReplays: 'Recent replays',
    recentReplaysDescription:
      'Durable job and revision state; failure detail is limited to a safe error code.',
    noReplays: 'No replay has been recorded yet.',
    reason: 'Reason',
    requestedAt: 'Requested at',
    revision: 'Revision',
    version: 'Version',
    noData: 'No data',
    current: 'Current',
    seconds: 'seconds',
    overallStatuses: {
      healthy: 'Healthy',
      warning: 'Needs review',
      critical: 'Critical',
      no_data: 'No data',
    },
    healthStatuses: {
      healthy: 'Healthy',
      degraded: 'Degraded',
      paused: 'Paused',
      no_data: 'No data',
    },
    freshnessStatuses: {
      fresh: 'Fresh',
      stale: 'Stale',
      no_data: 'No data',
    },
    jobStatuses: {
      queued: 'Queued',
      running: 'Running',
      succeeded: 'Succeeded',
      failed: 'Failed',
      cancelled: 'Cancelled',
    },
  },
};

export function getMarketDataHealthCopy(locale: PlatformLocale): MarketDataHealthCopy {
  return copies[locale];
}
