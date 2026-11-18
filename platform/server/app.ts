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

/** The website's campaign cookie (web middleware.js), on .glyphh.ai, so this site receives it too. */
const sourceCookie = 'glyphh_src';

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

    let tokens: Tokens;
    try {
      tokens = await exchangeCode(config, fetcher, code, flow.verifier, now());
    } catch (error) {
      return failed(error instanceof OAuthError ? error.error : 'unreachable');
    }
    writeSession(c, tokens);
    await sendSource(c, tokens);
    return c.redirect(flow.returnTo, 302);
  });

  /**
   * Where a sign-up came from: the website's first-party `glyphh_src` cookie on .glyphh.ai (its campaign tags, kept 90
   * days), passed to the server as a sign-in finishes; the server keeps it on an account made within the last day
   * only. Best effort: a sign-in never waits on it to succeed.
   */
  async function sendSource(c: Context, tokens: Tokens) {
    const raw = getCookie(c, sourceCookie);
    if (!raw) return;
    let tags: unknown;
    try {
      tags = JSON.parse(raw);
    } catch {
      return;
    }
    if (!tags || typeof tags !== 'object' || Array.isArray(tags)) return;
    try {
      await fetcher(`${config.serverUrl}/v1/me/source`, {
        method: 'POST',
        headers: { authorization: `Bearer ${tokens.accessToken}`, 'content-type': 'application/json', accept: 'application/json' },
        body: JSON.stringify(tags),
      });
    } catch {
      // The sign-in goes on: only the source is lost.
    }
  }

  app.post('/auth/logout', async (c) => {
    if (!sameOrigin(c)) return c.json(errorBody('E_FORBIDDEN', 'That request did not come from this site.'), 403);
    const session = readSession(c);
    clearSession(c);
    if (session) await revoke(config, fetcher, session.refreshToken);
    return c.redirect('/login', 303);
  });

  const forbidden = (c: Context) => c.json(errorBody('E_FORBIDDEN', 'That request did not come from this site.'), 403);
  const noSession = (c: Context) => c.json(errorBody('E_SIGNED_OUT', 'You are signed out. Log in again.'), 401);

  /**
   * The answer passed back as the server gave it, keeping any cookie set on the way (a renewed session), and a 429's
   * Retry-After, so the page knows when to ask again.
   */
  const passBack = (c: Context, upstream: Response) => {
    const headers: Record<string, string> = { 'cache-control': 'no-store' };
    for (const name of ['content-type', 'x-request-id', 'retry-after']) {
      const value = upstream.headers.get(name);
      if (value) headers[name] = value;
    }
    return c.newResponse(upstream.status === 204 ? null : upstream.body, upstream.status as ContentfulStatusCode, headers);
  };

  // The account API (/api/v1/* → {server}/v1/*), with the session's token.
  app.all('/api/v1/*', (c) => forward(c, config.serverUrl, /^\/api/));

  async function forward(c: Context, base: string, prefix: RegExp) {
    if (unsafeMethods.has(c.req.method) && !sameOrigin(c)) return forbidden(c);

    let session = readSession(c);
    if (!session) return noSession(c);

    const signedOut = () => {
      clearSession(c);
      return noSession(c);
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
    const target = `${base}${url.pathname.replace(prefix, '')}${url.search}`;
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

    return passBack(c, upstream);
  }

  return app;
}
