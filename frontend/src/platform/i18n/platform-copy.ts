import { NEXORA_PLATFORM_NAME, TRD_BOT_PRODUCT_NAME } from '@/platform/brand';
import type { Locale } from '@/i18n/config';
import type { PlatformNavigationGroupKey, PlatformNavigationItemKey } from '@/platform/navigation';

export type PlatformLocale = Locale;

export type PlatformCopy = {
  brand: {
    platformName: string;
    productName: string;
    description: string;
  };
  navigation: {
    groups: Record<PlatformNavigationGroupKey, string>;
    items: Record<PlatformNavigationItemKey, string>;
    comingSoon: string;
    mobile: {
      label: string;
      more: string;
      closeMenu: string;
    };
  };
  header: {
    researchMode: string;
    language: string;
    navigation: string;
    openNavigation: string;
    closeNavigation: string;
  };
  feedback: {
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
};

const platformCopies: Record<PlatformLocale, PlatformCopy> = {
  fa: {
    brand: {
      platformName: NEXORA_PLATFORM_NAME,
      productName: TRD_BOT_PRODUCT_NAME,
      description: 'پلتفرم پژوهش بازار',
    },
    navigation: {
      groups: {
        root: 'نمای کلی',
        research: 'پژوهش',
        strategyDecision: 'استراتژی و تصمیم‌گیری',
        simulation: 'شبیه‌سازی',
        data: 'داده',
        system: 'سامانه',
      },
      items: {
        overview: 'نمای کلی',
        datasets: 'مجموعه‌داده‌ها',
        experiments: 'آزمایش‌ها',
        walkForward: 'تحلیل Walk-forward',
        optimizations: 'بهینه‌سازی‌ها',
        strategies: 'استراتژی‌ها',
        signals: 'سیگنال‌ها',
        candidates: 'کاندیدها',
        risk: 'ریسک',
        portfolios: 'پرتفوی‌های تاریخی',
        connections: 'اتصال‌های داده',
        monitoring: 'پایش سامانه',
      },
      comingSoon: 'به‌زودی',
      mobile: {
        label: 'ناوبری موبایل',
        more: 'بیشتر',
        closeMenu: 'بستن منو',
      },
    },
    header: {
      researchMode: 'حالت پژوهشی — بدون اجرای معامله واقعی',
      language: 'English',
      navigation: 'ناوبری پلتفرم',
      openNavigation: 'باز کردن ناوبری',
      closeNavigation: 'بستن ناوبری',
    },
    feedback: {
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
  },
  en: {
    brand: {
      platformName: NEXORA_PLATFORM_NAME,
      productName: TRD_BOT_PRODUCT_NAME,
      description: 'Market research platform',
    },
    navigation: {
      groups: {
        root: 'Overview',
        research: 'Research',
        strategyDecision: 'Strategy & Decision',
        simulation: 'Simulation',
        data: 'Data',
        system: 'System',
      },
      items: {
        overview: 'Overview',
        datasets: 'Datasets',
        experiments: 'Experiments',
        walkForward: 'Walk-forward',
        optimizations: 'Optimizations',
        strategies: 'Strategies',
        signals: 'Signals',
        candidates: 'Candidates',
        risk: 'Risk',
        portfolios: 'Historical Portfolios',
        connections: 'Connections',
        monitoring: 'Monitoring',
      },
      comingSoon: 'Coming soon',
      mobile: {
        label: 'Mobile navigation',
        more: 'More',
        closeMenu: 'Close menu',
      },
    },
    header: {
      researchMode: 'Research mode — no live trade execution',
      language: 'فارسی',
      navigation: 'Platform navigation',
      openNavigation: 'Open navigation',
      closeNavigation: 'Close navigation',
    },
    feedback: {
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
  },
};

export function getPlatformCopy(locale: PlatformLocale): PlatformCopy {
  return platformCopies[locale];
}
