import type { ExperimentDetailLocale } from '@/components/dashboard/experiment-detail-copy';

export type ExperimentAcceptanceCopy = {
  title: string;
  description: string;
  policyLabel: string;
  policyPlaceholder: string;
  runAssessment: string;
  runningAssessment: string;
  retry: string;
  error: string;
  historicalOnly: string;
  thresholds: string;
  minimumTrades: string;
  minimumExcessReturn: string;
  maximumDrawdown: string;
  result: string;
  passedChecks: string;
  failedChecks: string;
  passed: string;
  failed: string;
  actualValue: string;
  thresholdValue: string;
  downloadCsv: string;
  downloadingCsv: string;
  downloadError: string;
  outcomes: {
    accepted: string;
    rejected: string;
    insufficient_data: string;
  };
  checks: {
    minimum_total_trades: string;
    minimum_excess_return: string;
    maximum_drawdown_fraction: string;
  };
  presetNames: Record<string, string>;
};

const copies: Record<ExperimentDetailLocale, ExperimentAcceptanceCopy> = {
  fa: {
    title: 'ارزیابی پژوهشی',
    description: 'نتایج تاریخی آزمایش را با یک Policy نسخه‌بندی‌شده و قابل‌بازتولید بررسی کنید.',
    policyLabel: 'Policy ارزیابی',
    policyPlaceholder: 'یک Policy انتخاب کنید',
    runAssessment: 'اجرای ارزیابی تاریخی',
    runningAssessment: 'در حال ارزیابی',
    retry: 'تلاش مجدد',
    error: 'دریافت گزارش ارزیابی ناموفق بود. اتصال Backend را بررسی کنید.',
    historicalOnly: 'این نتیجه فقط برای پژوهش تاریخی است.',
    thresholds: 'آستانه‌های Policy',
    minimumTrades: 'حداقل معاملات شبیه‌سازی‌شده',
    minimumExcessReturn: 'حداقل بازده مازاد',
    maximumDrawdown: 'حداکثر افت سرمایه',
    result: 'نتیجه ارزیابی',
    passedChecks: 'بررسی‌های موفق',
    failedChecks: 'بررسی‌های ناموفق',
    passed: 'عبور کرده',
    failed: 'عبور نکرده',
    actualValue: 'مقدار واقعی',
    thresholdValue: 'آستانه',
    downloadCsv: 'دانلود گزارش CSV',
    downloadingCsv: 'در حال آماده‌سازی',
    downloadError: 'دانلود گزارش ناموفق بود. دوباره تلاش کنید.',
    outcomes: {
      accepted: 'عبور از آستانه‌های پژوهشی',
      rejected: 'عدم عبور از آستانه‌های پژوهشی',
      insufficient_data: 'داده تاریخی ناکافی',
    },
    checks: {
      minimum_total_trades: 'حداقل تعداد معاملات',
      minimum_excess_return: 'حداقل بازده مازاد',
      maximum_drawdown_fraction: 'حداکثر افت سرمایه',
    },
    presetNames: {
      baseline: 'پایه',
      'larger-sample': 'نمونه آماری بزرگ‌تر',
      'drawdown-focused': 'متمرکز بر افت سرمایه',
    },
  },
  en: {
    title: 'Research assessment',
    description: 'Evaluate the historical experiment using a reproducible, versioned policy.',
    policyLabel: 'Assessment policy',
    policyPlaceholder: 'Select a policy',
    runAssessment: 'Run historical assessment',
    runningAssessment: 'Assessing',
    retry: 'Try again',
    error: 'Unable to retrieve the assessment report. Check the backend connection.',
    historicalOnly: 'This outcome is for historical research only.',
    thresholds: 'Policy thresholds',
    minimumTrades: 'Minimum simulated trades',
    minimumExcessReturn: 'Minimum excess return',
    maximumDrawdown: 'Maximum drawdown',
    result: 'Assessment result',
    passedChecks: 'Passed checks',
    failedChecks: 'Failed checks',
    passed: 'Passed',
    failed: 'Failed',
    actualValue: 'Actual value',
    thresholdValue: 'Threshold',
    downloadCsv: 'Download CSV report',
    downloadingCsv: 'Preparing download',
    downloadError: 'Unable to download the report. Please try again.',
    outcomes: {
      accepted: 'Passed research thresholds',
      rejected: 'Did not pass research thresholds',
      insufficient_data: 'Insufficient historical data',
    },
    checks: {
      minimum_total_trades: 'Minimum trade count',
      minimum_excess_return: 'Minimum excess return',
      maximum_drawdown_fraction: 'Maximum drawdown',
    },
    presetNames: {
      baseline: 'Baseline',
      'larger-sample': 'Larger sample',
      'drawdown-focused': 'Drawdown focused',
    },
  },
};

export function getExperimentAcceptanceCopy(
  locale: ExperimentDetailLocale,
): ExperimentAcceptanceCopy {
  return copies[locale];
}
