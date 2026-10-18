import type { AlertInboxStatus, AlertSeverity } from '@/features/alerts/api/types';
import type {
  MarketTrendRegime,
  MarketVolatilityRegime,
} from '@/features/market-context/api/types';
import type { PlatformLocale } from '@/platform/i18n';

export type AlertCenterCopy = {
  eyebrow: string;
  title: string;
  description: string;
  inAppOnly: string;
  disclaimer: string;
  total: string;
  statuses: Record<AlertInboxStatus, string>;
  severities: Record<AlertSeverity, string>;
  trends: Record<MarketTrendRegime, string>;
  volatility: Record<MarketVolatilityRegime, string>;
  allStatuses: string;
  allSeverities: string;
  statusFilter: string;
  severityFilter: string;
  pair: string;
  source: string;
  trend: string;
  volatilityLabel: string;
  confidence: string;
  createdAt: string;
  expiresAt: string;
  snoozedUntil: string;
  acknowledgedAt: string;
  acknowledgedBy: string;
  acknowledge: string;
  acknowledging: string;
  snooze: string;
  snoozing: string;
  snoozeDuration: string;
  actionError: string;
  loading: string;
  emptyTitle: string;
  emptyDescription: string;
  errorTitle: string;
  errorDescription: string;
  retry: string;
  technicalDetails: string;
  technicalDescription: string;
  alertId: string;
  rule: string;
  assessment: string;
  checksum: string;
  pagination: { label: string; previous: string; next: string };
  durations: Record<string, string>;
};

const copies: Record<PlatformLocale, AlertCenterCopy> = {
  fa: {
    eyebrow: 'هوشمندی تصمیم',
    title: 'مرکز هشدارها',
    description: 'هشدارهای درون‌برنامه‌ای مبتنی بر زمینه بازار، همراه با وضعیت و lineage کامل',
    inAppOnly: 'فقط درون‌برنامه‌ای',
    disclaimer:
      'این هشدارها سیگنال معامله یا سفارش واقعی نیستند. تأیید و تعویق فقط وضعیت Inbox را تغییر می‌دهد.',
    total: 'کل هشدارها',
    statuses: {
      active: 'فعال',
      snoozed: 'به‌تعویق‌افتاده',
      acknowledged: 'تأییدشده',
      expired: 'منقضی',
    },
    severities: { info: 'اطلاعاتی', warning: 'هشدار', critical: 'بحرانی' },
    trends: {
      trending_up: 'صعودی',
      trending_down: 'نزولی',
      ranging: 'خنثی / رنج',
      undetermined: 'نامشخص',
    },
    volatility: { low: 'کم', normal: 'عادی', high: 'زیاد', undetermined: 'نامشخص' },
    allStatuses: 'همه وضعیت‌ها',
    allSeverities: 'همه شدت‌ها',
    statusFilter: 'فیلتر وضعیت',
    severityFilter: 'فیلتر شدت',
    pair: 'جفت‌ارز',
    source: 'منبع',
    trend: 'روند',
    volatilityLabel: 'نوسان',
    confidence: 'اطمینان',
    createdAt: 'ایجاد',
    expiresAt: 'انقضا',
    snoozedUntil: 'تعویق تا',
    acknowledgedAt: 'زمان تأیید',
    acknowledgedBy: 'تأییدکننده',
    acknowledge: 'تأیید هشدار',
    acknowledging: 'در حال تأیید',
    snooze: 'تعویق',
    snoozing: 'در حال تعویق',
    snoozeDuration: 'مدت تعویق',
    actionError: 'ثبت اکشن ناموفق بود. وضعیت هشدار را تازه‌سازی و دوباره تلاش کنید.',
    loading: 'در حال دریافت هشدارها',
    emptyTitle: 'هشداری با این فیلتر وجود ندارد',
    emptyDescription: 'با تغییر فیلترها یا پس از ارزیابی بعدی دوباره بررسی کنید.',
    errorTitle: 'دریافت مرکز هشدارها ناموفق بود',
    errorDescription: 'اتصال Backend را بررسی و دوباره تلاش کنید.',
    retry: 'تلاش مجدد',
    technicalDetails: 'Lineage و جزئیات فنی',
    technicalDescription: 'شناسه‌های alert، rule و assessment برای بازبینی و audit',
    alertId: 'شناسه هشدار',
    rule: 'نسخه Rule',
    assessment: 'assessment منبع',
    checksum: 'checksum هشدار',
    pagination: { label: 'صفحه هشدارها', previous: 'قبلی', next: 'بعدی' },
    durations: { '900': '۱۵ دقیقه', '3600': '۱ ساعت', '14400': '۴ ساعت', '86400': '۲۴ ساعت' },
  },
  en: {
    eyebrow: 'Decision intelligence',
    title: 'Alert Center',
    description: 'In-app market-context alerts with durable status and complete lineage.',
    inAppOnly: 'In-app only',
    disclaimer:
      'These alerts are not trade signals or live orders. Acknowledge and snooze only change Inbox state.',
    total: 'Total alerts',
    statuses: {
      active: 'Active',
      snoozed: 'Snoozed',
      acknowledged: 'Acknowledged',
      expired: 'Expired',
    },
    severities: { info: 'Info', warning: 'Warning', critical: 'Critical' },
    trends: {
      trending_up: 'Trending up',
      trending_down: 'Trending down',
      ranging: 'Ranging',
      undetermined: 'Undetermined',
    },
    volatility: { low: 'Low', normal: 'Normal', high: 'High', undetermined: 'Undetermined' },
    allStatuses: 'All statuses',
    allSeverities: 'All severities',
    statusFilter: 'Status filter',
    severityFilter: 'Severity filter',
    pair: 'Pair',
    source: 'Source',
    trend: 'Trend',
    volatilityLabel: 'Volatility',
    confidence: 'Confidence',
    createdAt: 'Created',
    expiresAt: 'Expires',
    snoozedUntil: 'Snoozed until',
    acknowledgedAt: 'Acknowledged at',
    acknowledgedBy: 'Acknowledged by',
    acknowledge: 'Acknowledge',
    acknowledging: 'Acknowledging',
    snooze: 'Snooze',
    snoozing: 'Snoozing',
    snoozeDuration: 'Snooze duration',
    actionError: 'The action could not be saved. Refresh the alert state and try again.',
    loading: 'Loading alerts',
    emptyTitle: 'No alerts match these filters',
    emptyDescription: 'Change the filters or check again after the next evaluation.',
    errorTitle: 'Unable to load Alert Center',
    errorDescription: 'Check the backend connection and try again.',
    retry: 'Try again',
    technicalDetails: 'Lineage and technical details',
    technicalDescription: 'Alert, rule, and assessment identifiers for review and audit.',
    alertId: 'Alert ID',
    rule: 'Rule version',
    assessment: 'Source assessment',
    checksum: 'Alert checksum',
    pagination: { label: 'Alerts page', previous: 'Previous', next: 'Next' },
    durations: { '900': '15 minutes', '3600': '1 hour', '14400': '4 hours', '86400': '24 hours' },
  },
};

export function getAlertCenterCopy(locale: PlatformLocale): AlertCenterCopy {
  return copies[locale];
}
