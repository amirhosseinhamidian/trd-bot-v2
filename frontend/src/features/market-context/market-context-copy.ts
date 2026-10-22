import type {
  MarketContextAssessmentStatus,
  MarketContextUnavailableReason,
  MarketTrendRegime,
  MarketVolatilityRegime,
} from '@/features/market-context/api/types';
import type { PlatformLocale } from '@/platform/i18n';

export type MarketContextCopy = {
  eyebrow: string;
  title: string;
  description: string;
  readOnly: string;
  total: string;
  disclaimer: string;
  emptyTitle: string;
  emptyDescription: string;
  errorTitle: string;
  errorDescription: string;
  retry: string;
  loading: string;
  available: string;
  unavailable: string;
  source: string;
  trend: string;
  volatility: string;
  confidence: string;
  status: string;
  asOf: string;
  expectedAsOf: string;
  assessedAt: string;
  expiresAt: string;
  expiresIn: string;
  boundaryLag: string;
  seconds: string;
  unavailableTitle: string;
  evidenceTitle: string;
  evidenceDescription: string;
  feature: string;
  timeframe: string;
  value: string;
  calculation: string;
  windows: string;
  lineageTitle: string;
  assessmentId: string;
  manifestId: string;
  snapshotId: string;
  inputChecksum: string;
  featureChecksum: string;
  snapshotChecksum: string;
  algorithmVersion: string;
  pagination: {
    label: string;
    previous: string;
    next: string;
  };
  assessmentStatuses: Record<MarketContextAssessmentStatus, string>;
  trends: Record<MarketTrendRegime, string>;
  volatilityLevels: Record<MarketVolatilityRegime, string>;
  unavailableReasons: Record<MarketContextUnavailableReason, string>;
  featureLabels: Record<string, string>;
};

