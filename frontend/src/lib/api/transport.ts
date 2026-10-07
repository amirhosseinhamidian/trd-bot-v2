const configuredApiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://127.0.0.1:8000';

export const API_BASE_URL = configuredApiBaseUrl.replace(/\/+$/, '');

export class ApiRequestError extends Error {
  readonly status: number;
  readonly payload: unknown;

  constructor(message: string, status: number, payload: unknown) {
    super(message);

    this.name = 'ApiRequestError';
    this.status = status;
    this.payload = payload;
  }
}

async function parseErrorPayload(response: Response): Promise<unknown> {
  const contentType = response.headers.get('content-type') ?? '';

  if (contentType.includes('application/json')) {
    return response.json();
  }

  return response.text();
}

export async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: 'GET',
    headers: {
      Accept: 'application/json',
    },
    cache: 'no-store',
  });

  if (!response.ok) {
    const payload = await parseErrorPayload(response);

    throw new ApiRequestError(
      `API request failed with status ${response.status}`,
      response.status,
      payload,
    );
  }

  return response.json() as Promise<T>;
}

export async function getBlob(path: string, accept: string): Promise<Blob> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: 'GET',
    headers: {
      Accept: accept,
    },
    cache: 'no-store',
  });

  if (!response.ok) {
    const payload = await parseErrorPayload(response);

    throw new ApiRequestError(
      `API request failed with status ${response.status}`,
      response.status,
      payload,
    );
  }

  return response.blob();
}

export async function postJson<T>(path: string, body?: unknown): Promise<T> {
  const hasBody = body !== undefined;

  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: 'POST',
    headers: {
      Accept: 'application/json',
      ...(hasBody
        ? {
            'Content-Type': 'application/json',
          }
        : {}),
    },
    body: hasBody ? JSON.stringify(body) : undefined,
    cache: 'no-store',
  });

  if (!response.ok) {
    const payload = await parseErrorPayload(response);

    throw new ApiRequestError(
      `API request failed with status ${response.status}`,
      response.status,
      payload,
    );
  }

  return response.json() as Promise<T>;
}

export async function postFormData<T>(path: string, body: FormData): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: 'POST',
    headers: {
      Accept: 'application/json',
    },
    body,
    cache: 'no-store',
  });

  if (!response.ok) {
    const payload = await parseErrorPayload(response);

    throw new ApiRequestError(
      `API request failed with status ${response.status}`,
      response.status,
      payload,
    );
  }

  return response.json() as Promise<T>;
}
