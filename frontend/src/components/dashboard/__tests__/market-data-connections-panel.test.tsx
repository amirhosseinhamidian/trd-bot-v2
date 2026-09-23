import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import MarketDataConnectionsPanel from '@/components/dashboard/market-data-connections-panel';
import type { MarketDataConnection, MarketDataProviderSummary, Page } from '@/lib/api/types';

const mocks = vi.hoisted(() => ({
  createMarketDataConnection: vi.fn(),
  disableMarketDataConnection: vi.fn(),
  enableMarketDataConnection: vi.fn(),
  getMarketDataConnections: vi.fn(),
  getMarketDataImportHistory: vi.fn(),
  testMarketDataConnection: vi.fn(),
}));

vi.mock('@/lib/api/client', () => ({
  createMarketDataConnection: mocks.createMarketDataConnection,
  disableMarketDataConnection: mocks.disableMarketDataConnection,
  enableMarketDataConnection: mocks.enableMarketDataConnection,
  getMarketDataConnections: mocks.getMarketDataConnections,
  getMarketDataImportHistory: mocks.getMarketDataImportHistory,
  importHistoricalDataset: vi.fn(),
  previewHistoricalDatasetImport: vi.fn(),
  testMarketDataConnection: mocks.testMarketDataConnection,
}));

const providers: MarketDataProviderSummary[] = [
  {
    provider_id: 'binance-public',
    display_name: 'Binance Public Market Data',
    requires_credentials: false,
    supported_market_types: ['spot'],
    supported_timeframes: ['15m', '1h', '4h', '1d'],
    default_pair: {
      base_asset: 'BTC',
      quote_asset: 'USDT',
      market_type: 'spot',
    },
    access_mode: 'vpn_required',
    max_closed_candles: null,
  },
  {
    provider_id: 'kraken-public',
    display_name: 'Kraken Public Market Data',
    requires_credentials: false,
    supported_market_types: ['spot'],
    supported_timeframes: ['15m', '1h', '4h', '1d'],
    default_pair: {
      base_asset: 'BTC',
      quote_asset: 'USD',
      market_type: 'spot',
    },
    access_mode: 'vpn_required',
    max_closed_candles: 719,
  },
  {
    provider_id: 'nobitex-public',
    display_name: 'Nobitex Public Market Data',
    requires_credentials: false,
    supported_market_types: ['spot'],
    supported_timeframes: ['15m', '1h', '4h', '1d'],
    default_pair: {
      base_asset: 'BTC',
      quote_asset: 'USDT',
      market_type: 'spot',
    },
    access_mode: 'direct',
    max_closed_candles: null,
  },
];

const untestedConnection: MarketDataConnection = {
  connection_id: 'market-data-connection-1',
  provider_id: 'binance-public',
  display_name: 'Primary historical feed',
  state: 'disabled',
  health_status: 'untested',
  created_at: '2026-08-31T12:00:00Z',
  updated_at: '2026-08-31T12:00:00Z',
  last_tested_at: null,
  last_error_code: null,
  last_error: null,
};

const initialPage: Page<MarketDataConnection> = {
  items: [untestedConnection],
  total: 1,
  limit: 12,
  offset: 0,
  count: 1,
  has_next: false,
  has_previous: false,
};

