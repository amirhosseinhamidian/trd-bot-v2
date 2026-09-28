import { afterEach, describe, expect, it, vi } from 'vitest';

import { API_BASE_URL, ApiRequestError, getPortfolioAnalytics } from '@/lib/api/client';

afterEach(() => vi.unstubAllGlobals());

describe('portfolio analytics client', () => {
  it('encodes portfolio identity and fetches uncached read-only analytics', async () => {
    const payload = { analytics_version: 'portfolio-analytics-v1' };
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(payload)));
    vi.stubGlobal('fetch', fetchMock);
    await expect(getPortfolioAnalytics('portfolio/a')).resolves.toEqual(payload);
    expect(fetchMock).toHaveBeenCalledWith(
      `${API_BASE_URL}/api/v1/research/portfolios/portfolio%2Fa/analytics`,
      expect.objectContaining({ method: 'GET', cache: 'no-store' }),
    );
  });

  it('propagates a missing portfolio without fabricated analytics', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{}', { status: 404 })));
    await expect(getPortfolioAnalytics('missing')).rejects.toBeInstanceOf(ApiRequestError);
  });
});
