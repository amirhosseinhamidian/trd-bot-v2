import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { describe, expect, it } from 'vitest';

import { getExperimentSignal, getExperimentSignals } from '@/features/signals/api/client';
import {
  getExperimentSignal as getExperimentSignalFacade,
  getExperimentSignals as getExperimentSignalsFacade,
} from '@/lib/api/client';

describe('signals API boundary', () => {
  it('keeps the legacy client facade mapped to the feature-owned adapter', () => {
    expect(getExperimentSignalsFacade).toBe(getExperimentSignals);
    expect(getExperimentSignalFacade).toBe(getExperimentSignal);
  });

  it('keeps signal ownership outside the legacy facades', () => {
    const clientSource = readFileSync(resolve(process.cwd(), 'src/lib/api/client.ts'), 'utf8');
    const typesSource = readFileSync(resolve(process.cwd(), 'src/lib/api/types.ts'), 'utf8');
    const signalClientSource = readFileSync(
      resolve(process.cwd(), 'src/features/signals/api/client.ts'),
      'utf8',
    );
    const signalTypesSource = readFileSync(
      resolve(process.cwd(), 'src/features/signals/api/types.ts'),
      'utf8',
    );

    expect(clientSource).not.toContain('/signals?${params.toString()}');
    expect(clientSource).not.toContain('/signals/${encodedSignalId}');
    expect(clientSource).toContain("from '@/features/signals/api/client'");
    expect(typesSource).not.toContain('export interface StrategySignal');
    expect(typesSource).not.toContain("export type SignalDirection = 'long'");
    expect(typesSource).toContain("from '@/features/signals/api/types'");
    expect(signalClientSource).not.toContain('@/lib/api/client');
    expect(signalTypesSource).not.toContain('@/lib/api/types');
  });
});
