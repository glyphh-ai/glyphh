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
  http.get(v1('/org'), () => HttpResponse.json(fixtures.org)),
  http.get(v1('/org/sso'), () => HttpResponse.json(null)),
  http.get(v1('/runtime/keys'), () => HttpResponse.json(fixtures.runtimeKeys)),
  http.get(v1('/runtimes/self'), () => HttpResponse.json(fixtures.selfRuntimes)),
  http.get(v1('/plans'), () => HttpResponse.json(fixtures.plans)),
  http.get(v1('/org/members'), () => HttpResponse.json(fixtures.members)),
  http.get(v1('/org/invites'), () => HttpResponse.json(fixtures.invites)),
  http.get(v1('/installs'), () => HttpResponse.json(fixtures.installs)),
  http.get(v1('/license/keys'), () => HttpResponse.json(fixtures.licenceKeys)),
  http.get(v1('/license/nodes'), () => HttpResponse.json(fixtures.nodes)),
  // Hosted models off (no GLYPHH_LLM): billing without tokens or a balance, and no registry.
  http.get(v1('/billing'), () => HttpResponse.json(fixtures.billing)),
  http.get(v1('/llm/models'), () => apiError(404, 'E_NOT_FOUND', 'Not found.')),
];

/**
 * The server with hosted models on (GLYPHH_LLM): plans with their tokens a month and the models' rates, billing with
 * the month's tokens and the overage balance, use by day and the balance's history. `server.use(...llmHandlers())`.
 */
export const llmHandlers = (): HttpHandler[] => [
  http.get(v1('/plans'), () => HttpResponse.json(fixtures.llmPlans)),
  http.get(v1('/billing'), () => HttpResponse.json(fixtures.llmBilling)),
  http.get(v1('/llm/usage'), () => HttpResponse.json({ days: fixtures.tokenDays })),
  http.get(v1('/billing/ledger'), () => HttpResponse.json({ entries: fixtures.ledger })),
];

/** The server as it answers a Free org with features not yet built: a test calls `server.use(...onFreeHandlers())`. */
export const onFreeHandlers = (): HttpHandler[] => [
  http.get(v1('/me'), () => HttpResponse.json(fixtures.onFree.me)),
  http.get(v1('/org'), () => HttpResponse.json(fixtures.onFree.org)),
  http.get(v1('/plans'), () => HttpResponse.json(fixtures.onFree.plans)),
  http.get(v1('/license/keys'), () => HttpResponse.json(fixtures.onFree.licenceKeys)),
  http.get(v1('/license/nodes'), () => HttpResponse.json(fixtures.onFree.nodes)),
];

/**
 * `GET /v1/apps` as the server pages it: the state asked (approved by default), `type` when asked, `q` against title,
 * description and name, `per_page` (24) from `page`. Pass the fixtures (or many) and tests assert the query from what
 * comes back.
 */
export const appsHandler = (all = fixtures.apps) =>
  http.get(v1('/apps'), ({ request }) => {
    const url = new URL(request.url);
    const state = url.searchParams.get('state') ?? 'approved';
    const type = url.searchParams.get('type');
    const q = (url.searchParams.get('q') ?? '').toLowerCase();
    const page = Number(url.searchParams.get('page') ?? '1');
    const perPage = Number(url.searchParams.get('per_page') ?? '24');
    const found = all.filter(
      (a) => a.state === state && (!type || a.type === type) && (!q || [a.title, a.description, a.name].some((s) => s.toLowerCase().includes(q))),
    );
    const apps = found.slice((page - 1) * perPage, page * perPage);
    return HttpResponse.json({ apps, page, per_page: perPage, total: found.length });
  });

defaultHandlers.push(appsHandler());

export const server = setupServer(...defaultHandlers);

export { http, HttpResponse, v1 };
