import { createApp, safeReturnTo } from './app.js';
import { seal } from './seal.js';
import { cookiesFrom, fakeServer, testConfig } from './testing.js';
import type { Tokens } from './oauth.js';

// Response bodies in these tests are the platform's own JSON; reading them loosely keeps the assertions short.
const body = async (res: Response): Promise<any> => res.json();

const origin = { origin: testConfig.platformUrl, 'sec-fetch-site': 'same-origin' };

function setup(now = 1_000_000) {
  const server = fakeServer();
  let clock = now;
  const app = createApp({ config: testConfig, fetch: server.fetch, now: () => clock });
  const request = (path: string, init: RequestInit = {}) => app.request(`${testConfig.platformUrl}${path}`, init);
  return { app, server, request, advance: (ms: number) => (clock += ms), now: () => clock };
}

function sessionCookie(tokens: Partial<Tokens> = {}, at = 1_000_000) {
  const value: Tokens = { accessToken: 'access-1', refreshToken: 'refresh-1', expiresAt: at + 3_000_000, ...tokens };
  return `__Host-glyphh_session=${seal(value, testConfig.sessionKey, 'glyphh.session')}`;
}

/** Runs /auth/login then /auth/callback with the server's code, returning the callback response. */
async function signIn(ctx: ReturnType<typeof setup>, { returnTo = '/keys', code = 'good-code', state }: { returnTo?: string; code?: string; state?: string } = {}) {
  const login = await ctx.request(`/auth/login?returnTo=${encodeURIComponent(returnTo)}`);
  const authorize = new URL(login.headers.get('location')!);
  const query = new URLSearchParams({ code, state: state ?? authorize.searchParams.get('state')! });
  return ctx.request(`/auth/callback?${query}`, { headers: { cookie: cookiesFrom(login) } });
}

describe('safeReturnTo', () => {
  it.each([
    ['/keys', '/keys'],
    ['/settings/billing?done=1', '/settings/billing?done=1'],
    [undefined, '/'],
    ['https://evil.test/', '/'],
    ['//evil.test', '/'],
    ['/\\evil.test', '/'],
    ['/auth/logout', '/'],
  ])('%s → %s', (input, expected) => expect(safeReturnTo(input)).toBe(expected));
});

describe('GET /auth/session', () => {
  it('is signed out with no cookie, and names the server', async () => {
    const res = await setup().request('/auth/session');
    expect(await body(res)).toEqual({ signedIn: false, serverUrl: 'https://api.test', clientName: 'Glyphh' });
  });

  it('is signed in with a sealed session', async () => {
    const res = await setup().request('/auth/session', { headers: { cookie: sessionCookie() } });
    expect((await body(res)).signedIn).toBe(true);
  });

  it('ignores a cookie that was tampered with', async () => {
    const res = await setup().request('/auth/session', { headers: { cookie: `${sessionCookie()}x` } });
    expect((await body(res)).signedIn).toBe(false);
  });
});

describe('GET /auth/providers', () => {
  it('passes the server’s list through', async () => {
    const res = await setup().request('/auth/providers');
    expect(await body(res)).toEqual({ providers: ['google', 'github'] });
  });
});

describe('GET /auth/login', () => {
  it('sends the browser to the server’s authorize endpoint with PKCE and a sealed flow cookie', async () => {
    const res = await setup().request('/auth/login?returnTo=/models');
    expect(res.status).toBe(302);
    const location = new URL(res.headers.get('location')!);
    expect(location.origin + location.pathname).toBe('https://api.test/oauth/authorize');
    expect(Object.fromEntries(location.searchParams)).toMatchObject({
      response_type: 'code',
      client_id: 'platform-client',
      redirect_uri: 'https://app.test/auth/callback',
      code_challenge_method: 'S256',
      scope: 'account',
    });
    expect(location.searchParams.get('code_challenge')).toMatch(/^[A-Za-z0-9_-]{43}$/);
    const cookie = res.headers.getSetCookie().find((c) => c.startsWith('__Host-glyphh_flow='))!;
    expect(cookie).toMatch(/HttpOnly/);
    expect(cookie).toMatch(/Secure/);
    expect(cookie).toMatch(/SameSite=Lax/);
  });
});

