import type { DashboardLocale } from '@/components/dashboard/dashboard-copy';
import type { MarketDataImportStatus } from '@/lib/api/types';

export type ImportHistoryCopy = {
  title: string;
  description: string;
  show: string;
  hide: string;
  loading: string;
  errorTitle: string;
  errorDescription: string;
  retry: string;
  emptyTitle: string;
  emptyDescription: string;
  all: string;
  filters: Record<MarketDataImportStatus, string>;
  statuses: Record<MarketDataImportStatus, string>;
  datasetName: string;
  pair: string;
  timeframe: string;
  requestedRange: string;
  completedAt: string;
  candles: string;
  importId: string;
  datasetId: string;
  errorCode: string;
  viewDataset: string;
  page: string;
  previous: string;
  next: string;
};

const copies: Record<DashboardLocale, ImportHistoryCopy> = {
  fa: {
    title: 'تاریخچه ورود داده',
    description: 'تلاش‌های واقعی ورود داده تاریخی برای این Connection را مشاهده کنید.',
    show: 'نمایش تاریخچه ورود',
    hide: 'بستن تاریخچه ورود',
    loading: 'در حال دریافت تاریخچه ورود داده',
    errorTitle: 'دریافت تاریخچه ناموفق بود',
    errorDescription: 'تاریخچه ورود داده از Backend دریافت نشد. دوباره تلاش کنید.',
    retry: 'تلاش مجدد',
    emptyTitle: 'هنوز ورودی ثبت نشده است',
    emptyDescription: 'پس از اولین تلاش واقعی برای ساخت Dataset، نتیجه اینجا ثبت می‌شود.',
    all: 'همه',
    filters: {
      succeeded: 'موفق',
      failed: 'ناموفق',
    },
    statuses: {
      succeeded: 'موفق',
      failed: 'ناموفق',
    },
    datasetName: 'نام Dataset',
    pair: 'جفت بازار',
    timeframe: 'تایم‌فریم',
    requestedRange: 'بازه درخواستی',
    completedAt: 'زمان پایان',
    candles: 'کندل‌ها',
    importId: 'شناسه Import',
    datasetId: 'شناسه Dataset',
    errorCode: 'کد خطا',
    viewDataset: 'مشاهده Dataset',
    page: 'صفحه',
    previous: 'قبلی',
    next: 'بعدی',
  },
  en: {
    title: 'Import history',
    description: 'Review actual historical-data import attempts for this connection.',
    show: 'Show import history',
    hide: 'Hide import history',
    loading: 'Loading import history',
    errorTitle: 'Unable to load import history',
    errorDescription: 'Import history could not be retrieved from the backend. Try again.',
    retry: 'Try again',
    emptyTitle: 'No imports recorded yet',
    emptyDescription: 'The result of the first real dataset import attempt will appear here.',
    all: 'All',
    filters: {
      succeeded: 'Succeeded',
      failed: 'Failed',
    },
    statuses: {
      succeeded: 'Succeeded',
      failed: 'Failed',
    },
    datasetName: 'Dataset name',
    pair: 'Market pair',
    timeframe: 'Timeframe',
    requestedRange: 'Requested range',
    completedAt: 'Completed at',
    candles: 'Candles',
    importId: 'Import ID',
    datasetId: 'Dataset ID',
    errorCode: 'Error code',
    viewDataset: 'View dataset',
    page: 'Page',
    previous: 'Previous',
    next: 'Next',
  },
};

export function getImportHistoryCopy(locale: DashboardLocale): ImportHistoryCopy {
  return copies[locale];
}
