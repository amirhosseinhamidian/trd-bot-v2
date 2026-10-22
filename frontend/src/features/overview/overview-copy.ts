import type { PlatformLocale } from '@/platform/i18n';

export type OverviewCopy = {
  overview: {
    eyebrow: string;
    title: string;
    description: string;
    connected: string;
    cards: {
      datasets: string;
      experiments: string;
      walkForward: string;
      policies: string;
    };
    activity: {
      title: string;
      description: string;
      empty: string;
      types: {
        dataset: string;
        experiment: string;
        walkForwardRun: string;
      };
    };
    stages: {
      title: string;
      description: string;
      current: string;
      empty: string;
      dataAvailable: string;
      experimentsAvailable: string;
      walkForwardAvailable: string;
    };
    latest: {
      title: string;
      description: string;
      dataset: string;
      experiment: string;
      walkForward: string;
      noData: string;
      candles: string;
      timeframe: string;
      trades: string;
      return: string;
      comparison: string;
      folds: string;
      excessReturn: string;
    };
  };
};

const copies: Record<PlatformLocale, OverviewCopy> = {
  fa: {
    overview: {
      eyebrow: 'Research workspace',
      title: 'نمای کلی پژوهش',
      description:
        'وضعیت مجموعه‌داده‌ها، آزمایش‌های استراتژی و ارزیابی‌های Walk-forward را مشاهده کنید.',
      connected: 'Backend متصل است',
      cards: {
        datasets: 'مجموعه‌داده‌ها',
        experiments: 'آزمایش‌ها',
        walkForward: 'اجراهای Walk-forward',
        policies: 'سیاست‌های پذیرش',
      },
      activity: {
        title: 'فعالیت‌های اخیر',
        description: 'آخرین داده‌ها و اجرای فرآیندهای پژوهشی',
        empty: 'هنوز هیچ فعالیت پژوهشی ثبت نشده است.',
        types: {
          dataset: 'مجموعه‌داده',
          experiment: 'آزمایش',
          walkForwardRun: 'Walk-forward',
        },
      },
      stages: {
        title: 'مرحله فعلی پژوهش',
        description: 'میزان پیشرفت چرخه ارزیابی استراتژی',
        current: 'مرحله فعلی',
        empty: 'بدون داده',
        dataAvailable: 'داده آماده',
        experimentsAvailable: 'آزمایش آماده',
        walkForwardAvailable: 'Walk-forward آماده',
      },
      latest: {
        title: 'آخرین خروجی‌های پژوهش',
        description: 'جدیدترین خروجی ثبت‌شده در هر بخش',
        dataset: 'آخرین مجموعه‌داده',
        experiment: 'آخرین آزمایش',
        walkForward: 'آخرین Walk-forward',
        noData: 'هنوز داده‌ای ثبت نشده است.',
        candles: 'تعداد کندل',
        timeframe: 'تایم‌فریم',
        trades: 'تعداد معاملات شبیه‌سازی‌شده',
        return: 'بازده تاریخی',
        comparison: 'نتیجه مقایسه',
        folds: 'تعداد Fold',
        excessReturn: 'بازده مازاد تاریخی',
      },
    },
  },
  en: {
    overview: {
      eyebrow: 'Research workspace',
      title: 'Research overview',
      description: 'Review datasets, strategy experiments, and walk-forward evaluation status.',
      connected: 'Backend connected',
      cards: {
        datasets: 'Datasets',
        experiments: 'Experiments',
        walkForward: 'Walk-forward runs',
        policies: 'Acceptance policies',
      },
      activity: {
        title: 'Recent activity',
        description: 'Latest research data and executions',
        empty: 'No research activity has been recorded yet.',
        types: {
          dataset: 'Dataset',
          experiment: 'Experiment',
          walkForwardRun: 'Walk-forward',
        },
      },
      stages: {
        title: 'Current research stage',
        description: 'Strategy evaluation lifecycle progress',
        current: 'Current stage',
        empty: 'No data',
        dataAvailable: 'Data available',
        experimentsAvailable: 'Experiments available',
        walkForwardAvailable: 'Walk-forward available',
      },
      latest: {
        title: 'Latest research outputs',
        description: 'Most recently stored output in every area',
        dataset: 'Latest dataset',
        experiment: 'Latest experiment',
        walkForward: 'Latest walk-forward',
        noData: 'No data has been recorded yet.',
        candles: 'Candles',
        timeframe: 'Timeframe',
        trades: 'Simulated trades',
        return: 'Historical return',
        comparison: 'Comparison outcome',
        folds: 'Folds',
        excessReturn: 'Historical excess return',
      },
    },
  },
};

export function getOverviewCopy(locale: PlatformLocale): OverviewCopy {
  return copies[locale];
}
