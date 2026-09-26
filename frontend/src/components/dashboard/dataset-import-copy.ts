import type { DashboardLocale } from '@/components/dashboard/dashboard-copy';
import type { DatasetFileField } from '@/lib/api/types';

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
  datasetFile: string;
  fileHint: string;
  downloadTemplate: string;
  inspecting: string;
  mappingTitle: string;
  mappingDescription: string;
  optional: string;
  derivedCloseTime: string;
  defaultClosed: string;
  fields: Record<DatasetFileField, string>;
  previewButton: string;
  previewing: string;
  importButton: string;
  importing: string;
  previewTitle: string;
  previewFile: string;
  previewFormat: string;
  previewRows: string;
  previewCandles: string;
  previewStart: string;
  previewEnd: string;
  qualityScore: string;
  qualityPassed: string;
  qualityRejected: string;
  checksum: string;
  successTitle: string;
  successDescription: string;
  viewDataset: string;
  timeframes: Record<'15m' | '1h' | '4h' | '1d', string>;
  errors: {
    required: string;
    invalidAsset: string;
    identicalAssets: string;
    fileRequired: string;
    fileTooLarge: string;
    unsupportedFile: string;
    inspectionFailed: string;
    mappingRequired: string;
    duplicateMapping: string;
    previewFailed: string;
    qualityRejected: string;
    previewExpired: string;
    submitFailed: string;
  };
};

const fields: Record<DashboardLocale, Record<DatasetFileField, string>> = {
  fa: {
    open_time: 'زمان بازشدن',
    close_time: 'زمان بسته‌شدن',
    open_price: 'قیمت Open',
    high_price: 'قیمت High',
    low_price: 'قیمت Low',
    close_price: 'قیمت Close',
    volume: 'حجم',
    is_closed: 'وضعیت بسته‌شدن',
  },
  en: {
    open_time: 'Open time',
    close_time: 'Close time',
    open_price: 'Open price',
    high_price: 'High price',
    low_price: 'Low price',
    close_price: 'Close price',
    volume: 'Volume',
    is_closed: 'Closed state',
  },
};

