import type { Locale } from '@/i18n/config';

/**
 * Frozen public page inventory for the Nexora UI foundation.
 *
 * Keep entries relative to `src/app/[locale]`. The architecture and release
 * readiness tests use this single contract to detect route removal, renaming,
 * duplication, or dynamic parameter drift before release.
 */
export const PRESERVED_LOCALE_ROUTE_FILES = [
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
] as const;

export function getRoutePattern(file: (typeof PRESERVED_LOCALE_ROUTE_FILES)[number]): string {
  return file === 'page.tsx' ? '' : `/${file.replace(/\/page\.tsx$/, '')}`;
}

export function getLocalizedRoutePatterns(locale: Locale): string[] {
  return PRESERVED_LOCALE_ROUTE_FILES.map((file) => `/${locale}${getRoutePattern(file)}`);
}
