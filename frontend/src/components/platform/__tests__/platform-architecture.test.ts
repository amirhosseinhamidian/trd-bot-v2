import { existsSync, readFileSync, readdirSync } from 'node:fs';
import { join, relative, resolve } from 'node:path';

import { describe, expect, it } from 'vitest';

const screenComponentFiles = [
  'candidate-catalog.tsx',
  'candidate-detail.tsx',
  'dataset-catalog.tsx',
  'dataset-detail.tsx',
  'experiment-catalog.tsx',
  'experiment-detail.tsx',
  'market-data-connections-panel.tsx',
  'monitoring-dashboard.tsx',
  'optimization-catalog.tsx',
  'optimization-detail.tsx',
  'overview-dashboard.tsx',
  'portfolio-catalog.tsx',
  'portfolio-detail.tsx',
  'position-detail.tsx',
  'risk-dashboard.tsx',
  'signal-catalog.tsx',
  'signal-detail.tsx',
  'strategy-catalog.tsx',
  'strategy-detail.tsx',
  'walk-forward-catalog.tsx',
  'walk-forward-detail.tsx',
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

describe('Phase 2 platform architecture contract', () => {
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

  it.each(screenComponentFiles)('keeps %s on the shared page layout contract', (fileName) => {
    const source = readFileSync(
      resolve(process.cwd(), 'src/components/dashboard', fileName),
      'utf8',
    );

    expect(source).toContain('@/components/platform/page-frame');
    expect(source).toContain('@/components/platform/page-header');
    expect(source).toContain('<PageFrame');
    expect(source).toContain('<PageHeader');
    expect(source).not.toContain('<h1');
    expect(source).not.toContain('<main');
  });

  it('preserves the frozen 21-route locale inventory', () => {
    const localeRoot = resolve(process.cwd(), 'src/app/[locale]');
    const actualRoutes = collectPageFiles(localeRoot)
      .map((path) => relative(localeRoot, path).replaceAll('\\', '/'))
      .sort();

    expect(actualRoutes).toEqual(localeRoutes);
  });
});
