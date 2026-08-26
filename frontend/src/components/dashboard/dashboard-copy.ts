export type DashboardLocale = 'fa' | 'en';

export type DashboardCopy = {
  brand: {
    name: string;
    description: string;
  };
  navigation: {
    overview: string;
    experiments: string;
    datasets: string;
    walkForward: string;
    portfolios: string;
    signals: string;
    settings: string;
    comingSoon: string;
    monitoring: string;
  };
  header: {
    researchMode: string;
    language: string;
  };
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
  loading: {
    title: string;
    description: string;
  };
  notFound: {
    title: string;
    description: string;
    back: string;
  };
  error: {
    title: string;
    description: string;
    retry: string;
  };
};

const copies: Record<DashboardLocale, DashboardCopy> = {
  fa: {
    brand: {
      name: 'TRD Research',
      description: 'آزمایشگاه پژوهش بازار',
    },
    navigation: {
      overview: 'نمای کلی',
      experiments: 'آزمایش‌ها',
      datasets: 'مجموعه‌داده‌ها',
      walkForward: 'تحلیل Walk-forward',
      portfolios: 'گزارش‌های پرتفوی تاریخی',
      signals: 'سیگنال‌های پژوهشی',
      settings: 'تنظیمات',
      comingSoon: 'به‌زودی',
      monitoring: 'پایش سیستم',
    },
    header: {
      researchMode: 'حالت پژوهشی — بدون اجرای معامله واقعی',
      language: 'English',
    },
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
    loading: {
      title: 'در حال دریافت اطلاعات پژوهش',
      description: 'داده‌های داشبورد از Backend دریافت می‌شوند.',
    },
    notFound: {
      title: 'صفحه موردنظر پیدا نشد',
      description: 'ممکن است نشانی صفحه اشتباه باشد یا این بخش دیگر در دسترس نباشد.',
      back: 'بازگشت به نمای کلی',
    },
    error: {
      title: 'دریافت اطلاعات ناموفق بود',
      description: 'اتصال Backend و مقدار NEXT_PUBLIC_API_BASE_URL را بررسی و دوباره تلاش کنید.',
      retry: 'تلاش مجدد',
    },
  },
  en: {
    brand: {
      name: 'TRD Research',
      description: 'Market research laboratory',
    },
    navigation: {
      overview: 'Overview',
      experiments: 'Experiments',
      datasets: 'Datasets',
      walkForward: 'Walk-forward analysis',
      portfolios: 'Historical portfolio reports',
      signals: 'Research signals',
      settings: 'Settings',
      comingSoon: 'Coming soon',
      monitoring: 'System monitoring',
    },
    header: {
      researchMode: 'Research mode — no live trade execution',
      language: 'فارسی',
    },
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
    loading: {
      title: 'Loading research information',
      description: 'Dashboard data is being retrieved from the backend.',
    },
    notFound: {
      title: 'Page not found',
      description: 'The address may be incorrect, or this page may no longer be available.',
      back: 'Back to overview',
    },
    error: {
      title: 'Unable to load information',
      description: 'Check the backend connection and NEXT_PUBLIC_API_BASE_URL, then try again.',
      retry: 'Try again',
    },
  },
};

export function getDashboardCopy(locale: DashboardLocale): DashboardCopy {
  return copies[locale];
}
