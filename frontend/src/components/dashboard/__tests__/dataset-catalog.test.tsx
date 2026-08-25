import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import DatasetCatalog from '@/components/dashboard/dataset-catalog';
import type { DatasetSummary, Page } from '@/lib/api/types';

const mocks = vi.hoisted(() => ({
  getDatasets: vi.fn(),
  filterInstance: 0,
}));

vi.mock('@/lib/api/client', () => ({
  getDatasets: mocks.getDatasets,
}));

vi.mock('@/components/dashboard/dataset-import-form', () => ({
  default: function MockDatasetImportForm({
    onImported,
  }: {
    onImported: () => Promise<void> | void;
  }) {
    return (
      <button type="button" onClick={() => void onImported()}>
        Complete dataset import
      </button>
    );
  },
}));

vi.mock('@/components/dashboard/dataset-filter-panel', async () => {
  const { useState } = await import('react');

  return {
    DEFAULT_DATASET_FILTERS: {
      source: '',
      baseAsset: '',
      quoteAsset: '',
      timeframe: 'all',
      createdAtFrom: '',
      createdAtTo: '',
      sortBy: 'created_at',
      sortDirection: 'desc',
    },
    default: function MockDatasetFilterPanel() {
      const [instance] = useState(() => {
        mocks.filterInstance += 1;
        return mocks.filterInstance;
      });

      return <div data-testid="filter-instance">{instance}</div>;
    },
  };
});

const importedDataset: DatasetSummary = {
  dataset_id: 'dataset-imported-btc',
  schema_version: 1,
  name: 'Imported BTC dataset',
  source: 'csv',
  pair: {
    base_asset: 'BTC',
    quote_asset: 'USDT',
    market_type: 'spot',
  },
  timeframe: '1h',
  start_time: '2026-08-01T00:00:00Z',
  end_time: '2026-08-01T01:00:00Z',
  created_at: '2026-08-25T12:00:00Z',
  candle_count: 2,
  checksum: 'a'.repeat(64),
};

const initialPage: Page<DatasetSummary> = {
  items: [],
  total: 0,
  limit: 12,
  offset: 0,
  count: 0,
  has_next: false,
  has_previous: false,
};

const refreshedPage: Page<DatasetSummary> = {
  items: [importedDataset],
  total: 1,
  limit: 12,
  offset: 0,
  count: 1,
  has_next: false,
  has_previous: false,
};

describe('DatasetCatalog', () => {
  beforeEach(() => {
    mocks.getDatasets.mockReset();
    mocks.filterInstance = 0;
  });

  it('reloads the first page and resets filters after an import', async () => {
    const user = userEvent.setup();

    mocks.getDatasets.mockResolvedValue(refreshedPage);

    render(<DatasetCatalog locale="en" initialPage={initialPage} />);

    expect(screen.getByTestId('filter-instance')).toHaveTextContent('1');

    await user.click(
      screen.getByRole('button', {
        name: 'Complete dataset import',
      }),
    );

    await waitFor(() => {
      expect(mocks.getDatasets).toHaveBeenCalledTimes(1);
    });

    expect(mocks.getDatasets).toHaveBeenCalledWith(
      expect.objectContaining({
        limit: 12,
        offset: 0,
        sortBy: 'created_at',
        sortDirection: 'desc',
      }),
    );

    await waitFor(() => {
      expect(screen.getByTestId('filter-instance')).toHaveTextContent('2');
    });

    expect(await screen.findByText('Imported BTC dataset')).toBeInTheDocument();

    expect(
      screen.getByRole('link', {
        name: /view/i,
      }),
    ).toHaveAttribute('href', '/en/datasets/dataset-imported-btc');
  });
});
