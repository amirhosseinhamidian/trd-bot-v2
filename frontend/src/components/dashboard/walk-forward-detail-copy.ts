import type { DashboardLocale } from '@/components/dashboard/dashboard-copy';

export type WalkForwardDetailCopy = {
  back: string;
  notFoundTitle: string;
  notFoundDescription: string;
  eyebrow: string;
  historicalOnly: string;
  disclaimer: string;
  summary: string;
  summaryDescription: string;
  stability: string;
  stabilityDescription: string;
  folds: string;
  foldsDescription: string;
  configuration: string;
  configurationDescription: string;
  fields: {
    executionId: string;
    datasetId: string;
    planId: string;
    strategy: string;
    version: string;
    createdAt: string;
    horizon: string;
    totalFolds: string;
    totalSignals: string;
    foldsWithTrades: string;
    positiveFraction: string;
    positiveFolds: string;
    negativeFolds: string;
    flatFolds: string;
    outperformingFolds: string;
    underperformingFolds: string;
    benchmarkTies: string;
    averageReturn: string;
    medianReturn: string;
    bestReturn: string;
    worstReturn: string;
    returnRange: string;
    meanAbsoluteDeviation: string;
    averageExcessReturn: string;
    medianExcessReturn: string;
    worstDrawdown: string;
    foldNumber: string;
    trades: string;
    strategyReturn: string;
    benchmarkReturn: string;
    excessReturn: string;
    drawdown: string;
    direction: string;
    mode: string;
    trainCandles: string;
    testCandles: string;
    stepCandles: string;
    gapCandles: string;
    parameters: string;
  };
  directions: {
    positive: string;
    negative: string;
    flat: string;
  };
  modes: {
    rolling: string;
    expanding: string;
  };
};