const copies: Record<PlatformLocale, MarketContextCopy> = {
  fa: {
    eyebrow: 'هوشمندی بازار',
    title: 'زمینه بازار',
    description:
      'نمای چندبازه‌ای روند و نوسان با شواهد قطعی، نسخه‌دار و قابل بازتولید برای تصمیم‌گیری پژوهشی',
    readOnly: 'فقط‌خواندنی',
    total: 'کل جریان‌ها',
    disclaimer:
      'زمینه بازار سیگنال خرید یا فروش نیست. فقط assessmentهای هم‌تراز با مرز فعلی و دارای اعتبار زمانی، قابل‌مصرف علامت‌گذاری می‌شوند.',
    emptyTitle: 'هنوز زمینه بازاری ثبت نشده است',
    emptyDescription:
      'پس از اجرای موفق job ارزیابی، آخرین وضعیت هر منبع و جفت‌ارز اینجا ظاهر می‌شود.',
    errorTitle: 'دریافت زمینه بازار ناموفق بود',
    errorDescription: 'اتصال Backend را بررسی و دوباره تلاش کنید.',
    retry: 'تلاش مجدد',
    loading: 'در حال دریافت زمینه بازار',
    available: 'قابل‌مصرف',
    unavailable: 'غیرقابل‌مصرف',
    source: 'منبع',
    trend: 'روند',
    volatility: 'نوسان',
    confidence: 'اطمینان',
    status: 'وضعیت assessment',
    asOf: 'مرز assessment',
    expectedAsOf: 'مرز مورد انتظار',
    assessedAt: 'زمان ارزیابی',
    expiresAt: 'انقضا',
    expiresIn: 'زمان باقی‌مانده',
    boundaryLag: 'عقب‌ماندگی مرز',
    seconds: 'ثانیه',
    unavailableTitle: 'علت عدم امکان مصرف',
    evidenceTitle: 'شواهد ویژگی‌ها',
    evidenceDescription: 'مقادیر محاسبه‌شده و تعداد windowهای پشتیبان هر ویژگی',
    feature: 'ویژگی',
    timeframe: 'بازه زمانی',
    value: 'مقدار',
    calculation: 'نسخه محاسبه',
    windows: 'windowهای مرجع',
    lineageTitle: 'Lineage و نسخه‌ها',
    assessmentId: 'شناسه assessment',
    manifestId: 'شناسه manifest',
    snapshotId: 'شناسه snapshot',
    inputChecksum: 'checksum ورودی',
    featureChecksum: 'checksum feature-set',
    snapshotChecksum: 'checksum snapshot',
    algorithmVersion: 'نسخه الگوریتم',
    pagination: { label: 'صفحه زمینه بازار', previous: 'قبلی', next: 'بعدی' },
    assessmentStatuses: {
      ready: 'آماده',
      insufficient_data: 'داده ناکافی',
      stale: 'کهنه',
    },
    trends: {
      trending_up: 'صعودی',
      trending_down: 'نزولی',
      ranging: 'خنثی / رنج',
      undetermined: 'نامشخص',
    },
    volatilityLevels: {
      low: 'کم',
      normal: 'عادی',
      high: 'زیاد',
      undetermined: 'نامشخص',
    },
    unavailableReasons: {
      assessment_expired: 'اعتبار زمانی assessment پایان یافته است.',
      assessment_not_ready: 'assessment هنوز خروجی قطعی و آماده ندارد.',
      boundary_mismatch: 'مرز زمانی assessment با مرز فعلی هم‌تراز نیست.',
    },
    featureLabels: {
      realized_volatility_1d: 'نوسان تحقق‌یافته روزانه',
      realized_volatility_1h: 'نوسان تحقق‌یافته ساعتی',
      trend_slope_1d: 'شیب روند روزانه',
      trend_slope_1h: 'شیب روند ساعتی',
      trend_slope_4h: 'شیب روند چهارساعته',
    },
  },
  en: {
    eyebrow: 'Market intelligence',
    title: 'Market context',
    description:
      'Multi-timeframe trend and volatility with deterministic, versioned, reproducible evidence for research decisions.',
    readOnly: 'Read only',
    total: 'Total streams',
    disclaimer:
      'Market context is not a buy or sell signal. Only assessments aligned to the current boundary and within their validity window are marked consumable.',
    emptyTitle: 'No market context has been recorded',
    emptyDescription:
      'The latest state for each source and pair appears here after a successful evaluation job.',
    errorTitle: 'Unable to load market context',
    errorDescription: 'Check the backend connection and try again.',
    retry: 'Try again',
    loading: 'Loading market context',
    available: 'Consumable',
    unavailable: 'Unavailable',
    source: 'Source',
    trend: 'Trend',
    volatility: 'Volatility',
    confidence: 'Confidence',
    status: 'Assessment status',
    asOf: 'Assessment boundary',
    expectedAsOf: 'Expected boundary',
    assessedAt: 'Assessed at',
    expiresAt: 'Expires at',
    expiresIn: 'Time remaining',
    boundaryLag: 'Boundary lag',
    seconds: 'seconds',
    unavailableTitle: 'Why this context cannot be consumed',
    evidenceTitle: 'Feature evidence',
    evidenceDescription: 'Calculated values and supporting window counts for each feature.',
    feature: 'Feature',
    timeframe: 'Timeframe',
    value: 'Value',
    calculation: 'Calculation version',
    windows: 'Reference windows',
    lineageTitle: 'Lineage and versions',
    assessmentId: 'Assessment ID',
    manifestId: 'Manifest ID',
    snapshotId: 'Snapshot ID',
    inputChecksum: 'Input checksum',
    featureChecksum: 'Feature-set checksum',
    snapshotChecksum: 'Snapshot checksum',
    algorithmVersion: 'Algorithm version',
    pagination: { label: 'Market context page', previous: 'Previous', next: 'Next' },
    assessmentStatuses: {
      ready: 'Ready',
      insufficient_data: 'Insufficient data',
      stale: 'Stale',
    },
    trends: {
      trending_up: 'Trending up',
      trending_down: 'Trending down',
      ranging: 'Ranging',
      undetermined: 'Undetermined',
    },
    volatilityLevels: {
      low: 'Low',
      normal: 'Normal',
      high: 'High',
      undetermined: 'Undetermined',
    },
    unavailableReasons: {
      assessment_expired: 'The assessment validity window has ended.',
      assessment_not_ready: 'The assessment does not have a determinate ready outcome.',
      boundary_mismatch: 'The assessment boundary is not aligned with the current boundary.',
    },
    featureLabels: {
      realized_volatility_1d: 'Daily realized volatility',
      realized_volatility_1h: 'Hourly realized volatility',
      trend_slope_1d: 'Daily trend slope',
      trend_slope_1h: 'Hourly trend slope',
      trend_slope_4h: 'Four-hour trend slope',
    },
  },
};

export function getMarketContextCopy(locale: PlatformLocale): MarketContextCopy {
  return copies[locale];
}
