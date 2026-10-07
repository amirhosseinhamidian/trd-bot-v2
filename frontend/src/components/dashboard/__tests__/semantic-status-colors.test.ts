import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { describe, expect, it } from 'vitest';

const migratedComponentFiles = [
  'components/charts/category-bar-chart.tsx',
  'components/charts/historical-line-chart.tsx',
  'components/dashboard/activity-feed.tsx',
  'features/candidates/candidate-comparison-panel.tsx',
  'components/dashboard/dataset-detail.tsx',
  'components/dashboard/dataset-import-form.tsx',
  'components/dashboard/dataset-version-history.tsx',
  'components/dashboard/experiment-acceptance-panel.tsx',
  'components/dashboard/experiment-analytics.tsx',
  'components/dashboard/experiment-comparison-panel.tsx',
  'components/dashboard/experiment-replay-panel.tsx',
  'components/dashboard/experiment-run-form.tsx',
  'components/dashboard/historical-dataset-import-form.tsx',
  'components/dashboard/market-data-connections-panel.tsx',
  'components/dashboard/market-data-import-history.tsx',
  'features/monitoring/monitoring-dashboard.tsx',
  'components/dashboard/optimization-detail.tsx',
  'components/dashboard/optimization-run-form.tsx',
  'components/dashboard/overview-dashboard.tsx',
  'components/dashboard/portfolio-analytics.tsx',
  'components/dashboard/portfolio-catalog.tsx',
  'components/dashboard/portfolio-detail.tsx',
  'components/dashboard/position-detail.tsx',
  'features/risk/risk-dashboard.tsx',
  'components/dashboard/walk-forward-catalog.tsx',
  'components/dashboard/walk-forward-run-form.tsx',
  'components/language-switcher.tsx',
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
