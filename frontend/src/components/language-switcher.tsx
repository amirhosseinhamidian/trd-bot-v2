import Link from 'next/link';

import type { Locale } from '@/i18n/config';

interface LanguageSwitcherProps {
  locale: Locale;
  persianLabel: string;
  englishLabel: string;
  ariaLabel: string;
}

export default function LanguageSwitcher({
  locale,
  persianLabel,
  englishLabel,
  ariaLabel,
}: LanguageSwitcherProps) {
  const baseClassName = [
    'rounded-lg',
    'px-3',
    'py-2',
    'text-xs',
    'font-semibold',
    'transition-colors',
  ].join(' ');

  const activeClassName = [baseClassName, 'bg-app-accent', 'text-app-background'].join(' ');

  const inactiveClassName = [
    baseClassName,
    'text-app-muted',
    'hover:bg-app-hover',
    'hover:text-app-foreground',
  ].join(' ');

  return (
    <nav
      aria-label={ariaLabel}
      className={[
        'flex',
        'items-center',
        'gap-1',
        'rounded-xl',
        'border',
        'border-app-border',
        'bg-app-surface',
        'p-1',
      ].join(' ')}
      dir="ltr"
    >
      <Link
        className={locale === 'fa' ? activeClassName : inactiveClassName}
        href="/fa"
        hrefLang="fa"
      >
        {persianLabel}
      </Link>

      <Link
        className={locale === 'en' ? activeClassName : inactiveClassName}
        href="/en"
        hrefLang="en"
      >
        {englishLabel}
      </Link>
    </nav>
  );
}
