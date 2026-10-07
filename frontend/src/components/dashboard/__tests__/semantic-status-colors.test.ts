import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { describe, expect, it } from 'vitest';

const migratedFiles = [
  'activity-feed.tsx',
  'dataset-detail.tsx',
  'dataset-import-form.tsx',
  'dataset-version-history.tsx',
  'experiment-acceptance-panel.tsx',
  'experiment-comparison-panel.tsx',
  'experiment-replay-panel.tsx',
  'experiment-run-form.tsx',
  'historical-dataset-import-form.tsx',
  'market-data-connections-panel.tsx',
  'market-data-import-history.tsx',
  'optimization-detail.tsx',
  'optimization-run-form.tsx',
  'walk-forward-catalog.tsx',
  'walk-forward-run-form.tsx',
] as const;

const rawStatusColor =
  /(?:bg|border|fill|ring|stroke|text)-(?:amber|emerald|green|orange|red|rose|yellow)-\d{2,3}(?:\/\d{1,3})?/;

describe('dashboard semantic status color contract', () => {
  it.each(migratedFiles)('keeps %s free of raw status palette utilities', (fileName) => {
    const source = readFileSync(
      resolve(process.cwd(), 'src/components/dashboard', fileName),
      'utf8',
    );

    expect(source).not.toMatch(rawStatusColor);
  });
});
