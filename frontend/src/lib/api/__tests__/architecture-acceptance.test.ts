import { existsSync, readFileSync, readdirSync } from 'node:fs';
import { relative, resolve } from 'node:path';

import { describe, expect, it } from 'vitest';

const sourceRoot = resolve(process.cwd(), 'src');
const retiredFacadePaths = [
  'lib/api/client.ts',
  'lib/api/portfolio-analytics.ts',
  'lib/api/types.ts',
] as const;

function sourceFiles(directory: string, skipTests = true): string[] {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const path = resolve(directory, entry.name);

    if (entry.isDirectory()) {
      return skipTests && entry.name === '__tests__' ? [] : sourceFiles(path, skipTests);
    }

    return /\.tsx?$/.test(entry.name) ? [path] : [];
  });
}

function source(path: string): string {
  return readFileSync(resolve(sourceRoot, path), 'utf8');
}

describe('API boundary architecture acceptance', () => {
  it('owns the shared page contract only in the API core', () => {
    expect(source('lib/api/core/types.ts')).toContain('export interface Page<T>');
  });

  it('keeps retired API facades and component trees deleted', () => {
    const retiredPaths = [
      ...retiredFacadePaths,
      'components/dashboard',
      'components/language-switcher.tsx',
    ];

    expect(retiredPaths.filter((path) => existsSync(resolve(sourceRoot, path)))).toEqual([]);
  });

  it('prevents source and tests from depending on retired API facades', () => {
    const offenders = sourceFiles(sourceRoot, false)
      .map((path) => [relative(sourceRoot, path), readFileSync(path, 'utf8')] as const)
      .filter(([, contents]) =>
        /from ['"]@\/lib\/api\/(?:client|types|portfolio-analytics)['"]/.test(contents),
      )
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
