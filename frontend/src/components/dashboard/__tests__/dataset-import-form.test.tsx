import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import DatasetImportForm from '@/components/dashboard/dataset-import-form';
import type { DatasetImportCandle, DatasetSummary } from '@/lib/api/types';

const mocks = vi.hoisted(() => ({
  createDataset: vi.fn(),
  parseDatasetCsv: vi.fn(),
}));

vi.mock('@/lib/api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/lib/api/client')>();

  return {
    ...actual,
    createDataset: mocks.createDataset,
  };
});

vi.mock('@/lib/datasets/csv', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/lib/datasets/csv')>();

  return {
    ...actual,
    parseDatasetCsv: mocks.parseDatasetCsv,
  };
});

const candle: DatasetImportCandle = {
  open_time: '2026-08-20T10:00:00.000Z',
  close_time: '2026-08-20T11:00:00.000Z',
  open_price: '100',
  high_price: '102',
  low_price: '99',
  close_price: '101',
  volume: '1500',
  is_closed: true,
};

const createdDataset: DatasetSummary = {
  dataset_id: 'dataset-1234567890abcdef',
  schema_version: 1,
  name: 'BTC historical',
  source: 'manual-import',
  pair: {
    base_asset: 'BTC',
    quote_asset: 'USDT',
    market_type: 'spot',
  },
  timeframe: '1h',
  start_time: candle.open_time,
  end_time: candle.close_time,
  created_at: '2026-08-25T10:00:00.000Z',
  candle_count: 1,
  checksum: 'a'.repeat(64),
};

describe('DatasetImportForm', () => {
  it('validates required fields before submitting', async () => {
    const user = userEvent.setup();

    render(<DatasetImportForm locale="en" />);

    await user.click(
      screen.getByRole('button', {
        name: 'Import dataset',
      }),
    );

    expect(screen.getByText('Select a CSV file first.')).toBeInTheDocument();

    expect(mocks.createDataset).not.toHaveBeenCalled();
  });

  it('parses and imports a CSV dataset', async () => {
    const user = userEvent.setup();
    const onImported = vi.fn();

    mocks.parseDatasetCsv.mockReturnValue([candle]);

    mocks.createDataset.mockResolvedValue(createdDataset);

    render(<DatasetImportForm locale="en" onImported={onImported} />);

    await user.type(screen.getByLabelText('Dataset name'), 'BTC historical');

    await user.type(screen.getByLabelText('Data source'), 'manual-import');

    await user.type(screen.getByLabelText('Base asset'), 'btc');

    await user.type(screen.getByLabelText('Quote asset'), 'usdt');

    const file = new File(['csv contents'], 'btc.csv', {
      type: 'text/csv',
    });

    Object.defineProperty(file, 'text', {
      value: vi.fn().mockResolvedValue('csv contents'),
    });

    await user.upload(screen.getByLabelText('CSV file'), file);

    await waitFor(() => {
      expect(mocks.parseDatasetCsv).toHaveBeenCalledWith('csv contents', '1h');
    });

    await user.click(
      screen.getByRole('button', {
        name: 'Import dataset',
      }),
    );

    await waitFor(() => {
      expect(mocks.createDataset).toHaveBeenCalledWith({
        name: 'BTC historical',
        source: 'manual-import',
        pair: {
          base_asset: 'BTC',
          quote_asset: 'USDT',
          market_type: 'spot',
        },
        timeframe: '1h',
        candles: [candle],
      });
    });

    expect(onImported).toHaveBeenCalledWith(createdDataset);

    expect(screen.getByText('Dataset stored')).toBeInTheDocument();

    expect(
      screen.getByRole('link', {
        name: 'View dataset',
      }),
    ).toHaveAttribute('href', '/en/datasets/dataset-1234567890abcdef');
  });
});
