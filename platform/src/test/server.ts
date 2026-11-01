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
  http.get(v1('/runtime/keys'), () => HttpResponse.json(fixtures.runtimeKeys)),
  http.get(v1('/runtimes/self'), () => HttpResponse.json(fixtures.selfRuntimes)),
  http.get(v1('/plans'), () => HttpResponse.json(fixtures.plans)),
  http.get(v1('/org/members'), () => HttpResponse.json(fixtures.members)),
  http.get(v1('/org/invites'), () => HttpResponse.json(fixtures.invites)),
  http.get(v1('/installs'), () => HttpResponse.json(fixtures.installs)),
  http.get(v1('/license/keys'), () => HttpResponse.json(fixtures.licenceKeys)),
  http.get(v1('/license/nodes'), () => HttpResponse.json(fixtures.nodes)),
];

/** The server as it answers a Free org with features not yet built: a test calls `server.use(...onFreeHandlers())`. */
export const onFreeHandlers = (): HttpHandler[] => [
  http.get(v1('/me'), () => HttpResponse.json(fixtures.onFree.me)),
  http.get(v1('/org'), () => HttpResponse.json(fixtures.onFree.org)),
  http.get(v1('/plans'), () => HttpResponse.json(fixtures.onFree.plans)),
  http.get(v1('/license/keys'), () => HttpResponse.json(fixtures.onFree.licenceKeys)),
  http.get(v1('/license/nodes'), () => HttpResponse.json(fixtures.onFree.nodes)),
];

export const server = setupServer(...defaultHandlers);

export { http, HttpResponse, v1 };