describe('MarketDataConnectionsPanel', () => {
  beforeEach(() => {
    mocks.createMarketDataConnection.mockReset();
    mocks.disableMarketDataConnection.mockReset();
    mocks.enableMarketDataConnection.mockReset();
    mocks.getMarketDataConnections.mockReset();
    mocks.getMarketDataImportHistory.mockReset();
    mocks.getMarketDataImportHistory.mockResolvedValue({
      items: [],
      total: 0,
      limit: 10,
      offset: 0,
      count: 0,
      has_next: false,
      has_previous: false,
    });
    mocks.testMarketDataConnection.mockReset();
  });

  it('shows provider access and history constraints', () => {
    render(
      <MarketDataConnectionsPanel
        locale="en"
        initialProviders={providers}
        initialPage={initialPage}
      />,
    );

    expect(screen.getByText('Direct access')).toBeInTheDocument();
    expect(screen.getAllByText('VPN required')).toHaveLength(3);
    expect(screen.getByText('BTC/USD')).toBeInTheDocument();
    expect(screen.getByText('Up to 719 recent closed candles')).toBeInTheDocument();
  });

  it('moves a connection through test, enable, and disable actions', async () => {
    const user = userEvent.setup();
    const healthyConnection: MarketDataConnection = {
      ...untestedConnection,
      health_status: 'healthy',
      updated_at: '2026-08-31T12:05:00Z',
      last_tested_at: '2026-08-31T12:05:00Z',
    };
    const enabledConnection: MarketDataConnection = {
      ...healthyConnection,
      state: 'enabled',
      updated_at: '2026-08-31T12:06:00Z',
    };
    const disabledConnection: MarketDataConnection = {
      ...enabledConnection,
      state: 'disabled',
      updated_at: '2026-08-31T12:07:00Z',
    };

    mocks.testMarketDataConnection.mockResolvedValue(healthyConnection);
    mocks.enableMarketDataConnection.mockResolvedValue(enabledConnection);
    mocks.disableMarketDataConnection.mockResolvedValue(disabledConnection);

    render(
      <MarketDataConnectionsPanel
        locale="en"
        initialProviders={providers}
        initialPage={initialPage}
      />,
    );

    expect(screen.getByRole('button', { name: 'Enable' })).toBeDisabled();

    await user.click(screen.getByRole('button', { name: 'Test connection' }));

    await waitFor(() => {
      expect(mocks.testMarketDataConnection).toHaveBeenCalledWith('market-data-connection-1');
    });
    expect((await screen.findAllByText('Healthy')).length).toBeGreaterThan(0);
    expect(screen.getByRole('button', { name: 'Enable' })).toBeEnabled();

    await user.click(screen.getByRole('button', { name: 'Enable' }));

    await waitFor(() => {
      expect(mocks.enableMarketDataConnection).toHaveBeenCalledWith('market-data-connection-1');
    });
    expect(screen.getByRole('button', { name: 'Disable' })).toBeEnabled();

    await user.click(screen.getByRole('button', { name: 'Disable' }));

    await waitFor(() => {
      expect(mocks.disableMarketDataConnection).toHaveBeenCalledWith('market-data-connection-1');
    });
    expect(screen.getByRole('button', { name: 'Disable' })).toBeDisabled();
  });

  it('creates a disabled connection and refreshes the first page', async () => {
    const user = userEvent.setup();
    const emptyPage: Page<MarketDataConnection> = {
      ...initialPage,
      items: [],
      total: 0,
      count: 0,
    };
    const createdConnection: MarketDataConnection = {
      ...untestedConnection,
      connection_id: 'market-data-connection-2',
      display_name: 'Secondary feed',
    };
    const refreshedPage: Page<MarketDataConnection> = {
      ...initialPage,
      items: [createdConnection],
    };

    mocks.createMarketDataConnection.mockResolvedValue(createdConnection);
    mocks.getMarketDataConnections.mockResolvedValue(refreshedPage);

    render(
      <MarketDataConnectionsPanel
        locale="en"
        initialProviders={providers}
        initialPage={emptyPage}
      />,
    );

    await user.type(screen.getByLabelText('Connection name'), 'Secondary feed');
    await user.click(screen.getByRole('button', { name: 'Add connection' }));

    await waitFor(() => {
      expect(mocks.createMarketDataConnection).toHaveBeenCalledWith({
        provider_id: 'nobitex-public',
        display_name: 'Secondary feed',
      });
    });
    expect(mocks.getMarketDataConnections).toHaveBeenCalledWith({
      limit: 12,
      offset: 0,
    });
    expect(await screen.findByText('Secondary feed')).toBeInTheDocument();
    expect(screen.getAllByText('Untested').length).toBeGreaterThan(0);
  });
});
