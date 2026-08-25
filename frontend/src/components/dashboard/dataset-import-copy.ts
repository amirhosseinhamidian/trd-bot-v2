import type { DashboardLocale } from '@/components/dashboard/dashboard-copy';
import type { DatasetCsvErrorCode } from '@/lib/datasets/csv';

export type DatasetImportCopy = {
  title: string;
  description: string;
  historicalOnly: string;
  name: string;
  namePlaceholder: string;
  source: string;
  sourcePlaceholder: string;
  baseAsset: string;
  quoteAsset: string;
  timeframe: string;
  csvFile: string;
  csvHint: string;
  downloadTemplate: string;
  importButton: string;
  importing: string;
  previewTitle: string;
  previewFile: string;
  previewCandles: string;
  previewStart: string;
  previewEnd: string;
  successTitle: string;
  successDescription: string;
  viewDataset: string;
  row: string;
  timeframes: Record<'15m' | '1h' | '4h' | '1d', string>;
  errors: {
    required: string;
    invalidAsset: string;
    identicalAssets: string;
    fileRequired: string;
    fileTooLarge: string;
    readFailed: string;
    backendValidation: string;
    submitFailed: string;
  };
  csvErrors: Record<DatasetCsvErrorCode, string>;
};

const copies: Record<DashboardLocale, DatasetImportCopy> = {
  fa: {
    title: 'Import مجموعه‌داده تاریخی',
    description:
      'فایل CSV شامل کندل‌های بسته‌شده OHLCV را بررسی و به‌صورت Snapshot تغییرناپذیر ذخیره کنید.',
    historicalOnly: 'فقط داده تاریخی',
    name: 'نام مجموعه‌داده',
    namePlaceholder: 'مثلاً BTC/USDT Historical 1H',
    source: 'منبع داده',
    sourcePlaceholder: 'مثلاً manual-import',
    baseAsset: 'دارایی پایه',
    quoteAsset: 'دارایی مقابل',
    timeframe: 'تایم‌فریم',
    csvFile: 'فایل CSV',
    csvHint: 'حداکثر حجم فایل ۱۰ مگابایت است.',
    downloadTemplate: 'دریافت نمونه CSV',
    importButton: 'Import مجموعه‌داده',
    importing: 'در حال Import',
    previewTitle: 'پیش‌نمایش فایل',
    previewFile: 'نام فایل',
    previewCandles: 'تعداد کندل',
    previewStart: 'شروع داده',
    previewEnd: 'پایان داده',
    successTitle: 'مجموعه‌داده ذخیره شد',
    successDescription: 'Snapshot تاریخی با موفقیت اعتبارسنجی و ذخیره شد.',
    viewDataset: 'مشاهده مجموعه‌داده',
    row: 'ردیف',
    timeframes: {
      '15m': '۱۵ دقیقه',
      '1h': '۱ ساعت',
      '4h': '۴ ساعت',
      '1d': '۱ روز',
    },
    errors: {
      required: 'تکمیل این فیلد الزامی است.',
      invalidAsset: 'نماد دارایی باید بین ۲ تا ۱۵ حرف یا عدد باشد.',
      identicalAssets: 'دارایی پایه و مقابل نمی‌توانند یکسان باشند.',
      fileRequired: 'ابتدا یک فایل CSV انتخاب کنید.',
      fileTooLarge: 'حجم فایل CSV نباید بیشتر از ۱۰ مگابایت باشد.',
      readFailed: 'خواندن فایل CSV ناموفق بود.',
      backendValidation: 'Backend کیفیت داده تاریخی را تأیید نکرد.',
      submitFailed: 'ذخیره مجموعه‌داده ناموفق بود. اتصال Backend را بررسی کنید.',
    },
    csvErrors: {
      malformed_csv: 'ساختار فایل CSV معتبر نیست.',
      empty_file: 'فایل CSV خالی است.',
      missing_header: 'یکی از ستون‌های ضروری CSV وجود ندارد.',
      duplicate_header: 'یکی از نام‌های ستون‌ها تکراری است.',
      unknown_header: 'فایل CSV دارای ستون پشتیبانی‌نشده است.',
      empty_dataset: 'فایل CSV هیچ کندلی ندارد.',
      invalid_column_count: 'تعداد ستون‌های این ردیف صحیح نیست.',
      empty_value: 'یکی از مقادیر ضروری خالی است.',
      invalid_timestamp: 'زمان کندل معتبر نیست یا timezone ندارد.',
      invalid_number: 'یکی از مقادیر عددی معتبر نیست.',
      invalid_ohlc: 'رابطه قیمت‌های OHLC معتبر نیست.',
      open_candle: 'فقط کندل‌های بسته‌شده قابل Import هستند.',
      duplicate_timestamp: 'زمان تکراری در کندل‌ها پیدا شد.',
      out_of_order: 'کندل‌ها باید از قدیمی به جدید مرتب باشند.',
      missing_candle: 'یک یا چند کندل در بازه زمانی وجود ندارد.',
      unexpected_interval: 'فاصله کندل‌ها با تایم‌فریم انتخاب‌شده مطابقت ندارد.',
    },
  },

  en: {
    title: 'Import historical dataset',
    description:
      'Validate a CSV containing closed OHLCV candles and store it as an immutable snapshot.',
    historicalOnly: 'Historical data only',
    name: 'Dataset name',
    namePlaceholder: 'For example, BTC/USDT Historical 1H',
    source: 'Data source',
    sourcePlaceholder: 'For example, manual-import',
    baseAsset: 'Base asset',
    quoteAsset: 'Quote asset',
    timeframe: 'Timeframe',
    csvFile: 'CSV file',
    csvHint: 'The maximum supported file size is 10 MB.',
    downloadTemplate: 'Download CSV template',
    importButton: 'Import dataset',
    importing: 'Importing',
    previewTitle: 'File preview',
    previewFile: 'File name',
    previewCandles: 'Candles',
    previewStart: 'Data start',
    previewEnd: 'Data end',
    successTitle: 'Dataset stored',
    successDescription: 'The historical snapshot was successfully validated and stored.',
    viewDataset: 'View dataset',
    row: 'Row',
    timeframes: {
      '15m': '15 minutes',
      '1h': '1 hour',
      '4h': '4 hours',
      '1d': '1 day',
    },
    errors: {
      required: 'This field is required.',
      invalidAsset: 'The asset symbol must contain 2 to 15 letters or numbers.',
      identicalAssets: 'The base and quote assets must be different.',
      fileRequired: 'Select a CSV file first.',
      fileTooLarge: 'The CSV file cannot be larger than 10 MB.',
      readFailed: 'The CSV file could not be read.',
      backendValidation: 'The backend rejected the historical data quality.',
      submitFailed: 'The dataset could not be stored. Check the backend connection.',
    },
    csvErrors: {
      malformed_csv: 'The CSV structure is invalid.',
      empty_file: 'The CSV file is empty.',
      missing_header: 'A required CSV column is missing.',
      duplicate_header: 'A CSV column name is duplicated.',
      unknown_header: 'The CSV contains an unsupported column.',
      empty_dataset: 'The CSV does not contain any candles.',
      invalid_column_count: 'This row has an invalid number of columns.',
      empty_value: 'A required value is empty.',
      invalid_timestamp: 'A candle timestamp is invalid or has no timezone.',
      invalid_number: 'A numeric value is invalid.',
      invalid_ohlc: 'The OHLC price relationship is invalid.',
      open_candle: 'Only closed candles can be imported.',
      duplicate_timestamp: 'A duplicate candle timestamp was found.',
      out_of_order: 'Candles must be sorted chronologically.',
      missing_candle: 'One or more candles are missing from the time series.',
      unexpected_interval: 'The candle interval does not match the selected timeframe.',
    },
  },
};

export function getDatasetImportCopy(locale: DashboardLocale): DatasetImportCopy {
  return copies[locale];
}