describe('GET /auth/callback', () => {
  it('exchanges the code, seals the tokens into an HttpOnly cookie and returns to where the person was', async () => {
    const ctx = setup();
    const res = await signIn(ctx, { returnTo: '/models' });
    expect(res.status).toBe(302);
    expect(res.headers.get('location')).toBe('/models');
    const cookie = res.headers.getSetCookie().find((c) => c.startsWith('__Host-glyphh_session='))!;
    expect(cookie).toMatch(/HttpOnly/);
    expect(cookie).not.toContain('access-1');

    const token = ctx.server.state.seen.find((r) => r.path === '/oauth/token')!;
    const form = new URLSearchParams(token.body);
    expect(form.get('grant_type')).toBe('authorization_code');
    expect(form.get('redirect_uri')).toBe('https://app.test/auth/callback');
    expect(form.get('code_verifier')).toMatch(/^[A-Za-z0-9_-]{64}$/);

    const session = await ctx.request('/auth/session', { headers: { cookie: cookiesFrom(res) } });
    expect((await body(session)).signedIn).toBe(true);
  });

  it('refuses a state that does not match', async () => {
    const res = await signIn(setup(), { state: 'forged' });
    expect(res.headers.get('location')).toBe('/login?failed=state');
  });

  it('refuses a callback with no flow cookie', async () => {
    const res = await setup().request('/auth/callback?code=good-code&state=x');
    expect(res.headers.get('location')).toBe('/login?failed=expired');
  });

  it('refuses a flow older than ten minutes', async () => {
    const ctx = setup();
    const login = await ctx.request('/auth/login');
    const state = new URL(login.headers.get('location')!).searchParams.get('state')!;
    ctx.advance(601_000);
    const res = await ctx.request(`/auth/callback?code=good-code&state=${state}`, { headers: { cookie: cookiesFrom(login) } });
    expect(res.headers.get('location')).toBe('/login?failed=expired');
  });

  it('says so when the person denied', async () => {
    const ctx = setup();
    const login = await ctx.request('/auth/login');
    const state = new URL(login.headers.get('location')!).searchParams.get('state')!;
    const res = await ctx.request(`/auth/callback?error=access_denied&state=${state}`, { headers: { cookie: cookiesFrom(login) } });
    expect(res.headers.get('location')).toBe('/login?failed=denied');
  });

  describe('with the website’s campaign cookie', () => {
    async function signInWithSource(ctx: ReturnType<typeof setup>, value: string) {
      const login = await ctx.request('/auth/login?returnTo=/');
      const state = new URL(login.headers.get('location')!).searchParams.get('state')!;
      const cookie = `${cookiesFrom(login)}; glyphh_src=${encodeURIComponent(value)}`;
      return ctx.request(`/auth/callback?code=good-code&state=${state}`, { headers: { cookie } });
    }

    it('sends its tags to the server as the person, and signs them in', async () => {
      const ctx = setup();
      const tags = { utm_source: 'reddit', utm_campaign: 'launch', landing: '/code' };
      const res = await signInWithSource(ctx, JSON.stringify(tags));
      expect(res.headers.get('location')).toBe('/');
      const sent = ctx.server.state.seen.find((r) => r.path === '/v1/me/source')!;
      expect(sent.method).toBe('POST');
      expect(sent.headers.get('authorization')).toBe('Bearer access-1');
      expect(JSON.parse(sent.body)).toEqual(tags);
    });

    it.each(['not json', '[1,2]', 'null'])('sends nothing for a cookie that is not tags: %s', async (value) => {
      const ctx = setup();
      const res = await signInWithSource(ctx, value);
      expect(res.headers.get('location')).toBe('/');
      expect(ctx.server.state.seen.some((r) => r.path === '/v1/me/source')).toBe(false);
    });

    it('signs the person in when the server can’t take the tags', async () => {
      const server = fakeServer();
      const failing: typeof fetch = (input, init) =>
        String(input).endsWith('/v1/me/source') ? Promise.reject(new Error('down')) : server.fetch(input as Request, init);
      const app = createApp({ config: testConfig, fetch: failing, now: () => 1_000_000 });
      const ctx = { ...setup(), app, server, request: (path: string, init: RequestInit = {}) => app.request(`${testConfig.platformUrl}${path}`, init) };
      const res = await signInWithSource(ctx, '{"utm_source":"x"}');
      expect(res.headers.get('location')).toBe('/');
      expect(res.headers.getSetCookie().some((c) => c.startsWith('__Host-glyphh_session='))).toBe(true);
    });
  });

  it('reports the OAuth error when the code is refused', async () => {
    const res = await signIn(setup(), { code: 'bad-code' });
    expect(res.headers.get('location')).toBe('/login?failed=invalid_grant');
  });
});

