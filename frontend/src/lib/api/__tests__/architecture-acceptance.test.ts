import { readFileSync, readdirSync } from 'node:fs';
import { relative, resolve } from 'node:path';

import { describe, expect, it } from 'vitest';

const sourceRoot = resolve(process.cwd(), 'src');
const legacyFacadePaths = new Set([
  'lib/api/client.ts',
  'lib/api/portfolio-analytics.ts',
  'lib/api/types.ts',
]);

function sourceFiles(directory: string): string[] {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const path = resolve(directory, entry.name);

    if (entry.isDirectory()) {
      return entry.name === '__tests__' ? [] : sourceFiles(path);
    }

    return /\.tsx?$/.test(entry.name) ? [path] : [];
  });
}

function source(path: string): string {
  return readFileSync(resolve(sourceRoot, path), 'utf8');
}

describe('API boundary architecture acceptance', () => {
  it('owns the shared page contract in the API core and preserves its legacy alias', () => {
    const coreTypesSource = source('lib/api/core/types.ts');
    const legacyTypesSource = source('lib/api/types.ts');

    expect(coreTypesSource).toContain('export interface Page<T>');
    expect(legacyTypesSource).toContain("export type { Page } from '@/lib/api/core/types'");
    expect(legacyTypesSource).not.toContain('export interface Page<T>');
  });

  it('keeps the legacy API facades declarative-only', () => {
    const clientSource = source('lib/api/client.ts');
    const typesSource = source('lib/api/types.ts');
    const analyticsSource = source('lib/api/portfolio-analytics.ts');

    expect(clientSource).not.toMatch(/^import\s/m);
    expect(clientSource).not.toMatch(/\/api\/v1\//);
    expect(clientSource).not.toMatch(/\b(?:async\s+)?function\b/);
    expect(typesSource).not.toMatch(/^export interface\s/m);
    expect(typesSource).not.toMatch(/^export type\s+\w+\s*=/m);
    expect(analyticsSource).not.toMatch(/^export interface\s/m);
    expect(analyticsSource).not.toMatch(/^export type\s+\w+\s*=/m);
  });

  it('prevents production code from depending on legacy API facades', () => {
    const offenders = sourceFiles(sourceRoot)
      .map((path) => [relative(sourceRoot, path), readFileSync(path, 'utf8')] as const)
      .filter(([path, contents]) => {
        if (legacyFacadePaths.has(path)) return false;

        return /from ['"]@\/lib\/api\/(?:client|types|portfolio-analytics)['"]/.test(contents);
      })
      .map(([path]) => path);

    expect(offenders).toEqual([]);
  });

  it('keeps API endpoint literals inside feature-owned clients', () => {
    const offenders = sourceFiles(sourceRoot)
      .map((path) => [relative(sourceRoot, path), readFileSync(path, 'utf8')] as const)
      .filter(([path, contents]) => {
        if (!contents.includes('/api/v1/')) return false;

        return !/^features\/[^/]+\/api\/client\.ts$/.test(path);
      })
      .map(([path]) => path);

    expect(offenders).toEqual([]);
  });
});
