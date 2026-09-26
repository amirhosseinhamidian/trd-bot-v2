import type { ExperimentDetailLocale } from '@/components/dashboard/experiment-detail-copy';
import type { ExperimentReplayCode, ExperimentReplayStatus } from '@/lib/api/types';

export type ExperimentReplayCopy = {
  title: string;
  description: string;
  run: string;
  running: string;
  requestError: string;
  notRun: string;
  statusLabel: string;
  statuses: Record<ExperimentReplayStatus, string>;
  reasons: Record<ExperimentReplayCode, string>;
  checkedAt: string;
  recordedResult: string;
  replayedResult: string;
  recordedStrategy: string;
  currentStrategy: string;
  mismatchFields: string;
  unavailable: string;
};

const copies: Record<ExperimentDetailLocale, ExperimentReplayCopy> = {
  fa: {
    title: 'تأیید بازاجرای Experiment',
    description:
      'Dataset و نسخه ثبت‌شده بدون تغییر رکورد تاریخی دوباره اجرا و نتیجه کامل مقایسه می‌شوند.',
    run: 'اجرای بررسی بازتولیدپذیری',
    running: 'در حال بازاجرای تاریخی…',
    requestError: 'بررسی بازاجرا انجام نشد. اتصال API را بررسی و دوباره تلاش کنید.',
    notRun: 'این بررسی فقط با درخواست شما اجرا می‌شود و هیچ رکوردی را بازنویسی نمی‌کند.',
    statusLabel: 'نتیجه بررسی',
    statuses: {
      verified: 'تأییدشده',
      mismatch: 'عدم تطابق',
      unverifiable: 'غیرقابل تأیید',
    },
    reasons: {
      verified: 'نتیجه بازاجرا دقیقاً با نتیجه ذخیره‌شده برابر است.',
      legacy_fingerprint_missing:
        'این Experiment قدیمی fingerprint نسخه Strategy را ثبت نکرده و با حدس تأیید نمی‌شود.',
      dataset_not_found: 'Dataset immutable موردنیاز در دسترس نیست.',
      dataset_integrity_mismatch:
        'محتوای Dataset با checksum immutable ثبت‌شده آن مطابقت ندارد.',
      strategy_version_not_found: 'نسخه دقیق Strategy دیگر در Registry موجود نیست.',
      strategy_fingerprint_mismatch: 'fingerprint ثبت‌شده با تعریف فعلی همان نسخه متفاوت است.',
      invalid_strategy_parameters: 'پارامترهای ثبت‌شده برای بازسازی معتبر یا کامل نیستند.',
      replay_failed: 'Pipeline با ورودی‌های ثبت‌شده قابل بازاجرا نبود.',
      result_mismatch: 'نتیجه جدید با نتیجه immutable ذخیره‌شده یکسان نیست.',
    },
    checkedAt: 'زمان بررسی',
    recordedResult: 'Checksum نتیجه ثبت‌شده',
    replayedResult: 'Checksum نتیجه بازاجرا',
    recordedStrategy: 'Fingerprint ثبت‌شده Strategy',
    currentStrategy: 'Fingerprint فعلی Registry',
    mismatchFields: 'بخش‌های متفاوت',
    unavailable: 'در دسترس نیست',
  },
  en: {
    title: 'Experiment replay verification',
    description:
      'Replay the recorded dataset and exact strategy version, then compare the complete result without mutating history.',
    run: 'Verify reproducibility',
    running: 'Replaying historical experiment…',
    requestError: 'Replay verification failed. Check the API connection and try again.',
    notRun: 'This check runs only on request and never overwrites the historical record.',
    statusLabel: 'Verification outcome',
    statuses: {
      verified: 'Verified',
      mismatch: 'Mismatch',
      unverifiable: 'Unverifiable',
    },
    reasons: {
      verified: 'The replayed result exactly matches the stored result.',
      legacy_fingerprint_missing:
        'This legacy experiment did not record a strategy fingerprint and will not be verified by assumption.',
      dataset_not_found: 'The required immutable dataset is unavailable.',
      dataset_integrity_mismatch:
        'Dataset content does not match its recorded immutable checksum.',
      strategy_version_not_found: 'The exact strategy version is no longer registered.',
      strategy_fingerprint_mismatch:
        'The recorded fingerprint differs from the current definition of this version.',
      invalid_strategy_parameters: 'Recorded strategy parameters are incomplete or invalid.',
      replay_failed: 'The pipeline could not run with the recorded inputs.',
      result_mismatch: 'The new result does not match the immutable stored result.',
    },
    checkedAt: 'Checked at',
    recordedResult: 'Recorded result checksum',
    replayedResult: 'Replayed result checksum',
    recordedStrategy: 'Recorded strategy fingerprint',
    currentStrategy: 'Current Registry fingerprint',
    mismatchFields: 'Different result sections',
    unavailable: 'Unavailable',
  },
};

export function getExperimentReplayCopy(locale: ExperimentDetailLocale): ExperimentReplayCopy {
  return copies[locale];
}
