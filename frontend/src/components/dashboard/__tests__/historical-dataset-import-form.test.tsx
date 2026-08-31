import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import HistoricalDatasetImportForm from '@/components/dashboard/historical-dataset-import-form';
import type {
  DatasetSummary,
  HistoricalDatasetImportPreview,
  MarketDataConnection,
  MarketDataProviderSummary,
} from '@/lib/api/types';

const mocks = vi.hoisted(() => ({
  importHistoricalDataset: vi.fn(),
  previewHistoricalDatasetImport: vi.fn(),
}));

vi.mock('@/lib/api/client', () => ({
  importHistoricalDataset: mocks.importHistoricalDataset,
  previewHistoricalDatasetImport: mocks.previewHistoricalDatasetImport,
}));

const connection: MarketDataConnection = {
  connection_id: 'market-data-connection-1',
  provider_id: 'binance-public',
  display_name: 'Historical feed',
  state: 'enabled',
  health_status: 'healthy',
  created_at: '2026-08-31T12:00:00Z',
  updated_at: '2026-08-31T12:05:00Z',
  last_tested_at: '2026-08-31T12:05:00Z',
  last_error: null,
};

const provider: MarketDataProviderSummary = {
  provider_id: 'binance-public',
  display_name: 'Binance Public Market Data',
  requires_credentials: false,
  supported_market_types: ['spot'],
  supported_timeframes: ['1h', '4h'],
};

const preview: HistoricalDatasetImportPreview = {
  connection_id: connection.connection_id,
  provider_id: provider.provider_id,
  name: 'BTC August sample',
  pair: {
    base_asset: 'BTC',
    quote_asset: 'USDT',
    market_type: 'spot',
  },
  timeframe: '1h',
  requested_start_time: '2026-08-20T00:00:00Z',
  requested_end_time: '2026-08-21T00:00:00Z',
  candle_count: 24,
  first_open_time: '2026-08-20T00:00:00Z',
  last_close_time: '2026-08-20T23:59:59.999Z',
  quality_report: {
    candles_checked: 24,
    issues: [],
  },
  ready_to_import: true,
};

const dataset: DatasetSummary = {
  dataset_id: 'dataset-1234567890abcdef',
  schema_version: 1,
  name: 'BTC August sample',
  source: 'binance-public',
  pair: preview.pair,
  timeframe: '1h',
  start_time: '2026-08-20T00:00:00Z',
  end_time: '2026-08-21T00:00:00Z',
  created_at: '2026-08-31T14:00:00Z',
  candle_count: 24,
  checksum: 'a'.repeat(64),
};

function fillValidForm(): void {
  fireEvent.change(screen.getByLabelText('Dataset name'), {
    target: { value: 'BTC August sample' },
  });
  fireEvent.change(screen.getByLabelText('Range start'), {
    target: { value: '2026-08-20T00:00' },
  });
  fireEvent.change(screen.getByLabelText('Range end'), {
    target: { value: '2026-08-21T00:00' },
  });
}

describe('HistoricalDatasetImportForm', () => {
  beforeEach(() => {
    mocks.importHistoricalDataset.mockReset();
    mocks.previewHistoricalDatasetImport.mockReset();
  });

  it('previews a valid range and then creates an immutable dataset', async () => {
    const user = userEvent.setup();
    mocks.previewHistoricalDatasetImport.mockResolvedValue(preview);
    mocks.importHistoricalDataset.mockResolvedValue(dataset);

    render(<HistoricalDatasetImportForm connection={connection} locale="en" provider={provider} />);

    fillValidForm();
    await user.click(screen.getByRole('button', { name: 'Preview data' }));

    await waitFor(() => {
      expect(mocks.previewHistoricalDatasetImport).toHaveBeenCalledTimes(1);
    });
    expect(mocks.previewHistoricalDatasetImport).toHaveBeenCalledWith(
      connection.connection_id,
      expect.objectContaining({
        name: 'BTC August sample',
        pair: {
          base_asset: 'BTC',
          quote_asset: 'USDT',
          market_type: 'spot',
        },
        timeframe: '1h',
      }),
    );
    expect(await screen.findByText('Ready to import')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Create dataset' })).toBeEnabled();

    await user.click(screen.getByRole('button', { name: 'Create dataset' }));

    await waitFor(() => {
      expect(mocks.importHistoricalDataset).toHaveBeenCalledTimes(1);
    });
    expect(await screen.findByText(dataset.dataset_id)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'View dataset' })).toHaveAttribute(
      'href',
      `/en/datasets/${dataset.dataset_id}`,
    );
  });

  it('shows quality issues and keeps import disabled when preview is invalid', async () => {
    const user = userEvent.setup();
    mocks.previewHistoricalDatasetImport.mockResolvedValue({
      ...preview,
      ready_to_import: false,
      candle_count: 23,
      quality_report: {
        candles_checked: 23,
        issues: [
          {
            code: 'missing_candle',
            message: '1 missing candle(s) detected after 2026-08-20T10:00:00+00:00.',
            timestamp: '2026-08-20T11:00:00Z',
          },
        ],
      },
    } satisfies HistoricalDatasetImportPreview);

    render(<HistoricalDatasetImportForm connection={connection} locale="en" provider={provider} />);

    fillValidForm();
    await user.click(screen.getByRole('button', { name: 'Preview data' }));

    expect(await screen.findByText('Quality review required')).toBeInTheDocument();
    expect(screen.getByText(/Missing candle:/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Create dataset' })).toBeDisabled();
    expect(mocks.importHistoricalDataset).not.toHaveBeenCalled();
  });
});
