import { describe, expect, it } from 'vitest';

import { DEFAULT_API_BASE_URL, normalizeApiBaseUrl } from '@/lib/api/core/base-url';

describe('API base URL contract', () => {
  it.each([undefined, '', '   '])('uses the local API fallback for %j', (configuredBaseUrl) => {
    expect(normalizeApiBaseUrl(configuredBaseUrl)).toBe(DEFAULT_API_BASE_URL);
  });

  it('trims configuration whitespace and trailing slashes', () => {
    expect(normalizeApiBaseUrl('  https://api.example.test///  ')).toBe('https://api.example.test');
  });

  it('supports a relative reverse-proxy prefix', () => {
    expect(normalizeApiBaseUrl('/backend/')).toBe('/backend');
  });

  it('supports same-origin requests when the configured prefix is root', () => {
    expect(normalizeApiBaseUrl('/')).toBe('');
  });
});
