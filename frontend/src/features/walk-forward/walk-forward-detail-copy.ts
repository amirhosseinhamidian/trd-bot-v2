import type { PlatformLocale } from '@/platform/i18n';

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
  foldsTableScrollLabel: string;
  analyticsCharts: string;
  analyticsChartsDescription: string;
  chartMetricSelector: string;
  foldReturnsChart: string;
  foldDrawdownsChart: string;
  emptyFoldChart: string;
  strategySeries: string;
  benchmarkSeries: string;
  metricDefinitions: string;
  metricDefinitionsDescription: string;
  metricLabels: Record<
    | 'median_fold_return'
    | 'worst_fold_return'
    | 'traded_fold_fraction'
    | 'return_consistency'
    | 'fold_drawdown'
    | 'excess_return',
    string
  >;
  metricDescriptions: Record<
    | 'median_fold_return'
    | 'worst_fold_return'
    | 'traded_fold_fraction'
    | 'return_consistency'
    | 'fold_drawdown'
    | 'excess_return',
    string
  >;
  metricPreferences: {
    higher_is_better: string;
    lower_is_better: string;
    context_only: string;
  };
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
    foldsWithoutTrades: string;
    tradedFoldFraction: string;
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
    returnConsistency: string;
    averageExcessReturn: string;
    medianExcessReturn: string;
    worstDrawdown: string;
    worstReturnFold: string;
    worstDrawdownFold: string;
    foldNumber: string;
    trades: string;
    strategyReturn: string;
    benchmarkReturn: string;
    excessReturn: string;
    drawdown: string;
    benchmarkDrawdown: string;
    direction: string;
    tradeStatus: string;
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
  tradeStatuses: {
    withTrades: string;
    withoutTrades: string;
  };
  modes: {
    rolling: string;
    expanding: string;
  };
};

