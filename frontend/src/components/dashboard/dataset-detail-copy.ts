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
  provenance: {
    title: string;
    description: string;
    connectionId: string;
    providerId: string;
    importId: string;
    requestedRange: string;
    kinds: {
      legacy: string;
      generated: string;
      manual_upload: string;
      market_data_import: string;
    };
    kindDescriptions: {
      legacy: string;
      generated: string;
      manual_upload: string;
      market_data_import: string;
    };
  };
  quality: {
    title: string;
    description: string;
    statuses: {
      passed: string;
      issues: string;
      notRecorded: string;
    };
    candlesChecked: string;
    issueCount: string;
    passedDescription: string;
    notRecordedDescription: string;
    issueTimestamp: string;
  };
  versions: {
    title: string;
    description: string;
    load: string;
    reload: string;
    refresh: string;
    refreshing: string;
    loading: string;
    emptyTitle: string;
    emptyDescription: string;
    errorTitle: string;
    errorDescription: string;
    refreshErrorTitle: string;
    refreshErrorDescription: string;
    retry: string;
    version: string;
    initialImport: string;
    refreshOperation: string;
    succeeded: string;
    failed: string;
    contentChanged: string;
    contentUnchanged: string;
    currentSnapshot: string;
    openSnapshot: string;
    openNewSnapshot: string;
    completedAt: string;
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
    scrollLabel: string;
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
    provenance: {
      title: 'منشأ مجموعه‌داده',
      description: 'اطلاعات ثابت درباره نحوه ایجاد این Snapshot',
      connectionId: 'شناسه Connection',
      providerId: 'Provider',
      importId: 'شناسه Import',
      requestedRange: 'بازه درخواستی',
      kinds: {
        legacy: 'قدیمی / ثبت‌نشده',
        generated: 'تولید داخلی',
        manual_upload: 'ورودی دستی',
        market_data_import: 'ورودی Market Data',
      },
      kindDescriptions: {
        legacy: 'این Dataset پیش از ثبت metadata منشأ ساخته شده است.',
        generated: 'این Dataset توسط یک جریان داخلی پژوهشی ساخته شده است.',
        manual_upload: 'داده OHLCV این Dataset به‌صورت دستی به API پژوهش ارسال شده است.',
        market_data_import: 'این Dataset از یک Connection خواندنی Market Data وارد شده است.',
      },
    },
    quality: {
      title: 'کیفیت داده',
      description: 'نتیجه بررسی کیفیت ثبت‌شده هنگام ایجاد Snapshot',
      statuses: {
        passed: 'تأییدشده',
        issues: 'نیازمند بررسی',
        notRecorded: 'ثبت‌نشده',
      },
      candlesChecked: 'کندل‌های بررسی‌شده',
      issueCount: 'تعداد مسائل',
      passedDescription: 'در زمان ایجاد Snapshot هیچ مسئله کیفیتی ثبت نشده است.',
      notRecordedDescription: 'برای این Dataset قدیمی گزارش کیفیت ذخیره نشده است.',
      issueTimestamp: 'زمان مسئله',
    },
    versions: {
      title: 'تاریخچه نسخه‌ها',
      description: 'زنجیره تغییرناپذیر Import و Refresh برای این Dataset',
      load: 'نمایش تاریخچه نسخه‌ها',
      reload: 'به‌روزرسانی تاریخچه',
      refresh: 'Refresh آخرین نسخه',
      refreshing: 'در حال Refresh',
      loading: 'در حال دریافت تاریخچه نسخه‌ها',
      emptyTitle: 'تاریخچه نسخه‌ای وجود ندارد',
      emptyDescription: 'برای این Dataset هنوز lineage قابل نمایش ثبت نشده است.',
      errorTitle: 'دریافت تاریخچه نسخه‌ها ناموفق بود',
      errorDescription: 'اتصال Backend را بررسی کرده و دوباره تلاش کنید.',
      refreshErrorTitle: 'Refresh مجموعه‌داده ناموفق بود',
      refreshErrorDescription:
        'تلاش ناموفق در تاریخچه ثبت می‌شود؛ تاریخچه را دوباره بارگذاری کرده و وضعیت Connection را بررسی کنید.',
      retry: 'تلاش مجدد',
      version: 'نسخه',
      initialImport: 'Import اولیه',
      refreshOperation: 'Refresh',
      succeeded: 'موفق',
      failed: 'ناموفق',
      contentChanged: 'محتوا تغییر کرد',
      contentUnchanged: 'بدون تغییر محتوا',
      currentSnapshot: 'Snapshot فعلی',
      openSnapshot: 'مشاهده Snapshot',
      openNewSnapshot: 'مشاهده Snapshot جدید',
      completedAt: 'زمان تکمیل',
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
      scrollLabel: 'جدول کندل‌های تاریخی؛ برای مشاهده همه ستون‌ها به‌صورت افقی پیمایش کنید',
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
    provenance: {
      title: 'Dataset provenance',
      description: 'Immutable metadata describing how this snapshot was created',
      connectionId: 'Connection ID',
      providerId: 'Provider',
      importId: 'Import ID',
      requestedRange: 'Requested range',
      kinds: {
        legacy: 'Legacy / not recorded',
        generated: 'Internally generated',
        manual_upload: 'Manual upload',
        market_data_import: 'Market data import',
      },
      kindDescriptions: {
        legacy: 'This dataset predates immutable provenance metadata.',
        generated: 'This dataset was created by an internal research workflow.',
        manual_upload:
          'This dataset was created from OHLCV submitted manually to the research API.',
        market_data_import:
          'This dataset was imported from a configured read-only market-data connection.',
      },
    },
    quality: {
      title: 'Data quality',
      description: 'Quality-check evidence recorded when this snapshot was created',
      statuses: {
        passed: 'Passed',
        issues: 'Review required',
        notRecorded: 'Not recorded',
      },
      candlesChecked: 'Candles checked',
      issueCount: 'Issues',
      passedDescription: 'No data-quality issues were recorded when this snapshot was created.',
      notRecordedDescription: 'No persisted quality report is available for this legacy dataset.',
      issueTimestamp: 'Issue timestamp',
    },
    versions: {
      title: 'Version history',
      description: 'Immutable import and refresh lineage for this dataset',
      load: 'Load version history',
      reload: 'Reload history',
      refresh: 'Refresh latest version',
      refreshing: 'Refreshing dataset',
      loading: 'Loading version history',
      emptyTitle: 'No version history',
      emptyDescription: 'No displayable version lineage has been recorded for this dataset.',
      errorTitle: 'Unable to load version history',
      errorDescription: 'Check the backend connection and try again.',
      refreshErrorTitle: 'Dataset refresh failed',
      refreshErrorDescription:
        'The failed attempt remains in immutable history. Reload the history and check the connection state.',
      retry: 'Try again',
      version: 'Version',
      initialImport: 'Initial import',
      refreshOperation: 'Refresh',
      succeeded: 'Succeeded',
      failed: 'Failed',
      contentChanged: 'Content changed',
      contentUnchanged: 'No content change',
      currentSnapshot: 'Current snapshot',
      openSnapshot: 'Open snapshot',
      openNewSnapshot: 'Open new snapshot',
      completedAt: 'Completed',
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
      scrollLabel: 'Historical candles table; scroll horizontally to view all columns',
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
