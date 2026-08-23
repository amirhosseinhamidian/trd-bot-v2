import type { DashboardLocale } from '@/components/dashboard/dashboard-copy';

export type DatasetDetailCopy = {
  back: string;
  eyebrow: string;
  metadata: {
    title: string;
    description: string;
    datasetId: string;
    schemaVersion: string;
    source: string;
    pair: string;
    marketType: string;
    timeframe: string;
    candleCount: string;
    dataPeriod: string;
    createdAt: string;
    checksum: string;
  };
  candles: {
    title: string;
    description: string;
    total: string;
    row: string;
    openTime: string;
    closeTime: string;
    open: string;
    high: string;
    low: string;
    close: string;
    volume: string;
    status: string;
    closed: string;
    openCandle: string;
    loading: string;
    errorTitle: string;
    errorDescription: string;
    retry: string;
  };
  pagination: {
    page: string;
    previous: string;
    next: string;
  };
  notFound: {
    title: string;
    description: string;
    back: string;
  };
};

const copies: Record<DashboardLocale, DatasetDetailCopy> = {
  fa: {
    back: 'بازگشت به مجموعه‌داده‌ها',
    eyebrow: 'Historical dataset snapshot',
    metadata: {
      title: 'مشخصات مجموعه‌داده',
      description: 'اطلاعات شناسایی و بازه زمانی Snapshot تاریخی ذخیره‌شده',
      datasetId: 'شناسه Dataset',
      schemaVersion: 'نسخه Schema',
      source: 'منبع',
      pair: 'جفت معاملاتی',
      marketType: 'نوع بازار',
      timeframe: 'تایم‌فریم',
      candleCount: 'تعداد کندل',
      dataPeriod: 'بازه داده',
      createdAt: 'زمان ایجاد',
      checksum: 'Checksum',
    },
    candles: {
      title: 'کندل‌های تاریخی',
      description: 'داده OHLCV ذخیره‌شده در این Snapshot برای پژوهش و بک‌تست',
      total: 'تعداد کل',
      row: 'ردیف',
      openTime: 'زمان بازشدن',
      closeTime: 'زمان بسته‌شدن',
      open: 'Open',
      high: 'High',
      low: 'Low',
      close: 'Close',
      volume: 'Volume',
      status: 'وضعیت',
      closed: 'بسته‌شده',
      openCandle: 'باز',
      loading: 'در حال دریافت کندل‌ها',
      errorTitle: 'دریافت کندل‌ها ناموفق بود',
      errorDescription: 'اتصال Backend را بررسی کرده و دوباره تلاش کنید.',
      retry: 'تلاش مجدد',
    },
    pagination: {
      page: 'صفحه',
      previous: 'قبلی',
      next: 'بعدی',
    },
    notFound: {
      title: 'مجموعه‌داده پیدا نشد',
      description: 'Dataset موردنظر وجود ندارد یا شناسه آن صحیح نیست.',
      back: 'بازگشت به مجموعه‌داده‌ها',
    },
  },
  en: {
    back: 'Back to datasets',
    eyebrow: 'Historical dataset snapshot',
    metadata: {
      title: 'Dataset metadata',
      description: 'Identity information and time range of the stored historical snapshot',
      datasetId: 'Dataset ID',
      schemaVersion: 'Schema version',
      source: 'Source',
      pair: 'Trading pair',
      marketType: 'Market type',
      timeframe: 'Timeframe',
      candleCount: 'Candle count',
      dataPeriod: 'Data period',
      createdAt: 'Created at',
      checksum: 'Checksum',
    },
    candles: {
      title: 'Historical candles',
      description: 'Stored OHLCV data used by this snapshot for research and backtesting',
      total: 'Total',
      row: 'Row',
      openTime: 'Open time',
      closeTime: 'Close time',
      open: 'Open',
      high: 'High',
      low: 'Low',
      close: 'Close',
      volume: 'Volume',
      status: 'Status',
      closed: 'Closed',
      openCandle: 'Open',
      loading: 'Loading candles',
      errorTitle: 'Unable to retrieve candles',
      errorDescription: 'Check the backend connection and try again.',
      retry: 'Try again',
    },
    pagination: {
      page: 'Page',
      previous: 'Previous',
      next: 'Next',
    },
    notFound: {
      title: 'Dataset not found',
      description: 'The requested dataset does not exist or its identifier is invalid.',
      back: 'Back to datasets',
    },
  },
};

export function getDatasetDetailCopy(locale: DashboardLocale): DatasetDetailCopy {
  return copies[locale];
}
