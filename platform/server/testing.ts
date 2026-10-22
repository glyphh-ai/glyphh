import { Hono } from 'hono';
import type { Config } from './config.js';

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
  server.get('/v1/me', (c) => c.json({ id: 'u1', email: 'chris@example.com' }, 200, { 'x-request-id': 'req-1' }));
  server.patch('/v1/me', async (c) => c.json({ id: 'u1', name: (await c.req.json()).name }));
  server.delete('/v1/installs/:id', (c) => c.body(null, 204));
  server.get('/v1/org/members', (c) => c.json([], 200));
  server.get('/v1/usage', (c) => c.json({ plan: 'Pro', models: 0, precedents: { used: 0, max: 100_000 }, requests: null }));
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
