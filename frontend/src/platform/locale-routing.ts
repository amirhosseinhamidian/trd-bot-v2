import { isLocale, type Locale } from '@/i18n/config';

export function getAlternateLocale(locale: Locale): Locale {
  return locale === 'fa' ? 'en' : 'fa';
}

export function getLocalizedPathname(pathname: string, locale: Locale): string {
  const normalizedPathname = pathname.startsWith('/') ? pathname : `/${pathname}`;
  const segments = normalizedPathname.split('/');

  if (isLocale(segments[1] ?? '')) {
    segments[1] = locale;
  } else {
    segments.splice(1, 0, locale);
  }

  return segments.join('/') || `/${locale}`;
}

export function getAlternateLocalePathname(pathname: string, locale: Locale): string {
  return getLocalizedPathname(pathname, getAlternateLocale(locale));
}
