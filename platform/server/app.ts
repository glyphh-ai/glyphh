import { Hono, type Context } from 'hono';
import type { ContentfulStatusCode } from 'hono/utils/http-status';
import { deleteCookie, getCookie, setCookie } from 'hono/cookie';
import type { Config } from './config.js';
import { authorizeUrl, exchangeCode, OAuthError, refresh, revoke, type Tokens } from './oauth.js';
import { pkce, randomToken, seal, unseal } from './seal.js';

type Deps = {
  config: Config;
  /** The server is reached through this, so tests can put a fake server behind it. */
  fetch?: typeof fetch;
  now?: () => number;
};

type Flow = { state: string; verifier: string; returnTo: string; startedAt: number };

const sessionPurpose = 'glyphh.session';
const flowPurpose = 'glyphh.flow';
const flowMaxAgeSeconds = 600;
const sessionMaxAgeSeconds = 30 * 24 * 3600;

const unsafeMethods = new Set(['POST', 'PUT', 'PATCH', 'DELETE']);

/** Only a path on this platform may be returned to; anything else goes home. */
export function safeReturnTo(value: string | undefined): string {
  if (!value || !value.startsWith('/') || value.startsWith('//') || value.startsWith('/\\')) return '/';
  if (value.startsWith('/auth/')) return '/';
  return value;
}

function errorBody(code: string, message: string) {
  return { error: { code, message } };
}

export function createApp({ config, fetch: fetcher = fetch, now = Date.now }: Deps) {
  const app = new Hono();
  const secure = config.secureCookies;
  const sessionCookie = secure ? '__Host-glyphh_session' : 'glyphh_session';
  const flowCookie = secure ? '__Host-glyphh_flow' : 'glyphh_flow';

  const readSession = (c: Context) => unseal<Tokens>(getCookie(c, sessionCookie), config.sessionKey, sessionPurpose);

  const writeSession = (c: Context, tokens: Tokens) =>
    setCookie(c, sessionCookie, seal(tokens, config.sessionKey, sessionPurpose), {
      httpOnly: true,
      secure,
      sameSite: 'Lax',
      path: '/',
      maxAge: sessionMaxAgeSeconds,
    });

  const clearSession = (c: Context) => deleteCookie(c, sessionCookie, { path: '/', secure });

  /** A write must come from this platform's own pages, never from another site's form. */
  const sameOrigin = (c: Context) => {
    const site = c.req.header('sec-fetch-site');
    if (site) return site === 'same-origin';
    const origin = c.req.header('origin');
    return origin === config.platformUrl;
  };

  app.get('/auth/session', (c) =>
    c.json({ signedIn: readSession(c) !== null, serverUrl: config.serverUrl, clientName: config.clientName }),
  );

  app.get('/auth/providers', async () => {
    const upstream = await fetcher(`${config.serverUrl}/auth/providers`, { headers: { accept: 'application/json' } });
    return new Response(upstream.body, { status: upstream.status, headers: { 'content-type': 'application/json' } });
  });

  app.get('/auth/login', (c) => {
    const { verifier, challenge } = pkce();
    const flow: Flow = { state: randomToken(), verifier, returnTo: safeReturnTo(c.req.query('returnTo')), startedAt: now() };
    setCookie(c, flowCookie, seal(flow, config.sessionKey, flowPurpose), {
      httpOnly: true,
      secure,
      sameSite: 'Lax',
      path: '/',
      maxAge: flowMaxAgeSeconds,
    });
    return c.redirect(authorizeUrl(config, flow.state, challenge), 302);
  });

  app.get('/auth/callback', async (c) => {
    const flow = unseal<Flow>(getCookie(c, flowCookie), config.sessionKey, flowPurpose);
    deleteCookie(c, flowCookie, { path: '/', secure });

    const failed = (reason: string) => c.redirect(`/login?failed=${encodeURIComponent(reason)}`, 302);

    if (!flow || now() - flow.startedAt > flowMaxAgeSeconds * 1000) return failed('expired');
    if (c.req.query('state') !== flow.state) return failed('state');
    const denied = c.req.query('error');
    if (denied) return failed(denied === 'access_denied' ? 'denied' : 'refused');
    const code = c.req.query('code');
    if (!code) return failed('refused');

    try {
      writeSession(c, await exchangeCode(config, fetcher, code, flow.verifier, now()));
    } catch (error) {
      return failed(error instanceof OAuthError ? error.error : 'unreachable');
    }
    return c.redirect(flow.returnTo, 302);
  });

  app.post('/auth/logout', async (c) => {
    if (!sameOrigin(c)) return c.json(errorBody('E_FORBIDDEN', 'That request did not come from this site.'), 403);
    const session = readSession(c);
    clearSession(c);
    if (session) await revoke(config, fetcher, session.refreshToken);
    return c.redirect('/login', 303);
  });

  app.all('/api/v1/*', async (c) => {
    if (unsafeMethods.has(c.req.method) && !sameOrigin(c)) {
      return c.json(errorBody('E_FORBIDDEN', 'That request did not come from this site.'), 403);
    }

    let session = readSession(c);
    if (!session) return c.json(errorBody('E_SIGNED_OUT', 'You are signed out. Log in again.'), 401);

    const signedOut = () => {
      clearSession(c);
      return c.json(errorBody('E_SIGNED_OUT', 'You are signed out. Log in again.'), 401);
    };

    const renew = async (): Promise<boolean> => {
      try {
        session = await refresh(config, fetcher, session!.refreshToken, now());
        writeSession(c, session);
        return true;
      } catch {
        return false;
      }
    };

    if (now() >= session.expiresAt && !(await renew())) return signedOut();

    const url = new URL(c.req.url);
    const target = `${config.serverUrl}${url.pathname.replace(/^\/api/, '')}${url.search}`;
    const body = c.req.method === 'GET' || c.req.method === 'HEAD' ? undefined : await c.req.arrayBuffer();

    const send = () => {
      const headers: Record<string, string> = { authorization: `Bearer ${session!.accessToken}`, accept: 'application/json' };
      const contentType = c.req.header('content-type');
      if (contentType) headers['content-type'] = contentType;
      const requestId = c.req.header('x-request-id');
      if (requestId) headers['x-request-id'] = requestId;
      return fetcher(target, { method: c.req.method, headers, body });
    };

    let upstream = await send();
    if (upstream.status === 401) {
      if (!(await renew())) return signedOut();
      upstream = await send();
      if (upstream.status === 401) return signedOut();
    }

    // c.newResponse keeps any cookie set above (a renewed session) on the way out.
    const headers: Record<string, string> = { 'cache-control': 'no-store' };
    for (const name of ['content-type', 'x-request-id']) {
      const value = upstream.headers.get(name);
      if (value) headers[name] = value;
    }
    return c.newResponse(upstream.status === 204 ? null : upstream.body, upstream.status as ContentfulStatusCode, headers);
  });

  return app;
}
