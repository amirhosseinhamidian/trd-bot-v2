import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import DatasetVersionHistory from '@/components/dashboard/dataset-version-history';
import type { MarketDataImportRecord, Page } from '@/lib/api/types';

const mocks = vi.hoisted(() => ({
  getMarketDataImportVersions: vi.fn(),
  refreshMarketDataImport: vi.fn(),
}));

vi.mock('@/lib/api/client', () => ({
  getMarketDataImportVersions: mocks.getMarketDataImportVersions,
  refreshMarketDataImport: mocks.refreshMarketDataImport,
}));

const connectionId = 'market-data-connection-1';
const currentDatasetId = 'dataset-root';

const root: MarketDataImportRecord = {
  import_id: 'market-data-import-root',
  connection_id: connectionId,
  provider_id: 'synthetic-public',
  dataset_name: 'BTC history',
  pair: {
    base_asset: 'BTC',
    quote_asset: 'USDT',
    market_type: 'spot',
  },
  timeframe: '1h',
  requested_start_time: '2026-08-20T10:00:00Z',
  requested_end_time: '2026-08-20T14:00:00Z',
  created_at: '2026-08-31T12:00:00Z',
  completed_at: '2026-08-31T12:00:01Z',
  status: 'succeeded',
  candle_count: 2,
  dataset_id: currentDatasetId,
  error_code: null,
  error_message: null,
  operation: 'import',
  source_dataset_id: null,
  root_import_id: 'market-data-import-root',
  parent_import_id: null,
  version_number: 1,
  content_changed: null,
};

const refreshed: MarketDataImportRecord = {
  ...root,
  import_id: 'market-data-import-refresh',
  dataset_id: 'dataset-refreshed',
  operation: 'refresh',
  source_dataset_id: currentDatasetId,
  parent_import_id: root.import_id,
  version_number: 2,
  content_changed: true,
};

function versionPage(items: MarketDataImportRecord[]): Page<MarketDataImportRecord> {
  return {
    items,
    total: items.length,
    limit: 5,
    offset: 0,
    count: items.length,
    has_next: false,
    has_previous: false,
  };
}

describe('DatasetVersionHistory', () => {
  beforeEach(() => {
    mocks.getMarketDataImportVersions.mockReset();
    mocks.refreshMarketDataImport.mockReset();
  });

  it('loads history lazily and refreshes the latest successful version', async () => {
    const user = userEvent.setup();
    const initialPage = versionPage([root]);
    const refreshedPage = versionPage([refreshed, root]);

    mocks.getMarketDataImportVersions
      .mockResolvedValueOnce(initialPage)
      .mockResolvedValueOnce(initialPage)
      .mockResolvedValueOnce(refreshedPage);
    mocks.refreshMarketDataImport.mockResolvedValue(refreshed);

    render(
      <DatasetVersionHistory
        connectionId={connectionId}
        importId={root.import_id}
        currentDatasetId={currentDatasetId}
        locale="en"
      />,
    );

    expect(mocks.getMarketDataImportVersions).not.toHaveBeenCalled();

    await user.click(screen.getByRole('button', { name: 'Load version history' }));

    await waitFor(() => {
      expect(mocks.getMarketDataImportVersions).toHaveBeenCalledWith(connectionId, root.import_id, {
        limit: 5,
        offset: 0,
      });
    });

    expect(await screen.findByText('Version 1')).toBeInTheDocument();
    expect(screen.getByText('Initial import')).toBeInTheDocument();
    expect(screen.getByText('Current snapshot')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Refresh latest version' }));

    await waitFor(() => {
      expect(mocks.refreshMarketDataImport).toHaveBeenCalledWith(connectionId, root.import_id);
    });

    expect(await screen.findByText('Version 2')).toBeInTheDocument();
    expect(screen.getAllByText('Content changed').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByRole('link', { name: 'Open new snapshot' })).toHaveAttribute(
      'href',
      '/en/datasets/dataset-refreshed',
    );
  });
});
