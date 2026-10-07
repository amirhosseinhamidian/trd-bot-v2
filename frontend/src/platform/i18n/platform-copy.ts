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
  };
  header: {
    researchMode: string;
    language: string;
    navigation: string;
    openNavigation: string;
    closeNavigation: string;
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
    },
    header: {
      researchMode: 'حالت پژوهشی — بدون اجرای معامله واقعی',
      language: 'English',
      navigation: 'ناوبری پلتفرم',
      openNavigation: 'باز کردن ناوبری',
      closeNavigation: 'بستن ناوبری',
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
    },
    header: {
      researchMode: 'Research mode — no live trade execution',
      language: 'فارسی',
      navigation: 'Platform navigation',
      openNavigation: 'Open navigation',
      closeNavigation: 'Close navigation',
    },
  },
};

export function getPlatformCopy(locale: PlatformLocale): PlatformCopy {
  return platformCopies[locale];
}
