import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

import { describe, expect, it } from 'vitest';

import {
  createMarketDataConnection,
  disableMarketDataConnection,
  enableMarketDataConnection,
  enqueueHistoricalDatasetImport,
  enqueueMarketDataImportRefresh,
  getMarketDataConnections,
  getMarketDataImport,
  getMarketDataImportHistory,
  getMarketDataImportVersions,
  getMarketDataProviders,
  importHistoricalDataset,
  previewHistoricalDatasetImport,
  refreshMarketDataImport,
  testMarketDataConnection,
} from '@/features/connections/api/client';
import {
  createMarketDataConnection as createMarketDataConnectionFacade,
  disableMarketDataConnection as disableMarketDataConnectionFacade,
  enableMarketDataConnection as enableMarketDataConnectionFacade,
  enqueueHistoricalDatasetImport as enqueueHistoricalDatasetImportFacade,
  enqueueMarketDataImportRefresh as enqueueMarketDataImportRefreshFacade,
  getMarketDataConnections as getMarketDataConnectionsFacade,
  getMarketDataImport as getMarketDataImportFacade,
  getMarketDataImportHistory as getMarketDataImportHistoryFacade,
  getMarketDataImportVersions as getMarketDataImportVersionsFacade,
  getMarketDataProviders as getMarketDataProvidersFacade,
  importHistoricalDataset as importHistoricalDatasetFacade,
  previewHistoricalDatasetImport as previewHistoricalDatasetImportFacade,
  refreshMarketDataImport as refreshMarketDataImportFacade,
  testMarketDataConnection as testMarketDataConnectionFacade,
} from '@/lib/api/client';

describe('connections API boundary', () => {
  it('keeps the legacy client facade mapped to the feature-owned adapter', () => {
    expect(getMarketDataProvidersFacade).toBe(getMarketDataProviders);
    expect(getMarketDataConnectionsFacade).toBe(getMarketDataConnections);
    expect(createMarketDataConnectionFacade).toBe(createMarketDataConnection);
    expect(testMarketDataConnectionFacade).toBe(testMarketDataConnection);
    expect(enableMarketDataConnectionFacade).toBe(enableMarketDataConnection);
    expect(disableMarketDataConnectionFacade).toBe(disableMarketDataConnection);
    expect(previewHistoricalDatasetImportFacade).toBe(previewHistoricalDatasetImport);
    expect(importHistoricalDatasetFacade).toBe(importHistoricalDataset);
    expect(enqueueHistoricalDatasetImportFacade).toBe(enqueueHistoricalDatasetImport);
    expect(getMarketDataImportHistoryFacade).toBe(getMarketDataImportHistory);
    expect(getMarketDataImportFacade).toBe(getMarketDataImport);
    expect(getMarketDataImportVersionsFacade).toBe(getMarketDataImportVersions);
    expect(refreshMarketDataImportFacade).toBe(refreshMarketDataImport);
    expect(enqueueMarketDataImportRefreshFacade).toBe(enqueueMarketDataImportRefresh);
  });

  it('keeps connection endpoints and type definitions outside the legacy facades', () => {
    const clientSource = readFileSync(resolve(process.cwd(), 'src/lib/api/client.ts'), 'utf8');
    const typesSource = readFileSync(resolve(process.cwd(), 'src/lib/api/types.ts'), 'utf8');
    const connectionClientSource = readFileSync(
      resolve(process.cwd(), 'src/features/connections/api/client.ts'),
      'utf8',
    );
    const connectionTypesSource = readFileSync(
      resolve(process.cwd(), 'src/features/connections/api/types.ts'),
      'utf8',
    );

    expect(clientSource).not.toContain('/api/v1/market-data');
    expect(clientSource).toContain("from '@/features/connections/api/client'");
    expect(typesSource).not.toContain('export interface MarketDataConnection');
    expect(typesSource).toContain("from '@/features/connections/api/types'");
    expect(connectionClientSource).not.toContain('@/lib/api/client');
    expect(connectionTypesSource).not.toContain('@/lib/api/types');
  });
});
