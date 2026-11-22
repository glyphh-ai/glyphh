import { Hono } from 'hono';
import type { Config } from './config.js';
import { gameDefs, readGames } from './gamesAdmin.js';

export const testConfig: Config = {
  serverUrl: 'https://api.test',
  adaUrl: 'https://ada.test',
  platformUrl: 'https://app.test',
  clientId: 'platform-client',
  clientSecret: 's3cret',
  clientName: 'Glyphh',
  sessionKey: Buffer.alloc(32, 7),
  secureCookies: true,
};

export type Seen = { method: string; host: string; path: string; search: string; headers: Headers; body: string };

/**
 * A fake Glyphh server: the OAuth token and revoke endpoints and a small /v1, recording every request.
 * `accessTokens` are the tokens /v1 accepts; refreshing swaps in the next pair.
 */
export function fakeServer() {
  const seen: Seen[] = [];
  let generation = 1;
  const state = {
    seen,
    accessTokens: new Set(['access-1']),
    refreshFails: false,
    codeFails: false,
    /** /v1/me says staff: true. */
    staff: false,
  };

  const server = new Hono();

  server.use('*', async (c, next) => {
    const url = new URL(c.req.url);
    seen.push({ method: c.req.method, host: url.host, path: url.pathname, search: url.search, headers: c.req.raw.headers, body: await c.req.raw.clone().text() });
    await next();
  });

  server.post('/oauth/token', async (c) => {
    const form = new URLSearchParams(await c.req.text());
    if (c.req.header('authorization') !== `Basic ${Buffer.from('platform-client:s3cret').toString('base64')}`) {
      return c.json({ error: 'invalid_client', error_description: 'Unknown client.' }, 401);
    }
    if (form.get('grant_type') === 'authorization_code') {
      if (state.codeFails || form.get('code') !== 'good-code') return c.json({ error: 'invalid_grant', error_description: 'Bad code.' }, 400);
      return c.json({ access_token: 'access-1', token_type: 'Bearer', expires_in: 3600, refresh_token: 'refresh-1', scope: 'account' });
    }
    if (form.get('grant_type') === 'refresh_token') {
      if (state.refreshFails || form.get('refresh_token') !== `refresh-${generation}`) {
        return c.json({ error: 'invalid_grant', error_description: 'Refresh token used.' }, 400);
      }
      generation += 1;
      state.accessTokens.add(`access-${generation}`);
      return c.json({ access_token: `access-${generation}`, token_type: 'Bearer', expires_in: 3600, refresh_token: `refresh-${generation}`, scope: 'account' });
    }
    return c.json({ error: 'unsupported_grant_type', error_description: '' }, 400);
  });

  server.post('/oauth/revoke', (c) => c.body(null, 200));
  server.get('/auth/providers', (c) => c.json({ providers: ['google', 'github'] }));

  // Ada Cloud's upload links are their own credential: no bearer.
  server.put('/v1/uploads/:token', async (c) => c.json({ id: 'job-1', state: 'queued', bytes: (await c.req.arrayBuffer()).byteLength }, 202));

  server.use('/v1/*', async (c, next) => {
    const token = c.req.header('authorization')?.replace(/^Bearer /, '');
    if (!token || !state.accessTokens.has(token)) {
      return c.json({ error: { code: 'E_UNAUTHORIZED', message: 'Sign in again.', trace_id: 't-401' } }, 401);
    }
    await next();
  });
  server.get('/v1/me', (c) => c.json({ id: 'u1', email: 'chris@example.com', ...(state.staff ? { staff: true } : {}) }, 200, { 'x-request-id': 'req-1' }));
  server.patch('/v1/me', async (c) => c.json({ id: 'u1', name: (await c.req.json()).name }));
  server.delete('/v1/installs/:id', (c) => c.body(null, 204));
  server.get('/v1/org/members', (c) => c.json([], 200));
  server.get('/v1/usage', (c) =>
    c.json({
      plan: 'Pro',
      month: '2026-10',
      resets_at: '2026-11-01',
      models: 0,
      precedents: { used: 0, max: 100_000 },
      requests: { used: 0, max: 1_000_000, over: 0, overage: true },
      requests_per_second: 50,
    }),
  );
  // Ada's 429 for more calls a second than the plan allows, with when to ask again.
  server.post('/v1/decide', () =>
    Response.json(
      { error: { code: 'E_RATE', message: 'Your plan allows 5 Ada calls a second: try again in 1 second.', trace_id: 't-rate', retry_after: 1, reason: 'rate', max: 5 } },
      { status: 429, headers: { 'retry-after': '1' } },
    ),
  );
  server.post('/v1/org/invites', () =>
    Response.json({ error: { code: 'E_LIMIT', message: 'Your plan allows 1 member.', trace_id: 't-lim', limit: 'members' } }, { status: 403 }),
  );

  const fetcher = ((input: Request | string | URL, init?: RequestInit) => server.request(input instanceof Request ? input : String(input), init)) as typeof fetch;
  return { state, fetch: fetcher };
}

