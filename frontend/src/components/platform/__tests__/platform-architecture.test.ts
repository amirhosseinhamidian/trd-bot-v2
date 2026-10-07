import { existsSync, readFileSync, readdirSync } from 'node:fs';
import { join, relative, resolve } from 'node:path';

import { describe, expect, it } from 'vitest';

const screenComponentPaths = [
  'components/dashboard/candidate-catalog.tsx',
  'components/dashboard/candidate-detail.tsx',
  'components/dashboard/dataset-catalog.tsx',
  'components/dashboard/dataset-detail.tsx',
  'components/dashboard/experiment-catalog.tsx',
  'components/dashboard/experiment-detail.tsx',
  'components/dashboard/market-data-connections-panel.tsx',
  'features/monitoring/monitoring-dashboard.tsx',
  'components/dashboard/optimization-catalog.tsx',
  'components/dashboard/optimization-detail.tsx',
  'components/dashboard/overview-dashboard.tsx',
  'components/dashboard/portfolio-catalog.tsx',
  'components/dashboard/portfolio-detail.tsx',
  'components/dashboard/position-detail.tsx',
  'components/dashboard/risk-dashboard.tsx',
  'components/dashboard/signal-catalog.tsx',
  'components/dashboard/signal-detail.tsx',
  'components/dashboard/strategy-catalog.tsx',
  'components/dashboard/strategy-detail.tsx',
  'components/dashboard/walk-forward-catalog.tsx',
  'components/dashboard/walk-forward-detail.tsx',
] as const;

const localeRoutes = [
  'candidates/[candidateId]/page.tsx',
  'candidates/page.tsx',
  'connections/page.tsx',
  'datasets/[datasetId]/page.tsx',
  'datasets/page.tsx',
  'experiments/[experimentId]/page.tsx',
  'experiments/page.tsx',
  'monitoring/page.tsx',
  'optimizations/[executionId]/page.tsx',
  'optimizations/page.tsx',
  'page.tsx',
  'portfolios/[portfolioId]/page.tsx',
  'portfolios/[portfolioId]/positions/[positionId]/page.tsx',
  'portfolios/page.tsx',
  'risk/page.tsx',
  'signals/[experimentId]/[signalId]/page.tsx',
  'signals/page.tsx',
  'strategies/[strategyName]/[version]/page.tsx',
  'strategies/page.tsx',
  'walk-forward/[executionId]/page.tsx',
  'walk-forward/page.tsx',
].sort();

function collectPageFiles(directory: string): string[] {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const path = join(directory, entry.name);

    if (entry.isDirectory()) {
      return collectPageFiles(path);
    }

    return entry.name === 'page.tsx' ? [path] : [];
  });
}

describe('platform architecture contract', () => {
  it('uses PlatformShell without restoring legacy dashboard shell identifiers', () => {
    const layoutPath = resolve(process.cwd(), 'src/app/[locale]/layout.tsx');
    const layoutSource = readFileSync(layoutPath, 'utf8');
    const shellSource = readFileSync(
      resolve(process.cwd(), 'src/components/platform/platform-shell.tsx'),
      'utf8',
    );

    expect(existsSync(resolve(process.cwd(), 'src/components/layout/dashboard-shell.tsx'))).toBe(
      false,
    );
    expect(layoutSource).toContain('@/components/platform/platform-shell');
    expect(layoutSource).toContain('<PlatformShell');
    expect(shellSource).not.toContain('DashboardShell');
    expect(shellSource).not.toContain('getLegacyShellNavigation');
    expect(shellSource).not.toContain('dashboard-navigation');
  });

  it.each(screenComponentPaths)('keeps %s on the shared page layout contract', (path) => {
    const source = readFileSync(resolve(process.cwd(), 'src', path), 'utf8');

    expect(source).toContain('@/components/platform/page-frame');
    expect(source).toContain('@/components/platform/page-header');
    expect(source).toContain('<PageFrame');
    expect(source).toContain('<PageHeader');
    expect(source).not.toContain('<h1');
    expect(source).not.toContain('<main');
  });

  it('keeps monitoring UI and copy inside its feature boundary', () => {
    const routeSource = readFileSync(
      resolve(process.cwd(), 'src/app/[locale]/monitoring/page.tsx'),
      'utf8',
    );
    const dashboardSource = readFileSync(
      resolve(process.cwd(), 'src/features/monitoring/monitoring-dashboard.tsx'),
      'utf8',
    );
    const copySource = readFileSync(
      resolve(process.cwd(), 'src/features/monitoring/monitoring-copy.ts'),
      'utf8',
    );

    expect(routeSource).toContain('@/features/monitoring/monitoring-dashboard');
    expect(
      existsSync(resolve(process.cwd(), 'src/components/dashboard/monitoring-dashboard.tsx')),
    ).toBe(false);
    expect(existsSync(resolve(process.cwd(), 'src/components/dashboard/monitoring-copy.ts'))).toBe(
      false,
    );
    expect(dashboardSource).not.toContain('@/components/dashboard');
    expect(copySource).not.toContain('@/components/dashboard');
  });

  it('preserves the frozen 21-route locale inventory', () => {
    const localeRoot = resolve(process.cwd(), 'src/app/[locale]');
    const actualRoutes = collectPageFiles(localeRoot)
      .map((path) => relative(localeRoot, path).replaceAll('\\', '/'))
      .sort();

    expect(actualRoutes).toEqual(localeRoutes);
  });
});
