import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import MarketDataImportHistory from '@/components/dashboard/market-data-import-history';
import type { MarketDataImportRecord, Page } from '@/lib/api/types';

const mocks = vi.hoisted(() => ({
  getMarketDataImportHistory: vi.fn(),
}));

vi.mock('@/lib/api/client', () => ({
  getMarketDataImportHistory: mocks.getMarketDataImportHistory,
}));

const connectionId = 'market-data-connection-1';

const succeededRecord: MarketDataImportRecord = {
  import_id: 'market-data-import-success',
  connection_id: connectionId,
  provider_id: 'binance-public',
  dataset_name: 'BTC historical sample',
  pair: {
    base_asset: 'BTC',
    quote_asset: 'USDT',
    market_type: 'spot',
  },
  timeframe: '1h',
  requested_start_time: '2026-08-20T00:00:00Z',
  requested_end_time: '2026-08-21T00:00:00Z',
  created_at: '2026-08-31T14:00:00Z',
  completed_at: '2026-08-31T14:00:01Z',
  status: 'succeeded',
  candle_count: 24,
  dataset_id: 'dataset-1234567890abcdef',
  error_code: null,
  error_message: null,
  operation: 'import',
  source_dataset_id: null,
  root_import_id: 'market-data-import-success',
  parent_import_id: null,
  version_number: 1,
  content_changed: null,
};

const failedRecord: MarketDataImportRecord = {
  ...succeededRecord,
  import_id: 'market-data-import-failed',
  dataset_name: 'BTC incomplete sample',
  status: 'failed',
  candle_count: 23,
  dataset_id: null,
  error_code: 'quality_check_failed',
  error_message: 'Dataset failed quality checks: missing_candle',
  root_import_id: null,
  version_number: null,
};

const page: Page<MarketDataImportRecord> = {
  items: [succeededRecord, failedRecord],
  total: 2,
  limit: 5,
  offset: 0,
  count: 2,
  has_next: false,
  has_previous: false,
};

describe('MarketDataImportHistory', () => {
  beforeEach(() => {
    mocks.getMarketDataImportHistory.mockReset();
  });

  it('loads history lazily and renders success and failure lineage', async () => {
    const user = userEvent.setup();
    mocks.getMarketDataImportHistory.mockResolvedValue(page);

    render(<MarketDataImportHistory connectionId={connectionId} locale="en" />);

    expect(mocks.getMarketDataImportHistory).not.toHaveBeenCalled();
    await user.click(screen.getByRole('button', { name: 'Show import history' }));

    await waitFor(() => {
      expect(mocks.getMarketDataImportHistory).toHaveBeenCalledWith(connectionId, {
        status: undefined,
        limit: 5,
        offset: 0,
      });
    });

    expect(await screen.findByText('BTC historical sample')).toBeInTheDocument();
    expect(screen.getByText('BTC incomplete sample')).toBeInTheDocument();
    expect(screen.getByText('quality_check_failed')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'View dataset' })).toHaveAttribute(
      'href',
      '/en/datasets/dataset-1234567890abcdef',
    );
  });

  it('requests the failed-only history when the status filter changes', async () => {
    const user = userEvent.setup();
    const failedPage: Page<MarketDataImportRecord> = {
      items: [failedRecord],
      total: 1,
      limit: 5,
      offset: 0,
      count: 1,
      has_next: false,
      has_previous: false,
    };
    mocks.getMarketDataImportHistory.mockResolvedValueOnce(page).mockResolvedValueOnce(failedPage);

    render(<MarketDataImportHistory connectionId={connectionId} locale="en" />);

    await user.click(screen.getByRole('button', { name: 'Show import history' }));
    await screen.findByText('BTC historical sample');
    await user.click(screen.getByRole('button', { name: 'Failed' }));

    await waitFor(() => {
      expect(mocks.getMarketDataImportHistory).toHaveBeenLastCalledWith(connectionId, {
        status: 'failed',
        limit: 5,
        offset: 0,
      });
    });
    expect(await screen.findByText('BTC incomplete sample')).toBeInTheDocument();
  });
});
