import { http, HttpResponse, type HttpHandler } from 'msw';
import { setupServer } from 'msw/node';
import * as fixtures from './fixtures';

/**
 * The fake server the pages are tested against: the platform's own /auth routes and /api/v1,
 * answering from the fixtures. Each test can override a route with `server.use(...)`.
 */
export const serverUrl = 'http://api.test';

export const sessionHandler = (signedIn = true) =>
  http.get('*/auth/session', () => HttpResponse.json({ signedIn, serverUrl, clientName: 'Glyphh' }));

export const apiError = (status: number, code: string, message: string, extra: Record<string, unknown> = {}) =>
  HttpResponse.json({ error: { code, message, trace_id: 'trace-123', ...extra } }, { status });

const v1 = (path: string) => `*/api/v1${path}`;

export const defaultHandlers: HttpHandler[] = [
  sessionHandler(),
  http.get('*/auth/providers', () => HttpResponse.json({ providers: ['github', 'google'], sso: false })),
  http.get(v1('/me'), () => HttpResponse.json(fixtures.me)),
];

export const server = setupServer(...defaultHandlers);

export { http, HttpResponse, v1 };