describe('POST /auth/logout', () => {
  it('clears the session, revokes the grant and goes to /login', async () => {
    const ctx = setup();
    const res = await ctx.request('/auth/logout', { method: 'POST', headers: { ...origin, cookie: sessionCookie() } });
    expect(res.status).toBe(303);
    expect(res.headers.get('location')).toBe('/login');
    expect(res.headers.getSetCookie().join()).toMatch(/__Host-glyphh_session=;/);
    const revoke = ctx.server.state.seen.find((r) => r.path === '/oauth/revoke')!;
    expect(new URLSearchParams(revoke.body).get('token')).toBe('refresh-1');
  });

  it('refuses a log out posted from another site', async () => {
    const res = await setup().request('/auth/logout', { method: 'POST', headers: { 'sec-fetch-site': 'cross-site', cookie: sessionCookie() } });
    expect(res.status).toBe(403);
  });
});

describe('/api/v1/*', () => {
  it('is signed out without a session', async () => {
    const res = await setup().request('/api/v1/me');
    expect(res.status).toBe(401);
    expect((await body(res)).error.code).toBe('E_SIGNED_OUT');
  });

  it('calls the server with the session’s token, never exposing it', async () => {
    const ctx = setup();
    const res = await ctx.request('/api/v1/me', { headers: { cookie: sessionCookie() } });
    expect(res.status).toBe(200);
    expect(await body(res)).toEqual({ id: 'u1', email: 'chris@example.com' });
    expect(res.headers.get('x-request-id')).toBe('req-1');
    expect(res.headers.get('cache-control')).toBe('no-store');
    const call = ctx.server.state.seen.find((r) => r.path === '/v1/me')!;
    expect(call.headers.get('authorization')).toBe('Bearer access-1');
  });

  it('passes the method, query and JSON body through', async () => {
    const ctx = setup();
    const res = await ctx.request('/api/v1/me?x=1', {
      method: 'PATCH',
      headers: { ...origin, cookie: sessionCookie(), 'content-type': 'application/json' },
      body: JSON.stringify({ name: 'Chris' }),
    });
    expect(await body(res)).toEqual({ id: 'u1', name: 'Chris' });
    const call = ctx.server.state.seen.find((r) => r.method === 'PATCH')!;
    expect(call.search).toBe('?x=1');
    expect(call.headers.get('content-type')).toBe('application/json');
  });

  it('passes a 204 through with no body', async () => {
    const res = await setup().request('/api/v1/installs/i1', { method: 'DELETE', headers: { ...origin, cookie: sessionCookie() } });
    expect(res.status).toBe(204);
    expect(await res.text()).toBe('');
  });

  it('passes the server’s refusals through unchanged', async () => {
    const res = await setup().request('/api/v1/org/invites', {
      method: 'POST',
      headers: { ...origin, cookie: sessionCookie(), 'content-type': 'application/json' },
      body: '{"email":"a@b.c"}',
    });
    expect(res.status).toBe(403);
    expect((await body(res)).error).toMatchObject({ code: 'E_LIMIT', trace_id: 't-lim', limit: 'members' });
  });

  it('refuses a write from another site', async () => {
    const res = await setup().request('/api/v1/me', { method: 'PATCH', headers: { 'sec-fetch-site': 'cross-site', cookie: sessionCookie() }, body: '{}' });
    expect(res.status).toBe(403);
  });

  it('checks the Origin when the browser sends no Sec-Fetch-Site', async () => {
    const ctx = setup();
    const ok = await ctx.request('/api/v1/me', { method: 'PATCH', headers: { origin: 'https://app.test', cookie: sessionCookie(), 'content-type': 'application/json' }, body: '{"name":"A"}' });
    const bad = await ctx.request('/api/v1/me', { method: 'PATCH', headers: { origin: 'https://evil.test', cookie: sessionCookie() }, body: '{}' });
    expect(ok.status).toBe(200);
    expect(bad.status).toBe(403);
  });

  it('refreshes an expired access token first and keeps the new pair', async () => {
    const ctx = setup();
    const res = await ctx.request('/api/v1/me', { headers: { cookie: sessionCookie({ expiresAt: ctx.now() - 1 }) } });
    expect(res.status).toBe(200);
    expect(ctx.server.state.seen.find((r) => r.path === '/v1/me')!.headers.get('authorization')).toBe('Bearer access-2');
    expect(res.headers.getSetCookie().some((c) => c.startsWith('__Host-glyphh_session='))).toBe(true);
  });

  it('refreshes once when the server says the token is no longer good', async () => {
    const ctx = setup();
    ctx.server.state.accessTokens.delete('access-1');
    const res = await ctx.request('/api/v1/me', { headers: { cookie: sessionCookie() } });
    expect(res.status).toBe(200);
    const calls = ctx.server.state.seen.filter((r) => r.path === '/v1/me').map((r) => r.headers.get('authorization'));
    expect(calls).toEqual(['Bearer access-1', 'Bearer access-2']);
  });

  it('signs the person out when the refresh is refused', async () => {
    const ctx = setup();
    ctx.server.state.refreshFails = true;
    const res = await ctx.request('/api/v1/me', { headers: { cookie: sessionCookie({ expiresAt: ctx.now() - 1 }) } });
    expect(res.status).toBe(401);
    expect((await body(res)).error.code).toBe('E_SIGNED_OUT');
    expect(res.headers.getSetCookie().join()).toMatch(/__Host-glyphh_session=;/);
  });
});

