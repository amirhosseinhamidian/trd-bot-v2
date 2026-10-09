import { act } from 'react';
import { hydrateRoot, type Root } from 'react-dom/client';
import { renderToString } from 'react-dom/server';

import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  THEME_BOOTSTRAP_SCRIPT,
  THEME_BOOTSTRAP_SCRIPT_ID,
  THEME_STORAGE_KEY,
} from '@/components/theme/theme';
import ThemeToggle from '@/components/theme/theme-toggle';
import { locales, type Locale } from '@/i18n/config';
import { getAlternateLocalePathname } from '@/platform/locale-routing';
import { getLocalizedRoutePatterns, PRESERVED_LOCALE_ROUTE_FILES } from '@/platform/route-contract';

const hydratedRoots: Root[] = [];

function runThemeBootstrap(): void {
  Function(THEME_BOOTSTRAP_SCRIPT)();
}

afterEach(async () => {
  for (const root of hydratedRoots.splice(0)) {
    await act(async () => root.unmount());
  }

  vi.restoreAllMocks();
  window.localStorage.clear();
  delete document.documentElement.dataset.theme;
  document.documentElement.style.colorScheme = '';
  document.body.replaceChildren();
});

describe('P6 locale round-trip contract', () => {
  it.each(locales)('switches every preserved route away from and back to %s', (locale) => {
    const alternateLocale: Locale = locale === 'fa' ? 'en' : 'fa';
    const localizedRoutes = getLocalizedRoutePatterns(locale);
    const alternateRoutes = getLocalizedRoutePatterns(alternateLocale);

    expect(localizedRoutes).toHaveLength(PRESERVED_LOCALE_ROUTE_FILES.length);

    for (const [index, pathname] of localizedRoutes.entries()) {
      const alternatePathname = getAlternateLocalePathname(pathname, locale);

      expect(alternatePathname).toBe(alternateRoutes[index]);
      expect(getAlternateLocalePathname(alternatePathname, alternateLocale)).toBe(pathname);
    }
  });

  it('preserves encoded identifiers and localizes an unprefixed fallback path', () => {
    expect(getAlternateLocalePathname('/fa/datasets/BTC%2FUSDT', 'fa')).toBe(
      '/en/datasets/BTC%2FUSDT',
    );
    expect(getAlternateLocalePathname('/datasets/BTC%2FUSDT', 'en')).toBe(
      '/fa/datasets/BTC%2FUSDT',
    );
  });
});

describe.each([
  {
    locale: 'fa' as const,
    lightLabel: 'فعال کردن پوسته تیره',
    darkLabel: 'فعال کردن پوسته روشن',
  },
  {
    locale: 'en' as const,
    lightLabel: 'Switch to dark theme',
    darkLabel: 'Switch to light theme',
  },
])('P6 theme hydration contract in $locale', ({ locale, lightLabel, darkLabel }) => {
  it('hydrates a pre-bootstrapped light theme without a mismatch and still toggles', async () => {
    const container = document.createElement('div');
    const serverMarkup = renderToString(<ThemeToggle locale={locale} />);
    const consoleErrors: string[] = [];

    container.innerHTML = serverMarkup;
    document.body.append(container);
    window.localStorage.setItem(THEME_STORAGE_KEY, 'light');
    runThemeBootstrap();

    expect(document.documentElement.dataset.theme).toBe('light');

    vi.spyOn(console, 'error').mockImplementation((...messages: unknown[]) => {
      consoleErrors.push(messages.map(String).join(' '));
    });

    await act(async () => {
      hydratedRoots.push(hydrateRoot(container, <ThemeToggle locale={locale} />));
      await Promise.resolve();
    });

    const toggle = await within(container).findByRole('button', { name: lightLabel });

    expect(
      consoleErrors.filter((message) => /hydration|did not match|server rendered/i.test(message)),
    ).toEqual([]);
    expect(document.documentElement.style.colorScheme).toBe('light');

    await userEvent.setup().click(toggle);

    expect(document.documentElement.dataset.theme).toBe('dark');
    expect(document.documentElement.style.colorScheme).toBe('dark');
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe('dark');
    expect(screen.getByRole('button', { name: darkLabel })).toBeInTheDocument();
  });
});

describe('P6 document hydration boundary', () => {
  it('keeps theme bootstrap before hydration and scopes suppression to the document root', async () => {
    const { readFile } = await import('node:fs/promises');
    const { resolve } = await import('node:path');
    const layoutSource = await readFile(
      resolve(process.cwd(), 'src/app/[locale]/layout.tsx'),
      'utf8',
    );

    expect(layoutSource).toContain('<html lang={locale}');
    expect(layoutSource).toContain("dir={locale === 'fa' ? 'rtl' : 'ltr'}");
    expect(layoutSource).toContain('suppressHydrationWarning');
    expect(layoutSource.match(/suppressHydrationWarning/g)).toHaveLength(1);
    expect(layoutSource).toContain(`id={THEME_BOOTSTRAP_SCRIPT_ID}`);
    expect(layoutSource).toContain('strategy="beforeInteractive"');
    expect(THEME_BOOTSTRAP_SCRIPT_ID).toBe('app-theme-bootstrap');
  });
});
