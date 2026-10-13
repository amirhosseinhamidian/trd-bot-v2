import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  // The documented local URL uses 127.0.0.1 while Next's dev server is
  // initialized with localhost. Allow only that explicit loopback origin so
  // development chunks and HMR are not rejected as cross-origin requests.
  allowedDevOrigins: ['127.0.0.1'],
};

export default nextConfig;