const copies: Record<PlatformLocale, WalkForwardDetailCopy> = {
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
    foldsTableScrollLabel:
      'جدول جزئیات Foldهای Walk-forward؛ برای مشاهده همه ستون‌ها به‌صورت افقی پیمایش کنید',
    analyticsCharts: 'مقایسه Foldها',
    analyticsChartsDescription:
      'بازده و افت سرمایه Strategy و Benchmark برای هر پنجره خارج از نمونه از همان داده جدول.',
    chartMetricSelector: 'انتخاب شاخص نمودار در موبایل',
    foldReturnsChart: 'نمودار بازده هر Fold',
    foldDrawdownsChart: 'نمودار افت سرمایه هر Fold',
    emptyFoldChart: 'داده Fold برای نمایش وجود ندارد.',
    strategySeries: 'Strategy',
    benchmarkSeries: 'Benchmark',
    metricDefinitions: 'تعریف شاخص‌های پایداری',
    metricDefinitionsDescription: 'فرمول دقیق شاخص‌های Fold و نحوه تفسیر مقدار آن‌ها.',
    metricLabels: {
      median_fold_return: 'میانه بازده Fold',
      worst_fold_return: 'بازده بدترین Fold',
      traded_fold_fraction: 'نسبت Fold دارای معامله',
      return_consistency: 'سازگاری بازده',
      fold_drawdown: 'افت سرمایه Fold',
      excess_return: 'بازده مازاد Fold',
    },
    metricDescriptions: {
      median_fold_return: 'مقدار میانی بازده Strategy پس از مرتب‌سازی Foldهای خارج از نمونه.',
      worst_fold_return: 'کمترین بازده تحقق‌یافته Strategy میان Foldهای خارج از نمونه.',
      traded_fold_fraction: 'نسبت Foldهایی که حداقل یک معامله بسته‌شده دارند.',
      return_consistency: 'سازگاری محدودشده بازده پس از نرمال‌سازی انحراف مطلق میانگین.',
      fold_drawdown: 'بزرگ‌ترین افت تحقق‌یافته از قله موجودی در یک Fold آزمایشی.',
      excess_return: 'بازده Strategy در Fold منهای بازده خرید و نگهداری همان Fold.',
    },
    metricPreferences: {
      higher_is_better: 'مقدار بیشتر معمولاً بهتر است.',
      lower_is_better: 'مقدار کمتر معمولاً بهتر است.',
      context_only: 'این شاخص باید همراه با سایر شواهد تفسیر شود.',
    },
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
      foldsWithoutTrades: 'Fold بدون معامله',
      tradedFoldFraction: 'نسبت Fold دارای معامله',
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
      returnConsistency: 'سازگاری بازده',
      averageExcessReturn: 'میانگین بازده مازاد',
      medianExcessReturn: 'میانه بازده مازاد',
      worstDrawdown: 'بدترین افت سرمایه',
      worstReturnFold: 'شماره بدترین Fold بازده',
      worstDrawdownFold: 'شماره بدترین Fold افت',
      foldNumber: 'Fold',
      trades: 'معاملات شبیه‌سازی‌شده',
      strategyReturn: 'بازده Strategy',
      benchmarkReturn: 'بازده Benchmark',
      excessReturn: 'بازده مازاد',
      drawdown: 'افت سرمایه',
      benchmarkDrawdown: 'افت Benchmark',
      direction: 'جهت بازده',
      tradeStatus: 'وضعیت معامله',
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
    tradeStatuses: {
      withTrades: 'دارای معامله',
      withoutTrades: 'بدون معامله',
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
    foldsTableScrollLabel:
      'Walk-forward fold details table; scroll horizontally to view all columns',
    analyticsCharts: 'Fold comparison',
    analyticsChartsDescription:
      'Strategy and benchmark returns and drawdowns for every out-of-sample window, from the same data as the table.',
    chartMetricSelector: 'Select a chart metric on mobile',
    foldReturnsChart: 'Return by fold chart',
    foldDrawdownsChart: 'Drawdown by fold chart',
    emptyFoldChart: 'No fold data are available.',
    strategySeries: 'Strategy',
    benchmarkSeries: 'Benchmark',
    metricDefinitions: 'Stability metric definitions',
    metricDefinitionsDescription:
      'Exact formulas for fold metrics and how their values should be interpreted.',
    metricLabels: {
      median_fold_return: 'Median fold return',
      worst_fold_return: 'Worst fold return',
      traded_fold_fraction: 'Traded fold fraction',
      return_consistency: 'Return consistency',
      fold_drawdown: 'Fold drawdown',
      excess_return: 'Fold excess return',
    },
    metricDescriptions: {
      median_fold_return: 'Middle out-of-sample strategy return after fold returns are sorted.',
      worst_fold_return: 'Lowest realized strategy return across out-of-sample folds.',
      traded_fold_fraction: 'Share of out-of-sample folds containing at least one closed trade.',
      return_consistency: 'Bounded return consistency after normalizing mean absolute deviation.',
      fold_drawdown: 'Largest realized peak-to-trough decline inside one test fold.',
      excess_return: 'Fold strategy return minus the same fold’s buy-and-hold return.',
    },
    metricPreferences: {
      higher_is_better: 'A higher value is generally preferred.',
      lower_is_better: 'A lower value is generally preferred.',
      context_only: 'Interpret this metric together with the other evidence.',
    },
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
      foldsWithoutTrades: 'Folds without trades',
      tradedFoldFraction: 'Traded fold fraction',
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
      returnConsistency: 'Return consistency',
      averageExcessReturn: 'Average excess return',
      medianExcessReturn: 'Median excess return',
      worstDrawdown: 'Worst drawdown',
      worstReturnFold: 'Worst-return fold number',
      worstDrawdownFold: 'Worst-drawdown fold number',
      foldNumber: 'Fold',
      trades: 'Simulated trades',
      strategyReturn: 'Strategy return',
      benchmarkReturn: 'Benchmark return',
      excessReturn: 'Excess return',
      drawdown: 'Drawdown',
      benchmarkDrawdown: 'Benchmark drawdown',
      direction: 'Return direction',
      tradeStatus: 'Trade status',
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
    tradeStatuses: {
      withTrades: 'Has trades',
      withoutTrades: 'No trades',
    },
    modes: {
      rolling: 'Rolling',
      expanding: 'Expanding',
    },
  },
};

export function getWalkForwardDetailCopy(locale: PlatformLocale): WalkForwardDetailCopy {
  return copies[locale];
}
