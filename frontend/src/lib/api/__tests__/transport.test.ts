import { afterEach, describe, expect, it, vi } from 'vitest';

import { API_BASE_URL, getBlob, getJson, postFormData, postJson } from '@/lib/api/core/transport';

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('API transport boundary', () => {
  it('performs no-store JSON GET requests', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: 'ok' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );
    vi.stubGlobal('fetch', fetchMock);

    await expect(getJson<{ status: string }>('/health')).resolves.toEqual({ status: 'ok' });
    expect(fetchMock).toHaveBeenCalledWith(`${API_BASE_URL}/health`, {
      method: 'GET',
      headers: { Accept: 'application/json' },
      cache: 'no-store',
    });
  });

  it('omits JSON body headers when a POST request has no body', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ queued: true }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );
    vi.stubGlobal('fetch', fetchMock);

    await postJson('/jobs/run');

    expect(fetchMock).toHaveBeenCalledWith(`${API_BASE_URL}/jobs/run`, {
      method: 'POST',
      headers: { Accept: 'application/json' },
      body: undefined,
      cache: 'no-store',
    });
  });

  it('lets the runtime set the multipart boundary for FormData requests', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ imported: true }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );
    vi.stubGlobal('fetch', fetchMock);
    const body = new FormData();
    body.append('file', new File(['data'], 'dataset.csv', { type: 'text/csv' }));

    await postFormData('/datasets/import', body);

    expect(fetchMock).toHaveBeenCalledWith(`${API_BASE_URL}/datasets/import`, {
      method: 'POST',
      headers: { Accept: 'application/json' },
      body,
      cache: 'no-store',
    });
  });

  it('preserves text error payloads for blob requests', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response('report unavailable', {
        status: 503,
        headers: { 'Content-Type': 'text/plain' },
      }),
    );
    vi.stubGlobal('fetch', fetchMock);

    await expect(getBlob('/reports/latest', 'text/csv')).rejects.toMatchObject({
      name: 'ApiRequestError',
      status: 503,
      payload: 'report unavailable',
    });
  });

  it('preserves structured API error payloads for JSON requests', async () => {
    const payload = {
      detail: {
        code: 'dataset_not_found',
        message: 'Dataset was not found',
      },
    };
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(payload), {
        status: 404,
        headers: { 'Content-Type': 'application/json; charset=utf-8' },
      }),
    );
    vi.stubGlobal('fetch', fetchMock);

    await expect(getJson('/api/v1/research/datasets/missing')).rejects.toMatchObject({
      name: 'ApiRequestError',
      status: 404,
      payload,
    });
  });
});
