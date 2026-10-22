import { readFileSync, readdirSync } from 'node:fs';
import { relative, resolve } from 'node:path';

import { describe, expect, it } from 'vitest';

const sourceRoot = resolve(process.cwd(), 'src');
const testOnlyContracts = new Set([
  'platform/responsive-contract.ts',
  'platform/route-contract.ts',
]);
const importPattern = /(?:from\s+|import\s*(?:\(\s*)?)[`'"]([^`'"]+)[`'"]/g;

function productionSourceFiles(directory: string): string[] {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const path = resolve(directory, entry.name);

    if (entry.isDirectory()) {
      return entry.name === '__tests__' || entry.name === 'test' ? [] : productionSourceFiles(path);
    }

    return /\.tsx?$/.test(entry.name) ? [path] : [];
  });
}

function resolveSourceImport(
  importer: string,
  specifier: string,
  sourceFiles: Set<string>,
): string | null {
  const basePath = specifier.startsWith('@/')
    ? resolve(sourceRoot, specifier.slice(2))
    : specifier.startsWith('.')
      ? resolve(importer, '..', specifier)
      : null;

  if (basePath === null) return null;

  const candidates = [
    basePath,
    `${basePath}.ts`,
    `${basePath}.tsx`,
    resolve(basePath, 'index.ts'),
    resolve(basePath, 'index.tsx'),
  ];

  return candidates.find((candidate) => sourceFiles.has(candidate)) ?? null;
}

describe('dead-code acceptance', () => {
  it('keeps every production module reachable from a Next entry point', () => {
    const files = new Set(productionSourceFiles(sourceRoot));
    const dependencies = new Map<string, Set<string>>();

    for (const file of files) {
      const imports = [...readFileSync(file, 'utf8').matchAll(importPattern)]
        .map((match) => resolveSourceImport(file, match[1], files))
        .filter((dependency): dependency is string => dependency !== null);

      dependencies.set(file, new Set(imports));
    }

    const reachable = new Set<string>();
    const pending = [...files].filter((file) => {
      const path = relative(sourceRoot, file);
      return path.startsWith('app/') || path === 'proxy.ts';
    });

    while (pending.length > 0) {
      const file = pending.pop();
      if (file === undefined || reachable.has(file)) continue;

      reachable.add(file);
      pending.push(...(dependencies.get(file) ?? []));
    }

    const orphanedModules = [...files]
      .map((file) => relative(sourceRoot, file))
      .filter((file) => !reachable.has(resolve(sourceRoot, file)))
      .filter((file) => !testOnlyContracts.has(file))
      .sort();

    expect(orphanedModules).toEqual([]);
  });
});
