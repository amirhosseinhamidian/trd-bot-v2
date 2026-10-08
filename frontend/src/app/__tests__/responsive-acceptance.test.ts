import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { describe, expect, it } from 'vitest';

const TARGET_VIEWPORTS = [320, 480, 768, 1024, 1440] as const;

const platformShell = readFileSync(
  resolve(process.cwd(), 'src/components/platform/platform-shell.tsx'),
  'utf8',
);
const mobileNavigation = readFileSync(
  resolve(process.cwd(), 'src/components/platform/mobile-platform-navigation.tsx'),
  'utf8',
);
const globalsCss = readFileSync(resolve(process.cwd(), 'src/app/globals.css'), 'utf8');
const denseMetricSources = [
  'src/features/optimizations/optimization-run-form.tsx',
  'src/features/portfolios/position-detail.tsx',
  'src/features/portfolios/portfolio-detail.tsx',
].map((path) => readFileSync(resolve(process.cwd(), path), 'utf8'));

describe('P5 responsive acceptance contract', () => {
  it('covers the five required viewport widths across mobile, tablet, desktop, and wide modes', () => {
    const modes = TARGET_VIEWPORTS.map((width) => {
      if (width < 768) {
        return 'mobile';
      }

      if (width < 1024) {
        return 'tablet';
      }

      return width >= 1440 ? 'wide' : 'desktop';
    });

    expect(modes).toEqual(['mobile', 'mobile', 'tablet', 'desktop', 'wide']);
    expect(globalsCss).toMatch(/html\s*\{[\s\S]*?min-width:\s*320px;/);
    expect(mobileNavigation).toContain('md:hidden');
    expect(platformShell).toContain('md:flex lg:visible lg:translate-x-0');
    expect(platformShell).toContain('lg:ps-72');
    expect(platformShell).toContain('max-w-7xl');
  });

  it('avoids five-column content at the sidebar-constrained 1024px viewport', () => {
    for (const source of denseMetricSources) {
      expect(source).not.toMatch(/(?<!x)lg:grid-cols-5/);
    }

    expect(denseMetricSources.join('\n')).toContain('lg:grid-cols-3 xl:grid-cols-5');
  });
});
