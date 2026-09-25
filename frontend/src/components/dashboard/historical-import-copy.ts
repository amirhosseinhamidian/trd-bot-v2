import type { DashboardLocale } from '@/components/dashboard/dashboard-copy';
import type { MarketDataQualityIssueCode } from '@/lib/api/types';

export type HistoricalImportCopy = {
  title: string;
  description: string;
  datasetName: string;
  datasetNamePlaceholder: string;
  baseAsset: string;
  quoteAsset: string;
  timeframe: string;
  marketType: string;
  startTime: string;
  endTime: string;
  preview: string;
  previewing: string;
  importDataset: string;
  importing: string;
  previewTitle: string;
  ready: string;
  notReady: string;
  candles: string;
  requestedRange: string;
  availableRange: string;
  noCoverage: string;
  coverageTitle: string;
  expectedCandles: string;
  receivedCandles: string;
  missingCandles: string;
  coveragePercent: string;
  previewChecksum: string;
  qualityTitle: string;
  scoreTitle: string;
  scorePercent: string;
  coverageComponent: string;
  integrityComponent: string;
  scoreVersion: string;
  policyVersion: string;
  policyPassed: string;
  policyFailed: string;
  qualityPassed: string;
  qualityIssues: string;
  importedTitle: string;
  viewDataset: string;
  invalidRange: string;
  requestError: string;
  previewMismatchError: string;
  providerMetadataMissing: string;
  directAccessNotice: string;
  vpnAccessNotice: string;
  recentWindowNotice: string;
  recentWindowError: string;
  issueLabels: Record<MarketDataQualityIssueCode, string>;
};

