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

describe('DatasetCatalog', () => {
  beforeEach(() => {
    mocks.getDatasets.mockReset();
    mocks.filterInstance = 0;
  });

  it('reloads the first page and resets filters after a successful import', async () => {
    const user = userEvent.setup();

    const initialPage = {
      items: [],
      total: 0,
      limit: 12,
      offset: 0,
    } as Page<DatasetSummary>;

    mocks.getDatasets.mockResolvedValue({
      items: [],
      total: 0,
      limit: 12,
      offset: 0,
    });

    render(<DatasetCatalog locale="en" initialPage={initialPage} />);

    expect(screen.getByTestId('filter-instance')).toHaveTextContent('1');

    await user.click(
      screen.getByRole('button', {
        name: 'Complete dataset import',
      }),
    );

    await waitFor(() => {
      expect(mocks.getDatasets).toHaveBeenCalledWith(
        expect.objectContaining({
          limit: 12,
          offset: 0,
        }),
      );
    });

    await waitFor(() => {
      expect(screen.getByTestId('filter-instance')).toHaveTextContent('2');
    });
  });
});
