import { readFileSync, readdirSync } from 'node:fs';
import { join, resolve } from 'node:path';

import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { type AnchorHTMLAttributes, type ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import PlatformShell from '@/components/platform/platform-shell';

const navigationState = vi.hoisted(() => ({ pathname: '/en' }));

vi.mock('next/navigation', () => ({
  usePathname: () => navigationState.pathname,
}));

vi.mock('next/link', () => ({
  default: ({
    href,
    children,
    ...props
  }: AnchorHTMLAttributes<HTMLAnchorElement> & {
    href: string;
    children: ReactNode;
  }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

vi.mock('@/components/theme/theme-toggle', () => ({
  default: ({ locale }: { locale: 'fa' | 'en' }) => (
    <button type="button" aria-label={locale === 'fa' ? 'پوسته' : 'Theme'}>
      Theme
    </button>
  ),
}));

function collectTsxSources(directory: string): Array<{ path: string; source: string }> {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const path = join(directory, entry.name);

    if (entry.isDirectory()) {
      return collectTsxSources(path);
    }

    return entry.name.endsWith('.tsx') ? [{ path, source: readFileSync(path, 'utf8') }] : [];
  });
}

const featureSources = collectTsxSources(resolve(process.cwd(), 'src/features'));

describe.each([
  {
    locale: 'en' as const,
    pathname: '/en',
    skip: 'Skip to main content',
    navigation: 'Platform navigation',
    mobileNavigation: 'Mobile navigation',
    openNavigation: 'Open navigation',
    closeNavigation: 'Close navigation',
    research: 'Research',
    datasets: 'Datasets',
  },
  {
    locale: 'fa' as const,
    pathname: '/fa',
    skip: 'رفتن به محتوای اصلی',
    navigation: 'ناوبری پلتفرم',
    mobileNavigation: 'ناوبری موبایل',
    openNavigation: 'باز کردن ناوبری',
    closeNavigation: 'بستن ناوبری',
    research: 'پژوهش',
    datasets: 'مجموعه‌داده‌ها',
  },
])('P6 accessibility walkthrough in $locale', (copy) => {
  beforeEach(() => {
    navigationState.pathname = copy.pathname;
  });

  it('exposes landmarks and moves from the skip link into page actions in order', async () => {
    const user = userEvent.setup();
    const { container } = render(
      <PlatformShell locale={copy.locale}>
        <button type="button">Primary page action</button>
        <a href="#evidence">Evidence</a>
      </PlatformShell>,
    );

    const skipLink = screen.getByRole('link', { name: copy.skip });
    const main = screen.getByRole('main');

    expect(container.querySelector('a')).toBe(skipLink);
    expect(screen.getAllByRole('banner')).toHaveLength(1);
    expect(screen.getAllByRole('main')).toHaveLength(1);
    expect(screen.getByRole('complementary', { name: copy.navigation })).toBeInTheDocument();
    expect(screen.getByRole('navigation', { name: copy.mobileNavigation })).toBeInTheDocument();

    await user.tab();
    expect(skipLink).toHaveFocus();

    await user.click(skipLink);
    expect(main).toHaveFocus();

    await user.tab();
    expect(screen.getByRole('button', { name: 'Primary page action' })).toHaveFocus();

    await user.tab();
    expect(screen.getByRole('link', { name: 'Evidence' })).toHaveFocus();
  });

  it('traps the tablet drawer, closes with Escape, and restores its trigger', async () => {
    const user = userEvent.setup();

    render(
      <PlatformShell locale={copy.locale}>
        <div>Content</div>
      </PlatformShell>,
    );

    const openButton = screen.getByRole('button', { name: copy.openNavigation });

    await user.click(openButton);

    const sidebar = screen.getByRole('complementary', { name: copy.navigation });
    const closeButton = within(sidebar).getByRole('button', { name: copy.closeNavigation });

    expect(closeButton).toHaveFocus();

    await user.tab({ shift: true });
    expect(within(sidebar).getAllByRole('link').at(-1)).toHaveFocus();

    await user.tab();
    expect(closeButton).toHaveFocus();

    await user.keyboard('{Escape}');
    expect(openButton).toHaveFocus();
    expect(openButton).toHaveAttribute('aria-expanded', 'false');
  });

  it('moves focus into a mobile menu and returns it after Escape', async () => {
    const user = userEvent.setup();

    render(
      <PlatformShell locale={copy.locale}>
        <div>Content</div>
      </PlatformShell>,
    );

    const mobileNavigation = screen.getByRole('navigation', { name: copy.mobileNavigation });
    const researchButton = within(mobileNavigation).getByRole('button', {
      name: copy.research,
    });

    await user.click(researchButton);

    const menu = document.getElementById('mobile-navigation-research');

    expect(menu).not.toBeNull();
    expect(menu).toHaveAttribute('role', 'dialog');
    expect(menu).toHaveAttribute('aria-modal', 'true');
    expect(within(menu!).getByRole('link', { name: copy.datasets })).toHaveFocus();

    await user.keyboard('{Escape}');
    expect(researchButton).toHaveFocus();
    expect(researchButton).toHaveAttribute('aria-expanded', 'false');
  });
});

describe('P6 semantic accessibility contracts', () => {
  it('prevents custom positive tab order and autofocus across feature screens', () => {
    for (const { path, source } of featureSources) {
      expect(source, path).not.toMatch(/tabIndex\s*=\s*(?:\{\s*)?[1-9]/);
      expect(source, path).not.toMatch(/\bautoFocus\b/);
    }
  });

  it('labels every feature table scroll region for keyboard users', () => {
    const tableOpenings = featureSources.flatMap(({ path, source }) =>
      [...source.matchAll(/<Table\b[\s\S]*?>/g)].map(([opening]) => ({ opening, path })),
    );

    expect(tableOpenings.length).toBeGreaterThan(0);

    for (const { opening, path } of tableOpenings) {
      expect(opening, path).toContain('scrollLabel=');
    }
  });

  it('gives every feature progressbar a name, range, and current value', () => {
    const progressbars = featureSources.flatMap(({ path, source }) =>
      [...source.matchAll(/<[^>]+role="progressbar"[\s\S]*?>/g)].map(([opening]) => ({
        opening,
        path,
      })),
    );

    expect(progressbars.length).toBeGreaterThan(0);

    for (const { opening, path } of progressbars) {
      expect(opening, path).toContain('aria-label=');
      expect(opening, path).toContain('aria-valuemin=');
      expect(opening, path).toContain('aria-valuemax=');
      expect(opening, path).toContain('aria-valuenow=');
    }
  });
});
