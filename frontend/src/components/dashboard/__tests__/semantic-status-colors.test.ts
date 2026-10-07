import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { describe, expect, it } from 'vitest';

const migratedComponentFiles = [
  'charts/category-bar-chart.tsx',
  'charts/historical-line-chart.tsx',
  'dashboard/activity-feed.tsx',
  'dashboard/candidate-comparison-panel.tsx',
  'dashboard/dataset-detail.tsx',
  'dashboard/dataset-import-form.tsx',
  'dashboard/dataset-version-history.tsx',
  'dashboard/experiment-acceptance-panel.tsx',
  'dashboard/experiment-analytics.tsx',
  'dashboard/experiment-comparison-panel.tsx',
  'dashboard/experiment-replay-panel.tsx',
  'dashboard/experiment-run-form.tsx',
  'dashboard/historical-dataset-import-form.tsx',
  'dashboard/market-data-connections-panel.tsx',
  'dashboard/market-data-import-history.tsx',
  'dashboard/monitoring-dashboard.tsx',
  'dashboard/optimization-detail.tsx',
  'dashboard/optimization-run-form.tsx',
  'dashboard/overview-dashboard.tsx',
  'dashboard/portfolio-analytics.tsx',
  'dashboard/portfolio-catalog.tsx',
  'dashboard/portfolio-detail.tsx',
  'dashboard/position-detail.tsx',
  'dashboard/risk-dashboard.tsx',
  'dashboard/walk-forward-catalog.tsx',
  'dashboard/walk-forward-run-form.tsx',
  'language-switcher.tsx',
  'platform/mobile-platform-navigation.tsx',
  'platform/page-frame.tsx',
  'platform/page-header.tsx',
  'platform/platform-shell.tsx',
  'ui/select.tsx',
] as const;

const rawPaletteUtility =
  /(?:bg|border|fill|ring|shadow|stroke|text)-(?:amber|black|blue|cyan|emerald|fuchsia|gray|green|indigo|lime|neutral|orange|pink|purple|red|rose|sky|slate|stone|teal|violet|white|yellow)(?:-\d{2,3})?(?:\/\d{1,3})?/;
const rawHexColor = /#[\da-f]{3,8}/i;

describe('component semantic color contract', () => {
  it.each(migratedComponentFiles)('keeps %s free of raw palette colors', (fileName) => {
    const source = readFileSync(resolve(process.cwd(), 'src/components', fileName), 'utf8');

    expect(source).not.toMatch(rawPaletteUtility);
    expect(source).not.toMatch(rawHexColor);
  });
});