const copies: Record<DashboardLocale, WalkForwardDetailCopy> = {
  fa: {
    back: 'بازگشت به Walk-forward',
    notFoundTitle: 'اجرای Walk-forward پیدا نشد',
    notFoundDescription:
      'ممکن است شناسه اجرا نامعتبر باشد یا این اجرای تاریخی دیگر در پایگاه داده موجود نباشد.',
    eyebrow: 'جزئیات اعتبارسنجی خارج از نمونه',
    historicalOnly: 'فقط پژوهش تاریخی',
    disclaimer:
      'این گزارش فقط رفتار گذشته استراتژی را در پنجره‌های تاریخی نشان می‌دهد و توصیه مالی یا تضمین عملکرد آینده نیست.',
    summary: 'خلاصه اجرا',
    summaryDescription: 'هویت Strategy، Dataset و اجرای Walk-forward.',
    stability: 'شاخص‌های پایداری تاریخی',
    stabilityDescription: 'توزیع و پراکندگی بازده در Foldهای خارج از نمونه.',
    folds: 'جزئیات Foldها',
    foldsDescription: 'نتیجه مستقل هر پنجره Test در شبیه‌سازی تاریخی.',
    configuration: 'تنظیمات اجرا',
    configurationDescription: 'پنجره‌های زمانی و پارامترهای استفاده‌شده برای بازتولید این اجرا.',
    fields: {
      executionId: 'شناسه اجرا',
      datasetId: 'شناسه Dataset',
      planId: 'شناسه Plan',
      strategy: 'Strategy',
      version: 'نسخه',
      createdAt: 'زمان ایجاد',
      horizon: 'افق ارزیابی',
      totalFolds: 'تعداد Fold',
      totalSignals: 'تعداد سیگنال‌ها',
      foldsWithTrades: 'Fold دارای معامله شبیه‌سازی‌شده',
      positiveFraction: 'درصد Foldهای مثبت',
      positiveFolds: 'Fold مثبت',
      negativeFolds: 'Fold منفی',
      flatFolds: 'Fold بدون تغییر',
      outperformingFolds: 'برتری نسبت به Benchmark',
      underperformingFolds: 'عملکرد ضعیف‌تر از Benchmark',
      benchmarkTies: 'برابری با Benchmark',
      averageReturn: 'میانگین بازده',
      medianReturn: 'میانه بازده',
      bestReturn: 'بهترین بازده',
      worstReturn: 'بدترین بازده',
      returnRange: 'دامنه بازده',
      meanAbsoluteDeviation: 'میانگین انحراف مطلق',
      averageExcessReturn: 'میانگین بازده مازاد',
      medianExcessReturn: 'میانه بازده مازاد',
      worstDrawdown: 'بدترین افت سرمایه',
      foldNumber: 'Fold',
      trades: 'معاملات شبیه‌سازی‌شده',
      strategyReturn: 'بازده Strategy',
      benchmarkReturn: 'بازده Benchmark',
      excessReturn: 'بازده مازاد',
      drawdown: 'افت سرمایه',
      direction: 'جهت بازده',
      mode: 'نوع پنجره',
      trainCandles: 'کندل‌های Train',
      testCandles: 'کندل‌های Test',
      stepCandles: 'فاصله حرکت',
      gapCandles: 'فاصله Train و Test',
      parameters: 'پارامترهای Strategy',
    },
    directions: {
      positive: 'مثبت',
      negative: 'منفی',
      flat: 'بدون تغییر',
    },
    modes: {
      rolling: 'غلتان',
      expanding: 'گسترش‌یابنده',
    },
  },
  en: {
    back: 'Back to walk-forward',
    notFoundTitle: 'Walk-forward run not found',
    notFoundDescription:
      'The execution identifier may be invalid, or the historical run may no longer exist.',
    eyebrow: 'Out-of-sample validation details',
    historicalOnly: 'Historical research only',
    disclaimer:
      'This report only describes past strategy behavior across historical windows and is not financial advice or a guarantee of future performance.',
    summary: 'Execution summary',
    summaryDescription: 'Strategy, dataset, and walk-forward execution identity.',
    stability: 'Historical stability metrics',
    stabilityDescription: 'Return distribution and dispersion across out-of-sample folds.',
    folds: 'Fold details',
    foldsDescription: 'Independent results for every historical test window.',
    configuration: 'Execution configuration',
    configurationDescription:
      'Window and strategy parameters required to reproduce this execution.',
    fields: {
      executionId: 'Execution ID',
      datasetId: 'Dataset ID',
      planId: 'Plan ID',
      strategy: 'Strategy',
      version: 'Version',
      createdAt: 'Created at',
      horizon: 'Evaluation horizon',
      totalFolds: 'Total folds',
      totalSignals: 'Total signals',
      foldsWithTrades: 'Folds with simulated trades',
      positiveFraction: 'Positive fold fraction',
      positiveFolds: 'Positive folds',
      negativeFolds: 'Negative folds',
      flatFolds: 'Flat folds',
      outperformingFolds: 'Outperforming benchmark',
      underperformingFolds: 'Underperforming benchmark',
      benchmarkTies: 'Benchmark ties',
      averageReturn: 'Average return',
      medianReturn: 'Median return',
      bestReturn: 'Best return',
      worstReturn: 'Worst return',
      returnRange: 'Return range',
      meanAbsoluteDeviation: 'Mean absolute deviation',
      averageExcessReturn: 'Average excess return',
      medianExcessReturn: 'Median excess return',
      worstDrawdown: 'Worst drawdown',
      foldNumber: 'Fold',
      trades: 'Simulated trades',
      strategyReturn: 'Strategy return',
      benchmarkReturn: 'Benchmark return',
      excessReturn: 'Excess return',
      drawdown: 'Drawdown',
      direction: 'Return direction',
      mode: 'Window mode',
      trainCandles: 'Train candles',
      testCandles: 'Test candles',
      stepCandles: 'Step candles',
      gapCandles: 'Gap candles',
      parameters: 'Strategy parameters',
    },
    directions: {
      positive: 'Positive',
      negative: 'Negative',
      flat: 'Flat',
    },
    modes: {
      rolling: 'Rolling',
      expanding: 'Expanding',
    },
  },
};

export function getWalkForwardDetailCopy(locale: DashboardLocale): WalkForwardDetailCopy {
  return copies[locale];
}
