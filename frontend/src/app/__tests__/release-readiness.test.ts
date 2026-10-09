import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { describe, expect, it } from 'vitest';

import { locales } from '@/i18n/config';
import {
  getLocalizedRoutePatterns,
  getRoutePattern,
  PRESERVED_LOCALE_ROUTE_FILES,
} from '@/platform/route-contract';

const dynamicRoutePatterns = [
  '/candidates/[candidateId]',
  '/datasets/[datasetId]',
  '/experiments/[experimentId]',
  '/optimizations/[executionId]',
  '/portfolios/[portfolioId]',
  '/portfolios/[portfolioId]/positions/[positionId]',
  '/signals/[experimentId]/[signalId]',
  '/strategies/[strategyName]/[version]',
  '/walk-forward/[executionId]',
] as const;

describe('P6 release route contract', () => {
  it('expands the 21 frozen pages into 42 unique fa/en route patterns', () => {
    const localizedRoutes = locales.flatMap((locale) => getLocalizedRoutePatterns(locale));

    expect(locales).toEqual(['fa', 'en']);
    expect(PRESERVED_LOCALE_ROUTE_FILES).toHaveLength(21);
    expect(new Set(PRESERVED_LOCALE_ROUTE_FILES).size).toBe(21);
    expect(localizedRoutes).toHaveLength(42);
    expect(new Set(localizedRoutes).size).toBe(42);
    expect(localizedRoutes).toContain('/fa');
    expect(localizedRoutes).toContain('/en');
  });

  it('preserves every public dynamic parameter name', () => {
    const actualDynamicRoutes = PRESERVED_LOCALE_ROUTE_FILES.map(getRoutePattern)
      .filter((pattern) => pattern.includes('['))
      .sort();

    expect(actualDynamicRoutes).toEqual([...dynamicRoutePatterns].sort());
  });

  it.each(PRESERVED_LOCALE_ROUTE_FILES)('keeps the invalid-locale guard on %s', (file) => {
    const source = readFileSync(resolve(process.cwd(), 'src/app/[locale]', file), 'utf8');

    expect(source).toContain("locale !== 'fa' && locale !== 'en'");
    expect(source).toContain('notFound()');
  });

  it('keeps unprefixed requests on the configured default-locale redirect', () => {
    const proxySource = readFileSync(resolve(process.cwd(), 'src/proxy.ts'), 'utf8');

    expect(proxySource).toContain("import { defaultLocale, locales } from '@/i18n/config'");
    expect(proxySource).toContain('pathname === `/${locale}`');
    expect(proxySource).toContain('pathname.startsWith(`/${locale}/`)');
    expect(proxySource).toContain('redirectUrl.pathname = `/${defaultLocale}${pathname}`');
  });
});

describe('P6 final freeze gate', () => {
  it('keeps the frontend version aligned with the repository release version', () => {
    const packageJson = JSON.parse(
      readFileSync(resolve(process.cwd(), 'package.json'), 'utf8'),
    ) as { version: string };
    const pyproject = readFileSync(resolve(process.cwd(), '../pyproject.toml'), 'utf8');
    const backendVersion = pyproject.match(/^version = "([^"]+)"$/m)?.[1];

    expect(packageJson.version).toBe('0.2.0');
    expect(backendVersion).toBe(packageJson.version);
  });

  it('runs the explicit TypeScript gate on refactor branch pushes', () => {
    const packageJson = JSON.parse(
      readFileSync(resolve(process.cwd(), 'package.json'), 'utf8'),
    ) as { scripts: Record<string, string> };
    const workflow = readFileSync(resolve(process.cwd(), '../.github/workflows/ci.yml'), 'utf8');

    expect(packageJson.scripts.typecheck).toBe(
      'tsc --noEmit --noUnusedLocals --noUnusedParameters',
    );
    expect(workflow).toContain("- 'refactor/**'");
    expect(workflow).toContain('run: npm run typecheck');
  });

  it('publishes the frozen compatibility and migration boundary', () => {
    const releaseNotes = readFileSync(
      resolve(process.cwd(), '../docs/nexora-ui-release-and-migration.md'),
      'utf8',
    );

    expect(releaseNotes).toContain('Status: **Frozen after P6 acceptance**');
    expect(releaseNotes).toContain('## Compatibility contract');
    expect(releaseNotes).toContain('## Migration notes');
    expect(releaseNotes).toContain('## Known boundaries');
    expect(releaseNotes).toContain('## Freeze gate');
  });
});
