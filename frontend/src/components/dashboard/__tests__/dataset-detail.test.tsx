import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import DatasetDetail from '@/components/dashboard/dataset-detail';
import type { DatasetDetailSummary, Page, OHLCVCandle } from '@/lib/api/types';

vi.mock('@/lib/api/client', () => ({
  getDatasetCandles: vi.fn(),
}));

const initialCandlesPage: Page<OHLCVCandle> = {
  items: [],
  total: 0,
  limit: 25,
  offset: 0,
  count: 0,
  has_next: false,
  has_previous: false,
};

function importedDataset(): DatasetDetailSummary {
  return {
    dataset_id: 'dataset-1234567890abcdef',
    schema_version: 2,
    name: 'BTC historical import',
    source: 'synthetic-public',
    pair: {
      base_asset: 'BTC',
      quote_asset: 'USDT',
      market_type: 'spot',
    },
    timeframe: '1h',
    start_time: '2026-08-20T10:00:00Z',
    end_time: '2026-08-20T12:00:00Z',
    created_at: '2026-08-31T12:00:00Z',
    candle_count: 2,
    checksum: 'a'.repeat(64),
    provenance: {
      kind: 'market_data_import',
      connection_id: 'market-data-connection-1',
      provider_id: 'synthetic-public',
      import_id: 'market-data-import-1',
      requested_start_time: '2026-08-20T10:00:00Z',
      requested_end_time: '2026-08-20T14:00:00Z',
    },
    quality_report: {
      candles_checked: 2,
      issues: [],
    },
  };
}

describe('DatasetDetail', () => {
  it('renders immutable import provenance and the persisted quality result', () => {
    render(
      <DatasetDetail
        dataset={importedDataset()}
        initialCandlesPage={initialCandlesPage}
        locale="en"
      />,
    );

    expect(screen.getByRole('heading', { name: 'Dataset provenance' })).toBeInTheDocument();
    expect(screen.getByText('Market data import')).toBeInTheDocument();
    expect(screen.getByText('market-data-connection-1')).toBeInTheDocument();
    expect(screen.getAllByText('synthetic-public').length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText('market-data-import-1')).toBeInTheDocument();

    expect(screen.getByRole('heading', { name: 'Data quality' })).toBeInTheDocument();
    expect(screen.getByText('Passed')).toBeInTheDocument();
    expect(screen.getByText('Candles checked')).toBeInTheDocument();
    expect(
      screen.getByText('No data-quality issues were recorded when this snapshot was created.'),
    ).toBeInTheDocument();
  });

  it('labels legacy datasets without inventing missing provenance or quality evidence', () => {
    const legacy: DatasetDetailSummary = {
      ...importedDataset(),
      schema_version: 1,
      provenance: {
        kind: 'legacy',
        connection_id: null,
        provider_id: null,
        import_id: null,
        requested_start_time: null,
        requested_end_time: null,
      },
      quality_report: null,
    };

    render(<DatasetDetail dataset={legacy} initialCandlesPage={initialCandlesPage} locale="en" />);

    expect(screen.getByText('Legacy / not recorded')).toBeInTheDocument();
    expect(
      screen.getByText('This dataset predates immutable provenance metadata.'),
    ).toBeInTheDocument();
    expect(screen.getByText('Not recorded')).toBeInTheDocument();
    expect(
      screen.getByText('No persisted quality report is available for this legacy dataset.'),
    ).toBeInTheDocument();
    expect(screen.queryByText('market-data-connection-1')).toBeNull();
  });
});
