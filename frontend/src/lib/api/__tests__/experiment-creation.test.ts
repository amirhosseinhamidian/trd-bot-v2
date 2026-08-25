import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  API_BASE_URL,
  ApiRequestError,
  createEmaCrossoverExperimentFromDataset,
} from '@/lib/api/client';
import type { StoredDatasetEMACrossoverRequest } from '@/lib/api/types';

const request: StoredDatasetEMACrossoverRequest = {
  dataset_id: 'dataset-btc-usdt-1h',
  fast_period: 9,
  slow_period: 21,
  horizon_candles: 1,
  starting_balance: '10000',
  allocation_fraction: '0.10',
  fee_rate: '0.001',
  slippage_rate: '0.0005',
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('createEmaCrossoverExperimentFromDataset', () => {
  it('posts the historical EMA backtest request to the stored-dataset endpoint', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          experiment_id: 'experiment-ema-btc',
        }),
        {
          status: 200,
          headers: {
            'Content-Type': 'application/json',
          },
        },
      ),
    );

    vi.stubGlobal('fetch', fetchMock);

    const result = await createEmaCrossoverExperimentFromDataset(request);

    expect(result).toEqual({
      experiment_id: 'experiment-ema-btc',
    });

    expect(fetchMock).toHaveBeenCalledTimes(1);

    const [url, options] = fetchMock.mock.calls[0] as [string, RequestInit];

    expect(url).toBe(`${API_BASE_URL}/api/v1/research/experiments/ema-crossover/from-dataset`);

    expect(options).toEqual(
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify(request),
      }),
    );

    expect(options.headers).toEqual(
      expect.objectContaining({
        Accept: 'application/json',
        'Content-Type': 'application/json',
      }),
    );
  });

  it('exposes the API error when the selected dataset does not exist', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          detail: 'dataset not found',
        }),
        {
          status: 404,
          headers: {
            'Content-Type': 'application/json',
          },
        },
      ),
    );

    vi.stubGlobal('fetch', fetchMock);

    await expect(createEmaCrossoverExperimentFromDataset(request)).rejects.toMatchObject({
      name: ApiRequestError.name,
      status: 404,
      payload: {
        detail: 'dataset not found',
      },
    });
  });
});
