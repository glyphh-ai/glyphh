import type { ApiErrorBody } from './types';

/** A refusal from the server, carried as the server sent it. */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly traceId: string | undefined;
  readonly detail: Record<string, unknown>;
  /** Seconds to wait before asking again, from a 429's Retry-After header. */
  readonly retryAfter: number | undefined;

  constructor(status: number, body: ApiErrorBody['error'], retryAfter?: number) {
    super(body.message);
    this.name = 'ApiError';
    this.status = status;
    this.code = body.code;
    this.traceId = body.trace_id;
    this.detail = body;
    this.retryAfter = retryAfter;
  }
}

/** Retry-After as seconds; the server sends no HTTP date, so anything but a number is none. */
function retryAfter(response: Response): number | undefined {
  const header = response.headers.get('retry-after');
  const value = header === null ? Number.NaN : Number(header);
  return Number.isFinite(value) && value >= 0 ? value : undefined;
}

/** The platform's own sign-in has ended; the page should go to /login. */
export const signedOutCode = 'E_SIGNED_OUT';

type Method = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';

/**
 * Calls the server's /v1 API through the platform's own route handlers (/api/v1/...), or Ada Cloud's (/api/ada/v1/...),
 * which add the session's token. The browser never sees a token.
 */
export async function request<T>(method: Method, path: string, body?: unknown, base = '/api/v1'): Promise<T> {
  const response = await fetch(`${base}${path}`, {
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
    throw new ApiError(response.status, error ?? { code: 'E_HTTP', message: 'Something went wrong. Try again.' }, retryAfter(response));
  }
  return data as T;
}

export const api = {
  get: <T>(path: string) => request<T>('GET', path),
  post: <T>(path: string, body?: unknown) => request<T>('POST', path, body ?? {}),
  patch: <T>(path: string, body: unknown) => request<T>('PATCH', path, body),
  delete: <T = void>(path: string) => request<T>('DELETE', path),
};

/** Ada Cloud's API, at its own host, called with the same sign-in. */
const ada = '/api/ada/v1';
export const adaApi = {
  get: <T>(path: string) => request<T>('GET', path, undefined, ada),
  post: <T>(path: string, body?: unknown) => request<T>('POST', path, body ?? {}, ada),
  put: <T>(path: string, body: unknown) => request<T>('PUT', path, body, ada),
  patch: <T>(path: string, body: unknown) => request<T>('PATCH', path, body, ada),
  delete: <T = void>(path: string) => request<T>('DELETE', path, undefined, ada),
};
