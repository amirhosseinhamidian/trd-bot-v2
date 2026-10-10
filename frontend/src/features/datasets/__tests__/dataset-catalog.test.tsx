import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import DatasetCatalog from '@/features/datasets/dataset-catalog';
import type { DatasetSummary } from '@/features/datasets/api/types';
import type { Page } from '@/lib/api/core/types';

const mocks = vi.hoisted(() => ({
  getDatasets: vi.fn(),
  filterInstance: 0,
}));

vi.mock('@/features/datasets/api/client', () => ({
  getDatasets: mocks.getDatasets,
}));

vi.mock('@/features/datasets/dataset-import-form', () => ({
  default: function MockDatasetImportForm() {
    return <div>Dataset import form</div>;
  },
}));

vi.mock('@/features/datasets/dataset-filter-panel', async () => {
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

const initialPage: Page<DatasetSummary> = {
  items: [],
  total: 0,
  limit: 12,
  offset: 0,
  count: 0,
  has_next: false,
  has_previous: false,
};

describe('DatasetCatalog', () => {
  beforeEach(() => {
    mocks.getDatasets.mockReset();
    mocks.filterInstance = 0;
  });

  it('keeps the catalog stable while a durable file import runs', () => {
    render(<DatasetCatalog locale="en" initialPage={initialPage} />);

    expect(screen.getByText('Dataset import form')).toBeInTheDocument();
    expect(screen.getByTestId('filter-instance')).toHaveTextContent('1');
    expect(mocks.getDatasets).not.toHaveBeenCalled();
  });
});
