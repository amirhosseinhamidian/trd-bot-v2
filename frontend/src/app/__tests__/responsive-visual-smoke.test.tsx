import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { render, screen } from '@testing-library/react';
import { type AnchorHTMLAttributes, type ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import PlatformShell from '@/components/platform/platform-shell';
import { getResponsiveViewportMode, P6_RESPONSIVE_VIEWPORTS } from '@/platform/responsive-contract';

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
  default: () => <button type="button">Theme</button>,
}));

const criticalLayoutContracts = [
  {
    path: 'src/features/overview/overview-dashboard.tsx',
    tokens: ['sm:grid-cols-2', 'xl:grid-cols-4', 'xl:grid-cols-[1.35fr_1fr]'],
  },
  {
    path: 'src/features/datasets/dataset-catalog.tsx',
    tokens: ['md:grid-cols-2', 'xl:grid-cols-3'],
  },
  {
    path: 'src/features/datasets/dataset-detail.tsx',
    tokens: ['md:grid-cols-2', 'xl:grid-cols-4', 'scrollLabel'],
  },
  {
    path: 'src/features/experiments/experiment-detail.tsx',
    tokens: ['sm:grid-cols-2', 'lg:grid-cols-4'],
  },
  {
    path: 'src/features/walk-forward/walk-forward-detail.tsx',
    tokens: ['sm:grid-cols-2', 'lg:grid-cols-4', 'scrollLabel'],
  },
  {
    path: 'src/features/candidates/candidate-catalog.tsx',
    tokens: ['xl:grid-cols-2', 'sm:grid-cols-2'],
  },
  {
    path: 'src/features/risk/risk-dashboard.tsx',
    tokens: ['lg:grid-cols-3', 'xl:grid-cols-4'],
  },
  {
    path: 'src/features/portfolios/portfolio-detail.tsx',
    tokens: ['sm:grid-cols-2', 'xl:grid-cols-2'],
  },
  {
    path: 'src/features/connections/market-data-connections-panel.tsx',
    tokens: ['md:grid-cols-2', 'xl:grid-cols-3'],
  },
  {
    path: 'src/features/monitoring/monitoring-dashboard.tsx',
    tokens: ['md:hidden', 'hidden min-w-0 md:block', 'scrollLabel'],
  },
] as const;

function setViewportWidth(width: number): void {
  Object.defineProperty(window, 'innerWidth', {
    configurable: true,
    value: width,
  });
  window.dispatchEvent(new Event('resize'));
}

describe('P6 responsive viewport matrix', () => {
  beforeEach(() => {
    navigationState.pathname = '/en';
  });

  it('freezes the five release viewports and their breakpoint modes', () => {
    expect(P6_RESPONSIVE_VIEWPORTS).toEqual([
      { width: 360, mode: 'mobile', navigation: 'bottom-navigation', contentGutter: 16 },
      { width: 390, mode: 'mobile', navigation: 'bottom-navigation', contentGutter: 16 },
      { width: 768, mode: 'tablet', navigation: 'tablet-drawer', contentGutter: 24 },
      { width: 1024, mode: 'desktop', navigation: 'fixed-sidebar', contentGutter: 32 },
      { width: 1440, mode: 'wide', navigation: 'fixed-sidebar', contentGutter: 32 },
    ]);

    expect([767, 768, 1023, 1024, 1439, 1440].map(getResponsiveViewportMode)).toEqual([
      'mobile',
      'tablet',
      'tablet',
      'desktop',
      'desktop',
      'wide',
    ]);
  });

  it.each(P6_RESPONSIVE_VIEWPORTS)(
    'keeps the Shell contract intact at $widthpx ($mode)',
    ({ width, mode, navigation, contentGutter }) => {
      setViewportWidth(width);

      render(
        <PlatformShell locale="en">
          <div>Responsive content</div>
        </PlatformShell>,
      );

      const main = screen.getByRole('main');
      const header = screen.getByRole('banner');
      const sidebar = screen.getByRole('complementary', { name: 'Platform navigation' });
      const mobileNavigation = screen.getByRole('navigation', { name: 'Mobile navigation' });
      const drawerButton = screen.getByRole('button', { name: 'Open navigation' });

      expect(getResponsiveViewportMode(window.innerWidth)).toBe(mode);
      expect(main).toHaveClass('w-full', 'max-w-7xl', 'min-w-0', 'px-4', 'sm:px-6', 'lg:px-8');
      expect(header).toHaveClass('px-4', 'sm:px-6', 'lg:px-8');
      expect(mobileNavigation.parentElement).toHaveClass('md:hidden');
      expect(drawerButton).toHaveClass('hidden', 'md:inline-flex', 'lg:hidden');
      expect(sidebar).toHaveClass('hidden', 'md:flex', 'lg:visible', 'lg:translate-x-0');
      expect(main.parentElement).toHaveClass('min-w-0', 'lg:ps-72');

      if (navigation === 'bottom-navigation') {
        expect(mode).toBe('mobile');
        expect(contentGutter).toBe(16);
        expect(main).toHaveClass('pb-28');
      } else if (navigation === 'tablet-drawer') {
        expect(mode).toBe('tablet');
        expect(contentGutter).toBe(24);
        expect(sidebar).toHaveClass('invisible');
      } else {
        expect(['desktop', 'wide']).toContain(mode);
        expect(contentGutter).toBe(32);
        expect(sidebar).toHaveClass('lg:visible');
      }
    },
  );
});

describe('P6 critical-screen visual contracts', () => {
  it.each(criticalLayoutContracts)('keeps $path fluid across the matrix', ({ path, tokens }) => {
    const source = readFileSync(resolve(process.cwd(), path), 'utf8');

    expect(source).not.toContain('w-screen');
    expect(source).not.toContain('100vw');
    expect(source).not.toContain('overflow-x-hidden');

    for (const token of tokens) {
      expect(source).toContain(token);
    }
  });

  it('keeps chart-heavy journeys stacked on mobile with textual summaries', () => {
    const chartGroup = readFileSync(
      resolve(process.cwd(), 'src/components/charts/responsive-chart-group.tsx'),
      'utf8',
    );
    const chartConsumers = [
      'src/features/experiments/experiment-performance-charts.tsx',
      'src/features/walk-forward/walk-forward-analytics-charts.tsx',
      'src/features/portfolios/portfolio-analytics.tsx',
    ].map((path) => readFileSync(resolve(process.cwd(), path), 'utf8'));

    expect(chartGroup).toContain('md:hidden');
    expect(chartGroup).toContain("isActive ? 'block' : 'hidden md:block'");
    expect(chartGroup).toContain('{item.summary}');

    for (const source of chartConsumers) {
      expect(source).toContain('ResponsiveChartGroup');
      expect(source).toContain('summary:');
    }
  });
});
