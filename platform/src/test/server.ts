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
  http.get('*/auth/providers', () => HttpResponse.json({ providers: ['github', 'google'] })),
  http.get(v1('/me'), () => HttpResponse.json(fixtures.me)),
  http.get(v1('/org'), () => HttpResponse.json(fixtures.org)),
  http.get(v1('/runtime'), () => HttpResponse.json(fixtures.runtime)),
  http.get(v1('/runtime/keys'), () => HttpResponse.json(fixtures.runtimeKeys)),
  http.get(v1('/runtimes'), () => HttpResponse.json(fixtures.machines)),
  http.get(v1('/runtimes/self'), () => HttpResponse.json(fixtures.selfRuntimes)),
  http.get(v1('/models'), () => HttpResponse.json(fixtures.models)),
  http.get(v1('/plans'), () => HttpResponse.json(fixtures.plans)),
  http.get(v1('/rates'), () => HttpResponse.json(fixtures.rates)),
  http.get(v1('/org/members'), () => HttpResponse.json(fixtures.members)),
  http.get(v1('/org/invites'), () => HttpResponse.json(fixtures.invites)),
  http.get(v1('/installs'), () => HttpResponse.json(fixtures.installs)),
];

/**
 * The server as it answers with hosting off and features not yet built: a test calls `server.use(...hostingOffHandlers())`.
 * `rates` picks which of the two answers the server gives for the rates.
 */
export const hostingOffHandlers = (rates: 'off' | 'empty' = 'off'): HttpHandler[] => [
  http.get(v1('/me'), () => HttpResponse.json(fixtures.hostingOff.me)),
  http.get(v1('/org'), () => HttpResponse.json(fixtures.hostingOff.org)),
  http.get(v1('/plans'), () => HttpResponse.json(fixtures.hostingOff.plans)),
  http.get(v1('/rates'), () => HttpResponse.json(rates === 'off' ? fixtures.hostingOff.rates : { ...fixtures.rates, plans: {} })),
  http.get(v1('/runtime'), () => HttpResponse.json(fixtures.hostingOff.runtime)),
  http.get(v1('/runtimes'), () => HttpResponse.json(fixtures.hostingOff.machines)),
  http.post(v1('/runtimes'), () => apiError(409, 'E_UNAVAILABLE', 'Glyphh is not hosting machines now.', { reason: 'hosting_off' })),
  http.post(v1('/runtime/start'), () => apiError(409, 'E_UNAVAILABLE', 'Glyphh is not hosting machines now.', { reason: 'hosting_off' })),
];

export const server = setupServer(...defaultHandlers);

export { http, HttpResponse, v1 };