const copies: Record<DashboardLocale, HistoricalImportCopy> = {
  fa: {
    title: 'ساخت Dataset از داده تاریخی',
    description:
      'یک بازه تاریخی عمومی را Preview کنید، گزارش کیفیت را ببینید و فقط در صورت معتبر بودن داده Dataset immutable بسازید.',
    datasetName: 'نام Dataset',
    datasetNamePlaceholder: 'مثلاً BTC / USDT — August 2026',
    baseAsset: 'دارایی پایه',
    quoteAsset: 'دارایی مظنه',
    timeframe: 'تایم‌فریم',
    marketType: 'نوع بازار',
    startTime: 'شروع بازه',
    endTime: 'پایان بازه',
    preview: 'Preview داده',
    previewing: 'در حال دریافت Preview',
    importDataset: 'ساخت Dataset',
    importing: 'در حال ساخت Dataset',
    previewTitle: 'نتیجه Preview',
    ready: 'آماده Import',
    notReady: 'نیازمند اصلاح کیفیت',
    candles: 'تعداد کندل',
    requestedRange: 'بازه درخواستی',
    availableRange: 'پوشش داده دریافت‌شده',
    noCoverage: 'هیچ کندل معتبری در این بازه دریافت نشد.',
    coverageTitle: 'پوشش بازه',
    expectedCandles: 'کندل مورد انتظار',
    receivedCandles: 'کندل دریافت‌شده',
    missingCandles: 'کندل مفقود',
    coveragePercent: 'درصد پوشش',
    previewChecksum: 'Checksum پیش‌نمایش',
    qualityTitle: 'گزارش کیفیت',
    scoreTitle: 'امتیاز کیفیت نسخه‌دار',
    scorePercent: 'امتیاز نهایی',
    coverageComponent: 'مولفه پوشش',
    integrityComponent: 'مولفه یکپارچگی',
    scoreVersion: 'نسخه فرمول',
    policyVersion: 'نسخه سیاست پذیرش',
    policyPassed: 'پذیرفته‌شده',
    policyFailed: 'ردشده',
    qualityPassed: 'هیچ مشکل کیفیتی پیدا نشد.',
    qualityIssues: 'مشکلات کیفیت',
    importedTitle: 'Dataset ساخته شد',
    viewDataset: 'مشاهده Dataset',
    invalidRange: 'زمان پایان باید بعد از زمان شروع باشد.',
    requestError: 'دریافت داده یا ساخت Dataset ناموفق بود. ورودی‌ها و وضعیت Backend را بررسی کنید.',
    previewMismatchError:
      'داده Provider بعد از Preview تغییر کرده است. دوباره Preview بگیرید و نتیجه جدید را بررسی کنید.',
    providerMetadataMissing: 'Metadata مربوط به Provider این اتصال در دسترس نیست.',
    directAccessNotice: 'این Provider برای مسیر اتصال مستقیم انتخاب شده است.',
    vpnAccessNotice:
      'این Provider در محیط فعلی به VPN نیاز دارد. پیش از Preview از فعال بودن مسیر VPN مطمئن شوید.',
    recentWindowNotice: 'این Provider فقط {count} کندل بسته اخیر را ارائه می‌کند.',
    recentWindowError:
      'زمان شروع خارج از پنجره {count} کندل اخیر این Provider است. بازه جدیدتری انتخاب کنید.',
    issueLabels: {
      empty_data: 'داده خالی',
      mixed_series: 'سری داده ترکیبی',
      duplicate_timestamp: 'زمان تکراری',
      out_of_order: 'ترتیب زمانی نامعتبر',
      missing_candle: 'کندل گمشده',
      open_candle: 'کندل بسته‌نشده',
      incomplete_start: 'ابتدای بازه ناقص',
      incomplete_end: 'انتهای بازه ناقص',
      outside_requested_range: 'خارج از بازه درخواستی',
      unaligned_candle: 'مرز زمانی نامعتبر',
    },
  },
  en: {
    title: 'Build dataset from historical data',
    description:
      'Preview a public historical range, review its quality report, and create an immutable dataset only when the normalized data is valid.',
    datasetName: 'Dataset name',
    datasetNamePlaceholder: 'For example, BTC / USDT — August 2026',
    baseAsset: 'Base asset',
    quoteAsset: 'Quote asset',
    timeframe: 'Timeframe',
    marketType: 'Market type',
    startTime: 'Range start',
    endTime: 'Range end',
    preview: 'Preview data',
    previewing: 'Loading preview',
    importDataset: 'Create dataset',
    importing: 'Creating dataset',
    previewTitle: 'Preview result',
    ready: 'Ready to import',
    notReady: 'Quality review required',
    candles: 'Candles',
    requestedRange: 'Requested range',
    availableRange: 'Received data coverage',
    noCoverage: 'No valid candles were received for this range.',
    coverageTitle: 'Range coverage',
    expectedCandles: 'Expected candles',
    receivedCandles: 'Received candles',
    missingCandles: 'Missing candles',
    coveragePercent: 'Coverage',
    previewChecksum: 'Preview checksum',
    qualityTitle: 'Quality report',
    scoreTitle: 'Versioned quality score',
    scorePercent: 'Final score',
    coverageComponent: 'Coverage component',
    integrityComponent: 'Integrity component',
    scoreVersion: 'Formula version',
    policyVersion: 'Acceptance policy',
    policyPassed: 'Accepted',
    policyFailed: 'Rejected',
    qualityPassed: 'No quality issues were detected.',
    qualityIssues: 'Quality issues',
    importedTitle: 'Dataset created',
    viewDataset: 'View dataset',
    invalidRange: 'Range end must be after range start.',
    requestError:
      'Unable to fetch data or create the dataset. Check the inputs and backend status.',
    previewMismatchError:
      'Provider data changed after preview. Run preview again and review the new result.',
    providerMetadataMissing: 'Provider metadata for this connection is unavailable.',
    directAccessNotice: 'This provider is selected for the direct network route.',
    vpnAccessNotice:
      'This provider requires VPN in the current environment. Confirm the VPN route before previewing data.',
    recentWindowNotice: 'This provider exposes only the latest {count} closed candles.',
    recentWindowError:
      'The start time is outside this provider’s {count}-candle recent window. Choose a newer range.',
    issueLabels: {
      empty_data: 'Empty data',
      mixed_series: 'Mixed series',
      duplicate_timestamp: 'Duplicate timestamp',
      out_of_order: 'Out of order',
      missing_candle: 'Missing candle',
      open_candle: 'Open candle',
      incomplete_start: 'Incomplete range start',
      incomplete_end: 'Incomplete range end',
      outside_requested_range: 'Outside requested range',
      unaligned_candle: 'Unaligned candle',
    },
  },
};

export function getHistoricalImportCopy(locale: DashboardLocale): HistoricalImportCopy {
  return copies[locale];
}