describe('over plain http', () => {
  it('names its cookies without the __Host- prefix and does not mark them Secure', async () => {
    const server = fakeServer();
    const app = createApp({ config: { ...testConfig, platformUrl: 'http://localhost:5173', secureCookies: false }, fetch: server.fetch, now: () => 1_000_000 });
    const login = await app.request('http://localhost:5173/auth/login');
    const flow = login.headers.getSetCookie().find((c) => c.startsWith('glyphh_flow='))!;
    expect(flow).not.toMatch(/Secure/);
    const state = new URL(login.headers.get('location')!).searchParams.get('state')!;
    const callback = await app.request(`http://localhost:5173/auth/callback?code=good-code&state=${state}`, { headers: { cookie: cookiesFrom(login) } });
    expect(callback.headers.getSetCookie().some((c) => c.startsWith('glyphh_session='))).toBe(true);
    const session = await app.request('http://localhost:5173/auth/session', { headers: { cookie: cookiesFrom(callback) } });
    expect((await body(session)).signedIn).toBe(true);
  });
});

describe('GET /auth/callback, when the server does not hand over a code', () => {
  /** Starts a sign-in and returns the callback's location for the given extra query. */
  async function callbackWith(ctx: ReturnType<typeof setup>, query: Record<string, string>) {
    const login = await ctx.request('/auth/login');
    const state = new URL(login.headers.get('location')!).searchParams.get('state')!;
    const res = await ctx.request(`/auth/callback?${new URLSearchParams({ state, ...query })}`, { headers: { cookie: cookiesFrom(login) } });
    return res.headers.get('location');
  }

  it('says the sign-in was refused for any OAuth error other than a denial', async () => {
    expect(await callbackWith(setup(), { error: 'invalid_scope' })).toBe('/login?failed=refused');
  });

  it('says the sign-in was refused when there is neither a code nor an error', async () => {
    expect(await callbackWith(setup(), {})).toBe('/login?failed=refused');
  });

  it('says the server could not be reached when the token request fails outright', async () => {
    const server = fakeServer();
    const fetcher = ((input: string, init?: RequestInit) =>
      String(input).endsWith('/oauth/token') ? Promise.reject(new TypeError('fetch failed')) : server.fetch(input, init)) as typeof fetch;
    const app = createApp({ config: testConfig, fetch: fetcher, now: () => 1_000_000 });
    const ctx = { ...setup(), request: (path: string, init: RequestInit = {}) => app.request(`${testConfig.platformUrl}${path}`, init) };
    expect(await callbackWith(ctx, { code: 'good-code' })).toBe('/login?failed=unreachable');
  });
});

