import { existsSync, readFileSync, readdirSync } from 'node:fs';
import { join, relative, resolve } from 'node:path';

import { describe, expect, it } from 'vitest';

const screenComponentPaths = [
  'features/candidates/candidate-catalog.tsx',
  'features/candidates/candidate-detail.tsx',
  'features/datasets/dataset-catalog.tsx',
  'features/datasets/dataset-detail.tsx',
  'features/experiments/experiment-catalog.tsx',
  'features/experiments/experiment-detail.tsx',
  'features/connections/market-data-connections-panel.tsx',
  'features/monitoring/monitoring-dashboard.tsx',
  'components/dashboard/optimization-catalog.tsx',
  'components/dashboard/optimization-detail.tsx',
  'components/dashboard/overview-dashboard.tsx',
  'features/portfolios/portfolio-catalog.tsx',
  'features/portfolios/portfolio-detail.tsx',
  'features/portfolios/position-detail.tsx',
  'features/risk/risk-dashboard.tsx',
  'features/signals/signal-catalog.tsx',
  'features/signals/signal-detail.tsx',
  'features/strategies/strategy-catalog.tsx',
  'features/strategies/strategy-detail.tsx',
  'features/walk-forward/walk-forward-catalog.tsx',
  'features/walk-forward/walk-forward-detail.tsx',
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

const featureBoundaries = [
  [
    'candidates',
    [
      ['candidates', 'candidate-catalog'],
      ['candidates/[candidateId]', 'candidate-detail'],
    ],
    'candidate-copy',
  ],
  ['connections', [['connections', 'market-data-connections-panel']], 'connections-copy'],
  [
    'datasets',
    [
      ['datasets', 'dataset-catalog'],
      ['datasets/[datasetId]', 'dataset-detail'],
    ],
    'datasets-copy',
  ],
  [
    'experiments',
    [
      ['experiments', 'experiment-catalog'],
      ['experiments/[experimentId]', 'experiment-detail'],
    ],
    'experiments-copy',
  ],
  ['monitoring', [['monitoring', 'monitoring-dashboard']], 'monitoring-copy'],
  [
    'portfolios',
    [
      ['portfolios', 'portfolio-catalog'],
      ['portfolios/[portfolioId]', 'portfolio-detail'],
      ['portfolios/[portfolioId]/positions/[positionId]', 'position-detail'],
    ],
    'portfolio-copy',
  ],
  ['risk', [['risk', 'risk-dashboard']], 'risk-copy'],
  [
    'signals',
    [
      ['signals', 'signal-catalog'],
      ['signals/[experimentId]/[signalId]', 'signal-detail'],
    ],
    'signals-copy',
  ],
  [
    'strategies',
    [
      ['strategies', 'strategy-catalog'],
      ['strategies/[strategyName]/[version]', 'strategy-detail'],
    ],
    'strategy-workspace-copy',
  ],
  [
    'walk-forward',
    [
      ['walk-forward', 'walk-forward-catalog'],
      ['walk-forward/[executionId]', 'walk-forward-detail'],
    ],
    'walk-forward-copy',
  ],
] as const;

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

  it.each(featureBoundaries)(
    'keeps %s UI and copy inside its feature boundary',
    (feature, screens, copy) => {
      const copySource = readFileSync(
        resolve(process.cwd(), `src/features/${feature}/${copy}.ts`),
        'utf8',
      );

      for (const [route, screen] of screens) {
        const routeSource = readFileSync(
          resolve(process.cwd(), `src/app/[locale]/${route}/page.tsx`),
          'utf8',
        );
        const screenSource = readFileSync(
          resolve(process.cwd(), `src/features/${feature}/${screen}.tsx`),
          'utf8',
        );

        expect(routeSource).toContain(`@/features/${feature}/${screen}`);
        expect(existsSync(resolve(process.cwd(), `src/components/dashboard/${screen}.tsx`))).toBe(
          false,
        );
        expect(screenSource).not.toContain('@/components/dashboard');
      }

      expect(existsSync(resolve(process.cwd(), `src/components/dashboard/${copy}.ts`))).toBe(false);
      expect(copySource).not.toContain('@/components/dashboard');
    },
  );

  it('preserves the frozen 21-route locale inventory', () => {
    const localeRoot = resolve(process.cwd(), 'src/app/[locale]');
    const actualRoutes = collectPageFiles(localeRoot)
      .map((path) => relative(localeRoot, path).replaceAll('\\', '/'))
      .sort();

    expect(actualRoutes).toEqual(localeRoutes);
  });
});
