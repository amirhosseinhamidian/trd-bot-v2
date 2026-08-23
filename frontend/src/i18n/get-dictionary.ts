/* eslint-disable @next/next/no-assign-module-variable */
import type { DashboardDictionary } from '@/i18n/dictionary';
import type { Locale } from '@/i18n/config';

const dictionaries: Record<Locale, () => Promise<DashboardDictionary>> = {
  fa: async () => {
    const module = await import('@/i18n/dictionaries/fa');

    return module.default;
  },

  en: async () => {
    const module = await import('@/i18n/dictionaries/en');

    return module.default;
  },
};

export function getDictionary(locale: Locale): Promise<DashboardDictionary> {
  return dictionaries[locale]();
}