describe('POST /auth/logout, without a session', () => {
  it('still goes to /login and calls nothing at the server', async () => {
    const ctx = setup();
    const res = await ctx.request('/auth/logout', { method: 'POST', headers: origin });
    expect(res.status).toBe(303);
    expect(res.headers.get('location')).toBe('/login');
    expect(ctx.server.state.seen).toEqual([]);
  });

  it('signs out even when the server cannot be reached to revoke the grant', async () => {
    const app = createApp({ config: testConfig, fetch: (() => Promise.reject(new TypeError('fetch failed'))) as typeof fetch });
    const res = await app.request(`${testConfig.platformUrl}/auth/logout`, { method: 'POST', headers: { ...origin, cookie: sessionCookie() } });
    expect(res.status).toBe(303);
    expect(res.headers.getSetCookie().join()).toMatch(/__Host-glyphh_session=;/);
  });
});

describe('/api/v1/*, more', () => {
  it('passes the browser’s request id on to the server', async () => {
    const ctx = setup();
    await ctx.request('/api/v1/me', { headers: { cookie: sessionCookie(), 'x-request-id': 'req-from-browser' } });
    expect(ctx.server.state.seen.find((r) => r.path === '/v1/me')!.headers.get('x-request-id')).toBe('req-from-browser');
  });

  it('refuses a write that carries neither Sec-Fetch-Site nor Origin', async () => {
    const res = await setup().request('/api/v1/me', { method: 'PATCH', headers: { cookie: sessionCookie() }, body: '{}' });
    expect(res.status).toBe(403);
    expect((await body(res)).error.code).toBe('E_FORBIDDEN');
  });

  it('signs the person out when the server refuses the token and the refresh is refused too', async () => {
    const ctx = setup();
    ctx.server.state.accessTokens.delete('access-1');
    ctx.server.state.refreshFails = true;
    const res = await ctx.request('/api/v1/me', { headers: { cookie: sessionCookie() } });
    expect(res.status).toBe(401);
    expect((await body(res)).error.code).toBe('E_SIGNED_OUT');
    expect(res.headers.getSetCookie().join()).toMatch(/__Host-glyphh_session=;/);
  });

  it('signs the person out when the server refuses even the renewed token, without asking a third time', async () => {
    const server = fakeServer();
    const fetcher = ((input: string, init?: RequestInit) =>
      String(input).includes('/v1/')
        ? Promise.resolve(Response.json({ error: { code: 'E_UNAUTHORIZED', message: 'Sign in again.' } }, { status: 401 }))
        : server.fetch(input, init)) as typeof fetch;
    const app = createApp({ config: testConfig, fetch: fetcher, now: () => 1_000_000 });
    const res = await app.request(`${testConfig.platformUrl}/api/v1/me`, { headers: { cookie: sessionCookie() } });
    expect(res.status).toBe(401);
    expect((await body(res)).error.code).toBe('E_SIGNED_OUT');
    expect(server.state.seen.filter((r) => r.path === '/oauth/token')).toHaveLength(1);
  });
});

describe('what is gone with Glyphh’s products (2026-11-18)', () => {
  it.each(['/api/ada/v1/usage', '/api/ada/v1/models'])('has no route to Ada Cloud at %s', async (path) => {
    const ctx = setup();
    expect((await ctx.request(path, { headers: { cookie: sessionCookie() } })).status).toBe(404);
    expect(ctx.server.state.seen).toHaveLength(0);
  });

  it('has no file upload to Ada Cloud either', async () => {
    const ctx = setup();
    const res = await ctx.request('/api/ada/v1/uploads/signed.link', { method: 'PUT', headers: { ...origin, cookie: sessionCookie() }, body: 'a,b\n' });
    expect(res.status).toBe(404);
    expect(ctx.server.state.seen).toHaveLength(0);
  });
});
