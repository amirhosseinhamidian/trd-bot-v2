export const DEFAULT_API_BASE_URL = 'http://127.0.0.1:8000';

export function normalizeApiBaseUrl(configuredBaseUrl: string | undefined): string {
  const trimmedBaseUrl = configuredBaseUrl?.trim();

  if (!trimmedBaseUrl) {
    return DEFAULT_API_BASE_URL;
  }

  return trimmedBaseUrl.replace(/\/+$/, '');
}