const copies: Record<DashboardLocale, DatasetImportCopy> = {
  fa: {
    title: 'Import مجموعه‌داده تاریخی',
    description:
      'فایل CSV، JSON یا Parquet را روی Backend بررسی کنید، ستون‌ها را نگاشت دهید و فقط Preview تأییدشده را ذخیره کنید.',
    historicalOnly: 'فقط داده تاریخی',
    name: 'نام مجموعه‌داده',
    namePlaceholder: 'مثلاً BTC/USDT Historical 1H',
    source: 'منبع داده',
    sourcePlaceholder: 'مثلاً manual-import',
    baseAsset: 'دارایی پایه',
    quoteAsset: 'دارایی مقابل',
    timeframe: 'تایم‌فریم',
    datasetFile: 'فایل Dataset',
    fileHint: 'CSV، JSON یا Parquet؛ حداکثر ۱۰ مگابایت و ۱۰۰٬۰۰۰ ردیف.',
    downloadTemplate: 'دریافت نمونه CSV',
    inspecting: 'در حال بررسی فایل',
    mappingTitle: 'نگاشت ستون‌ها',
    mappingDescription: 'ستون فایل را برای هر فیلد استاندارد OHLCV انتخاب کنید.',
    optional: 'اختیاری',
    derivedCloseTime: 'محاسبه از تایم‌فریم',
    defaultClosed: 'مقدار پیش‌فرض: بسته‌شده',
    fields: fields.fa,
    previewButton: 'ساخت Preview',
    previewing: 'در حال ساخت Preview',
    importButton: 'ثبت Dataset تأییدشده',
    importing: 'در حال ثبت Dataset',
    previewTitle: 'Preview سمت سرور',
    previewFile: 'نام فایل',
    previewFormat: 'فرمت',
    previewRows: 'ردیف فایل',
    previewCandles: 'کندل canonical',
    previewStart: 'شروع داده',
    previewEnd: 'پایان داده',
    qualityScore: 'امتیاز کیفیت',
    qualityPassed: 'آماده ثبت',
    qualityRejected: 'ردشده توسط سیاست کیفیت',
    checksum: 'Preview checksum',
    successTitle: 'مجموعه‌داده ذخیره شد',
    successDescription: 'Snapshot تاریخی با provenance فایل و گزارش کیفیت ذخیره شد.',
    viewDataset: 'مشاهده مجموعه‌داده',
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
      fileRequired: 'ابتدا یک فایل Dataset انتخاب کنید.',
      fileTooLarge: 'حجم فایل نباید بیشتر از ۱۰ مگابایت باشد.',
      unsupportedFile: 'فقط فایل CSV، JSON یا Parquet پشتیبانی می‌شود.',
      inspectionFailed: 'بررسی ساختار فایل روی Backend ناموفق بود.',
      mappingRequired: 'ستون همه فیلدهای ضروری را انتخاب کنید.',
      duplicateMapping: 'هر ستون فایل فقط یک‌بار قابل انتخاب است.',
      previewFailed: 'ساخت Preview ناموفق بود؛ mapping و محتوای فایل را بررسی کنید.',
      qualityRejected: 'کیفیت Dataset تأیید نشد؛ مسائل Preview را برطرف کنید.',
      previewExpired: 'فایل یا mapping پس از Preview تغییر کرده است؛ دوباره Preview بگیرید.',
      submitFailed: 'ذخیره مجموعه‌داده ناموفق بود. اتصال Backend را بررسی کنید.',
    },
  },
  en: {
    title: 'Import historical dataset',
    description:
      'Inspect a CSV, JSON, or Parquet file on the backend, map its columns, and store only an approved preview.',
    historicalOnly: 'Historical data only',
    name: 'Dataset name',
    namePlaceholder: 'For example, BTC/USDT Historical 1H',
    source: 'Data source',
    sourcePlaceholder: 'For example, manual-import',
    baseAsset: 'Base asset',
    quoteAsset: 'Quote asset',
    timeframe: 'Timeframe',
    datasetFile: 'Dataset file',
    fileHint: 'CSV, JSON, or Parquet; maximum 10 MB and 100,000 rows.',
    downloadTemplate: 'Download CSV template',
    inspecting: 'Inspecting file',
    mappingTitle: 'Column mapping',
    mappingDescription: 'Select the source column for each canonical OHLCV field.',
    optional: 'Optional',
    derivedCloseTime: 'Derive from timeframe',
    defaultClosed: 'Default: closed',
    fields: fields.en,
    previewButton: 'Build preview',
    previewing: 'Building preview',
    importButton: 'Import approved dataset',
    importing: 'Importing dataset',
    previewTitle: 'Server preview',
    previewFile: 'File name',
    previewFormat: 'Format',
    previewRows: 'File rows',
    previewCandles: 'Canonical candles',
    previewStart: 'Data start',
    previewEnd: 'Data end',
    qualityScore: 'Quality score',
    qualityPassed: 'Ready to import',
    qualityRejected: 'Rejected by quality policy',
    checksum: 'Preview checksum',
    successTitle: 'Dataset stored',
    successDescription:
      'The historical snapshot was stored with file provenance and quality evidence.',
    viewDataset: 'View dataset',
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
      fileRequired: 'Select a dataset file first.',
      fileTooLarge: 'The file cannot be larger than 10 MB.',
      unsupportedFile: 'Only CSV, JSON, and Parquet files are supported.',
      inspectionFailed: 'The backend could not inspect the file structure.',
      mappingRequired: 'Select a column for every required field.',
      duplicateMapping: 'Each source column can be selected only once.',
      previewFailed: 'Preview failed. Check the mapping and file contents.',
      qualityRejected: 'Dataset quality was rejected. Resolve the preview issues first.',
      previewExpired: 'The file or mapping changed after preview. Build a new preview.',
      submitFailed: 'The dataset could not be stored. Check the backend connection.',
    },
  },
};

export function getDatasetImportCopy(locale: DashboardLocale): DatasetImportCopy {
  return copies[locale];
}
