import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import HistoricalDatasetImportForm from '@/components/dashboard/historical-dataset-import-form';
import { ApiRequestError } from '@/lib/api/client';
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
  ApiRequestError: class ApiRequestError extends Error {
    readonly status: number;
    readonly payload: unknown;

    constructor(message: string, status: number, payload: unknown) {
      super(message);
      this.status = status;
      this.payload = payload;
    }
  },
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
  last_error_code: null,
  last_error: null,
};

const provider: MarketDataProviderSummary = {
  provider_id: 'binance-public',
  display_name: 'Binance Public Market Data',
  requires_credentials: false,
  supported_market_types: ['spot'],
  supported_timeframes: ['1h', '4h'],
  default_pair: {
    base_asset: 'BTC',
    quote_asset: 'USDT',
    market_type: 'spot',
  },
  access_mode: 'vpn_required',
  max_closed_candles: null,
};

const krakenProvider: MarketDataProviderSummary = {
  ...provider,
  provider_id: 'kraken-public',
  display_name: 'Kraken Public Market Data',
  default_pair: {
    base_asset: 'BTC',
    quote_asset: 'USD',
    market_type: 'spot',
  },
  max_closed_candles: 719,
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
  preview_checksum: 'b'.repeat(64),
  quality_report: {
    candles_checked: 24,
    issues: [],
    coverage: {
      requested_start_time: '2026-08-20T00:00:00Z',
      requested_end_time: '2026-08-21T00:00:00Z',
      expected_first_open_time: '2026-08-20T00:00:00Z',
      expected_last_open_time: '2026-08-20T23:00:00Z',
      actual_first_open_time: '2026-08-20T00:00:00Z',
      actual_last_close_time: '2026-08-20T23:59:59.999Z',
      expected_candles: 24,
      received_candles: 24,
      missing_candles: 0,
      coverage_percent: 100,
      complete: true,
    },
    score: {
      score_version: 'quality-score-v1',
      score_percent: 100,
      coverage_percent: 100,
      integrity_percent: 100,
    },
    acceptance: {
      policy_version: 'strict-quality-v1',
      accepted: true,
      minimum_score_percent: 100,
      blocking_issue_codes: [],
    },
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
    const onImported = vi.fn();

    render(
      <HistoricalDatasetImportForm
        connection={connection}
        locale="en"
        provider={provider}
        onImported={onImported}
      />,
    );

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
    expect(screen.getByText('Range coverage')).toBeInTheDocument();
    expect(screen.getByText('Expected candles')).toBeInTheDocument();
    expect(screen.getByText('Versioned quality score')).toBeInTheDocument();
    expect(screen.getByText('quality-score-v1')).toBeInTheDocument();
    expect(screen.getByText('strict-quality-v1')).toBeInTheDocument();
    expect(screen.getAllByText('100%').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByRole('button', { name: 'Create dataset' })).toBeEnabled();

    await user.click(screen.getByRole('button', { name: 'Create dataset' }));

    await waitFor(() => {
      expect(mocks.importHistoricalDataset).toHaveBeenCalledTimes(1);
    });
    expect(mocks.importHistoricalDataset).toHaveBeenCalledWith(
      connection.connection_id,
      expect.objectContaining({ preview_checksum: preview.preview_checksum }),
    );
    expect(await screen.findByText(dataset.dataset_id)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'View dataset' })).toHaveAttribute(
      'href',
      `/en/datasets/${dataset.dataset_id}`,
    );
    expect(onImported).toHaveBeenCalledTimes(1);
  });

  it('shows quality issues and keeps import disabled when preview is invalid', async () => {
    const user = userEvent.setup();
    mocks.previewHistoricalDatasetImport.mockResolvedValue({
      ...preview,
      ready_to_import: false,
      candle_count: 23,
      quality_report: {
        candles_checked: 23,
        coverage: {
          ...preview.quality_report.coverage!,
          received_candles: 23,
          missing_candles: 1,
          coverage_percent: 95.83,
          complete: false,
        },
        issues: [
          {
            code: 'missing_candle',
            message: '1 missing candle(s) detected after 2026-08-20T10:00:00+00:00.',
            timestamp: '2026-08-20T11:00:00Z',
          },
        ],
        score: {
          score_version: 'quality-score-v1',
          score_percent: 95.83,
          coverage_percent: 95.83,
          integrity_percent: 100,
        },
        acceptance: {
          policy_version: 'strict-quality-v1',
          accepted: false,
          minimum_score_percent: 100,
          blocking_issue_codes: ['missing_candle'],
        },
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

  it('requires a new preview when provider content changes before import', async () => {
    const user = userEvent.setup();
    mocks.previewHistoricalDatasetImport.mockResolvedValue(preview);
    mocks.importHistoricalDataset.mockRejectedValue(
      new ApiRequestError('preview mismatch', 409, {
        detail: 'provider data changed after preview; run preview again before importing',
      }),
    );

    render(<HistoricalDatasetImportForm connection={connection} locale="en" provider={provider} />);

    fillValidForm();
    await user.click(screen.getByRole('button', { name: 'Preview data' }));
    await user.click(await screen.findByRole('button', { name: 'Create dataset' }));

    expect(
      await screen.findByText(
        'Provider data changed after preview. Run preview again and review the new result.',
      ),
    ).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Create dataset' })).toBeDisabled();
  });

  it('uses provider defaults and blocks ranges outside the recent Kraken window', async () => {
    render(
      <HistoricalDatasetImportForm
        connection={{ ...connection, provider_id: krakenProvider.provider_id }}
        locale="en"
        provider={krakenProvider}
      />,
    );

    expect(screen.getByLabelText('Quote asset')).toHaveValue('USD');
    expect(
      screen.getByText(
        'This provider requires VPN in the current environment. Confirm the VPN route before previewing data.',
      ),
    ).toBeInTheDocument();
    expect(screen.getByText(/latest 719 closed candles/)).toBeInTheDocument();

    fillValidForm();

    expect(
      screen.getByText(/outside this provider’s 719-candle recent window/),
    ).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Preview data' })).toBeDisabled();
    expect(mocks.previewHistoricalDatasetImport).not.toHaveBeenCalled();
  });
});
