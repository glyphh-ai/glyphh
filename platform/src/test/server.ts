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
  http.get(v1('/license/keys'), () => HttpResponse.json(fixtures.licenceKeys)),
  http.get(v1('/license/nodes'), () => HttpResponse.json(fixtures.nodes)),
  http.get(v1('/telemetry/logs'), () => HttpResponse.json({ logs: fixtures.logs, next: null })),
  http.get(v1('/telemetry/audit'), () => HttpResponse.json({ events: fixtures.auditEvents, next: null })),
  http.get(v1('/telemetry/metrics'), () => HttpResponse.json({ runtimes: fixtures.metrics })),
];

/** The server as it answers while no runtime sends it anything, rrotor's default: `server.use(...nothingSentHandlers())`. */
export const nothingSentHandlers = (): HttpHandler[] => [
  http.get(v1('/telemetry/logs'), () => HttpResponse.json({ logs: [], next: null })),
  http.get(v1('/telemetry/audit'), () => HttpResponse.json({ events: [], next: null })),
  http.get(v1('/telemetry/metrics'), () => HttpResponse.json({ runtimes: [] })),
];

/**
 * The server as it answers with hosting off and features not yet built: a test calls `server.use(...hostingOffHandlers())`.
 * `rates` picks how the server answers the rates: refused with `hosting_off` (as it does), `{hosting: "off"}`, or no plans.
 */
export const hostingOffHandlers = (rates: 'refused' | 'off' | 'empty' = 'refused'): HttpHandler[] => [
  http.get(v1('/me'), () => HttpResponse.json(fixtures.hostingOff.me)),
  http.get(v1('/org'), () => HttpResponse.json(fixtures.hostingOff.org)),
  http.get(v1('/plans'), () => HttpResponse.json(fixtures.hostingOff.plans)),
  http.get(v1('/rates'), () =>
    rates === 'refused'
      ? apiError(503, 'E_UNAVAILABLE', 'Hosting is off.', { reason: 'hosting_off' })
      : HttpResponse.json(rates === 'off' ? fixtures.hostingOff.rates : { ...fixtures.rates, plans: {} }),
  ),
  http.get(v1('/runtime'), () => HttpResponse.json(fixtures.hostingOff.runtime)),
  http.get(v1('/runtimes'), () => HttpResponse.json(fixtures.hostingOff.machines)),
  http.get(v1('/license/keys'), () => HttpResponse.json(fixtures.hostingOff.licenceKeys)),
  http.get(v1('/license/nodes'), () => HttpResponse.json(fixtures.hostingOff.nodes)),
  http.post(v1('/runtimes'), () => apiError(503, 'E_UNAVAILABLE', 'Glyphh is not hosting machines now.', { reason: 'hosting_off' })),
  http.post(v1('/runtime/start'), () => apiError(503, 'E_UNAVAILABLE', 'Glyphh is not hosting machines now.', { reason: 'hosting_off' })),
];

export const server = setupServer(...defaultHandlers);

export { http, HttpResponse, v1 };
