import { http, HttpResponse, type HttpHandler } from 'msw';
import { setupServer } from 'msw/node';
import * as fixtures from './fixtures';
import { marketplace } from './marketplace';

/**
 * The fake server the pages are tested against: the platform's own /auth routes, /api/marketplace and /api/v1,
 * answering from the fixtures. Each test can override a route with `server.use(...)`.
 */
export const serverUrl = 'http://api.test';

export const sessionHandler = (signedIn = true) =>
  http.get('*/auth/session', () => HttpResponse.json({ signedIn, serverUrl, clientName: 'Glyphh' }));

export const apiError = (status: number, code: string, message: string, extra: Record<string, unknown> = {}) =>
  HttpResponse.json({ error: { code, message, trace_id: 'trace-123', ...extra } }, { status });

const v1 = (path: string) => `*/api/v1${path}`;

/** `GET /api/marketplace`, answering what it is given: the fixtures' two plugins unless told otherwise. */
export const marketplaceHandler = (answer = marketplace()) => http.get('*/api/marketplace', () => HttpResponse.json(answer));

export const defaultHandlers: HttpHandler[] = [
  sessionHandler(),
  http.get('*/auth/providers', () => HttpResponse.json({ providers: ['github', 'google'], sso: false })),
  marketplaceHandler(),
  http.get(v1('/me'), () => HttpResponse.json(fixtures.me)),
  http.get(v1('/org'), () => HttpResponse.json(fixtures.org)),
  http.get(v1('/org/sso'), () => HttpResponse.json(null)),
  http.get(v1('/plans'), () => HttpResponse.json(fixtures.plans)),
  http.get(v1('/org/members'), () => HttpResponse.json(fixtures.members)),
  http.get(v1('/org/invites'), () => HttpResponse.json(fixtures.invites)),
  http.get(v1('/installs'), () => HttpResponse.json(fixtures.installs)),
  // Hosted models off (no GLYPHH_LLM): billing without tokens or a balance, and no registry.
  http.get(v1('/billing'), () => HttpResponse.json(fixtures.billing)),
  http.get(v1('/llm/models'), () => apiError(404, 'E_NOT_FOUND', 'Not found.')),
  // The use by day for Usage's charts, the days asked for; the admin's card on file and invoices.
  http.get(v1('/billing/series'), ({ request }) =>
    HttpResponse.json({ days: fixtures.seriesDays(Number(new URL(request.url).searchParams.get('days') ?? '30')) }),
  ),
  http.get(v1('/billing/payment'), () => HttpResponse.json(fixtures.payment)),
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
];

export const server = setupServer(...defaultHandlers);

export { http, HttpResponse, v1 };
