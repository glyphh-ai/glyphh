import type { ApiErrorBody } from './types';

/** A refusal from the server, carried as the server sent it. */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly traceId: string | undefined;
  readonly detail: Record<string, unknown>;

  constructor(status: number, body: ApiErrorBody['error']) {
    super(body.message);
    this.name = 'ApiError';
    this.status = status;
    this.code = body.code;
    this.traceId = body.trace_id;
    this.detail = body;
  }
}

/** The platform's own sign-in has ended; the page should go to /login. */
export const signedOutCode = 'E_SIGNED_OUT';

type Method = 'GET' | 'POST' | 'PATCH' | 'DELETE';

/**
 * Calls the server's /v1 API through the platform's own route handlers (/api/v1/...),
 * which add the session's token. The browser never sees a token.
 */
export async function request<T>(method: Method, path: string, body?: unknown): Promise<T> {
  const response = await fetch(`/api/v1${path}`, {
    method,
    credentials: 'same-origin',
    headers: body === undefined ? { accept: 'application/json' } : { accept: 'application/json', 'content-type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  return readResponse<T>(response);
}

export async function readResponse<T>(response: Response): Promise<T> {
  if (response.status === 204) return undefined as T;
  const text = await response.text();
  const data: unknown = text ? JSON.parse(text) : undefined;
  if (!response.ok) {
    const error = (data as ApiErrorBody | undefined)?.error;
    throw new ApiError(response.status, error ?? { code: 'E_HTTP', message: 'Something went wrong. Try again.' });
  }
  return data as T;
}

export const api = {
  get: <T>(path: string) => request<T>('GET', path),
  post: <T>(path: string, body?: unknown) => request<T>('POST', path, body ?? {}),
  patch: <T>(path: string, body: unknown) => request<T>('PATCH', path, body),
  delete: <T = void>(path: string) => request<T>('DELETE', path),
};
