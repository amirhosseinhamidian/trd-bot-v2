import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { describe, expect, it } from 'vitest';

const migratedComponentFiles = [
  'components/charts/category-bar-chart.tsx',
  'components/charts/historical-line-chart.tsx',
  'features/overview/activity-feed.tsx',
  'features/candidates/candidate-comparison-panel.tsx',
  'features/datasets/dataset-detail.tsx',
  'features/datasets/dataset-import-form.tsx',
  'features/datasets/dataset-version-history.tsx',
  'features/experiments/experiment-acceptance-panel.tsx',
  'features/experiments/experiment-analytics.tsx',
  'features/experiments/experiment-comparison-panel.tsx',
  'features/experiments/experiment-replay-panel.tsx',
  'features/experiments/experiment-run-form.tsx',
  'features/connections/historical-dataset-import-form.tsx',
  'features/connections/market-data-connections-panel.tsx',
  'features/connections/market-data-import-history.tsx',
  'features/monitoring/monitoring-dashboard.tsx',
  'features/optimizations/optimization-detail.tsx',
  'features/optimizations/optimization-run-form.tsx',
  'features/overview/overview-dashboard.tsx',
  'features/portfolios/portfolio-analytics.tsx',
  'features/portfolios/portfolio-catalog.tsx',
  'features/portfolios/portfolio-detail.tsx',
  'features/portfolios/position-detail.tsx',
  'features/risk/risk-dashboard.tsx',
  'features/walk-forward/walk-forward-catalog.tsx',
  'features/walk-forward/walk-forward-run-form.tsx',
  'components/platform/mobile-platform-navigation.tsx',
  'components/platform/page-frame.tsx',
  'components/platform/page-header.tsx',
  'components/platform/platform-shell.tsx',
  'components/ui/select.tsx',
] as const;

const rawPaletteUtility =
  /(?:bg|border|fill|ring|shadow|stroke|text)-(?:amber|black|blue|cyan|emerald|fuchsia|gray|green|indigo|lime|neutral|orange|pink|purple|red|rose|sky|slate|stone|teal|violet|white|yellow)(?:-\d{2,3})?(?:\/\d{1,3})?/;
const rawHexColor = /#[\da-f]{3,8}/i;

describe('component semantic color contract', () => {
  it.each(migratedComponentFiles)('keeps %s free of raw palette colors', (fileName) => {
    const source = readFileSync(resolve(process.cwd(), 'src', fileName), 'utf8');

    expect(source).not.toMatch(rawPaletteUtility);
    expect(source).not.toMatch(rawHexColor);
  });
});
