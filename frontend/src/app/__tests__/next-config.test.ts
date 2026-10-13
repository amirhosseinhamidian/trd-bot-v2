import { describe, expect, it } from 'vitest';

import nextConfig from '../../../next.config';

describe('Next.js local development origins', () => {
  it('allows the documented 127.0.0.1 development host without a wildcard', () => {
    expect(nextConfig.allowedDevOrigins).toEqual(['127.0.0.1']);
  });
});