/** Pulls cookies set on a response into a Cookie header for the next request. */
export function cookiesFrom(response: Response): string {
  return response.headers
    .getSetCookie()
    .map((line) => line.split(';')[0])
    .filter((pair) => pair && !pair.endsWith('='))
    .join('; ');
}

export type GameCall = { game: string; key: string | null; tool: string; args: Record<string, unknown> };

/** What each fake game's admin tools answer: a value, or a function of the arguments; an `Error` answers isError. */
type Answers = Record<string, unknown>;

export const gameAnswers: Record<string, Answers> = {
  frank: {
    admin_stats: {
      overview: { players: 1200, players24: 30, players7: 210, active24: 80, accounts: 90, buyers: 12, revenue: 4500 },
      days: [
        { d: '1970-01-12', players: 30, revenue: 99 },
        { d: '1970-01-10', players: 20, revenue: 198 },
        { d: '1970-01-01', players: 5, revenue: 1000 },
      ],
    },
    admin_queue: { waiting: 2, levels: [{ id: 'lv1', name: 'Rooftops', author: 'Sam', status: 'pending' }] },
    admin_review: (args: Record<string, unknown>) => ({ id: args.id, status: args.decision === 'approve' ? 'public' : 'declined' }),
  },
  crabby: {
    admin_overview: { overview: { players: 300, players24: 4, active24: 9, reportsOpen: 3 } },
    admin_ban: () => new Error('There is no such player.'),
  },
  mahj: {
    admin_overview: { overview: { players: 800, players24: 12, active24: 40, revenue: 2997, queue: 5, reportsOpen: 1 }, days: [{ d: '1970-01-12', revenue: 999 }] },
  },
  carol: {
    admin_overview: (args: Record<string, unknown>) => ({
      days: args.days,
      recent: { revenue_usd: args.days === 1 ? 4.99 : args.days === 7 ? 19.96 : 49.9, made: 3, opened: 11 },
      all_time: { revenue_usd: 120.5 },
      accounts: 64,
      open_reports: 2,
      failed_jobs: 1,
    }),
  },
};

/**
 * Fake games behind one fetch: each answers /healthz and its admin MCP endpoint (`/mcp?admin=key-<game>`) from
 * `gameAnswers`, recording every tool call. A game in `down` answers nothing at all.
 */
export function fakeGames(answers: Record<string, Answers> = gameAnswers) {
  const calls: GameCall[] = [];
  const down = new Set<string>();
  const fetcher = (async (input: Request | string | URL, init?: RequestInit) => {
    const url = new URL(input instanceof Request ? input.url : String(input));
    const game = url.hostname.replace(/\.test$/, '');
    if (down.has(game)) throw new TypeError('fetch failed');
    if (url.pathname === '/healthz') return Response.json({ ok: true, build: `build-${game}` });
    if (url.pathname !== '/mcp') return new Response('not found', { status: 404 });
    const key = url.searchParams.get('admin');
    if (key !== `key-${game}`) {
      return Response.json({ jsonrpc: '2.0', id: null, error: { code: -32001, message: 'that admin address is not right' } }, { status: 401 });
    }
    const message = JSON.parse(String(init?.body));
    const { name, arguments: args = {} } = message.params;
    calls.push({ game, key, tool: name, args });
    const answer = answers[game]?.[name];
    const value = typeof answer === 'function' ? answer(args) : (answer ?? { ok: true });
    if (value instanceof Error) {
      return Response.json({ jsonrpc: '2.0', id: message.id, result: { content: [{ type: 'text', text: `Could not do that: ${value.message}` }], isError: true } });
    }
    return Response.json({ jsonrpc: '2.0', id: message.id, result: { content: [{ type: 'text', text: JSON.stringify(value) }], structuredContent: value } });
  }) as typeof fetch;
  return { calls, down, fetch: fetcher };
}

/** The four games, reached at https://<game>.test with the key key-<game>; the games in `unset` have no key. */
export function testGames(unset: string[] = []) {
  const env: Record<string, string> = {};
  for (const g of gameDefs) {
    env[`GAME_URL_${g.id.toUpperCase()}`] = `https://${g.id}.test`;
    if (!unset.includes(g.id)) env[`GAME_ADMIN_KEY_${g.id.toUpperCase()}`] = `key-${g.id}`;
  }
  return readGames(env);
}
