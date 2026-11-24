import { Hono, type Context } from 'hono';
import type { ContentfulStatusCode } from 'hono/utils/http-status';
import { deleteCookie, getCookie, setCookie } from 'hono/cookie';
import type { Config } from './config.js';
import { authorizeUrl, exchangeCode, OAuthError, refresh, revoke, type Tokens } from './oauth.js';
import { callTool, GameError, health, isAction, summary, type Game } from './gamesAdmin.js';
import { createMarketplace, type MarketplaceReader } from './marketplace.js';
import { pkce, randomToken, seal, unseal } from './seal.js';

type Deps = {
  config: Config;
  /** What the Marketplace page shows: github.com/glyphh-ai/plugins, read and kept (marketplace.ts). */
  marketplace?: MarketplaceReader;
  /** The games the admin reaches (readGames()); none, and the games' admin lists nothing. */
  games?: Game[];
  /** Where each staff action on a game is written; the platform's log by default. */
  log?: (line: string) => void;
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

export function createApp({ config, games = [], log = (line) => console.log(line), fetch: fetcher = fetch, now = Date.now, marketplace = createMarketplace({ fetch: fetcher, now }) }: Deps) {
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
    c.json({ signedIn: readSession(c) !== null, serverUrl: config.serverUrl, adaUrl: config.adaUrl, clientName: config.clientName }),
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
   * Retry-After (Ada's E_RATE), so the page knows when to ask again.
   */
  const passBack = (c: Context, upstream: Response) => {
    const headers: Record<string, string> = { 'cache-control': 'no-store' };
    for (const name of ['content-type', 'x-request-id', 'retry-after']) {
      const value = upstream.headers.get(name);
      if (value) headers[name] = value;
    }
    return c.newResponse(upstream.status === 204 ? null : upstream.body, upstream.status as ContentfulStatusCode, headers);
  };

  // An import's file, to Ada Cloud's upload link: the link is its own credential, so no token goes with it, and the
  // file streams through rather than being held here. Signed-in pages of this site only.
  app.put('/api/ada/v1/uploads/:link', async (c) => {
    if (!sameOrigin(c)) return forbidden(c);
    if (!readSession(c)) return noSession(c);
    const headers: Record<string, string> = { accept: 'application/json' };
    for (const name of ['content-type', 'content-length']) {
      const value = c.req.header(name);
      if (value) headers[name] = value;
    }
    const init = { method: 'PUT', headers, body: c.req.raw.body, duplex: 'half' } as RequestInit;
    return passBack(c, await fetcher(`${config.adaUrl}/v1/uploads/${encodeURIComponent(c.req.param('link'))}`, init));
  });

  // The account API (/api/v1/* → {server}/v1/*) and Ada Cloud's (/api/ada/v1/* → {ada}/v1/*), with the session's token.
  app.all('/api/v1/*', (c) => forward(c, config.serverUrl, /^\/api/));
  app.all('/api/ada/v1/*', (c) => forward(c, config.adaUrl, /^\/api\/ada/));

  /**
   * Calls the server with the session's token, renewing it once when it has expired or the server says 401. Null
   * when the sign-in has ended (the cookie is cleared).
   */
  async function withToken(c: Context, send: (token: string) => Promise<Response>): Promise<Response | null> {
    let session = readSession(c);
    if (!session) return null;

    const renew = async (): Promise<boolean> => {
      try {
        session = await refresh(config, fetcher, session!.refreshToken, now());
        writeSession(c, session);
        return true;
      } catch {
        return false;
      }
    };
    const signedOut = () => {
      clearSession(c);
      return null;
    };

    if (now() >= session.expiresAt && !(await renew())) return signedOut();
    let upstream = await send(session.accessToken);
    if (upstream.status === 401) {
      if (!(await renew())) return signedOut();
      upstream = await send(session.accessToken);
      if (upstream.status === 401) return signedOut();
    }
    return upstream;
  }

  async function forward(c: Context, base: string, prefix: RegExp) {
    if (unsafeMethods.has(c.req.method) && !sameOrigin(c)) return forbidden(c);

    const url = new URL(c.req.url);
    const target = `${base}${url.pathname.replace(prefix, '')}${url.search}`;
    const body = c.req.method === 'GET' || c.req.method === 'HEAD' ? undefined : await c.req.arrayBuffer();

    const upstream = await withToken(c, (token) => {
      const headers: Record<string, string> = { authorization: `Bearer ${token}`, accept: 'application/json' };
      const contentType = c.req.header('content-type');
      if (contentType) headers['content-type'] = contentType;
      const requestId = c.req.header('x-request-id');
      if (requestId) headers['x-request-id'] = requestId;
      return fetcher(target, { method: c.req.method, headers, body });
    });
    return upstream ? passBack(c, upstream) : noSession(c);
  }

  // The Marketplace: the plugins in github.com/glyphh-ai/plugins, read here and kept ten minutes, for signed-in pages.
  // The repository is public, so no token goes to GitHub and none of the person's goes anywhere.
  app.get('/api/marketplace', async (c) => {
    if (!readSession(c)) return noSession(c);
    try {
      return c.json(await marketplace.load(), 200, { 'cache-control': 'no-store' });
    } catch {
      return c.json(errorBody('E_MARKETPLACE', 'The marketplace could not be loaded from GitHub.'), 502, { 'cache-control': 'no-store' });
    }
  });

  // ---- The games' admin: staff only, every call made here, server-side, with the game's own key. ----

  /**
   * Who is asking, as the server says (`GET /v1/me`): staff, or a refusal to answer with. The server only lets staff
   * sign in at all since the wind-down; this is checked again for every call regardless.
   */
  async function staffOnly(c: Context): Promise<{ email: string } | Response> {
    const me = await withToken(c, (token) =>
      fetcher(`${config.serverUrl}/v1/me`, { headers: { authorization: `Bearer ${token}`, accept: 'application/json' } }),
    );
    if (!me) return noSession(c);
    const who = (await me.json().catch(() => null)) as { email?: string; staff?: boolean } | null;
    if (!me.ok || who?.staff !== true) return c.json(errorBody('E_STAFF_ONLY', 'The games’ admin is for Glyphh’s staff.'), 403);
    return { email: who.email ?? 'staff' };
  }

  const gameById = (id: string) => games.find((g) => g.id === id);
  const listed = (g: Game) => ({ id: g.id, name: g.name, site: g.site, icon: `${g.site}${g.icon}`, connected: Boolean(g.key) });
  const gameRefusal = (c: Context, error: unknown) => {
    if (error instanceof GameError) return c.json(errorBody(error.code, error.message), error.status);
    throw error;
  };

  app.get('/api/games', async (c) => {
    const who = await staffOnly(c);
    if (who instanceof Response) return who;
    return c.json({ games: games.map(listed) }, 200, { 'cache-control': 'no-store' });
  });

  /** Every game at once: up or not, its build, its numbers. A game that fails says why; the rest still answer. */
  app.get('/api/games/overview', async (c) => {
    const who = await staffOnly(c);
    if (who instanceof Response) return who;
    const rows = await Promise.all(
      games.map(async (g) => {
        const [up, numbers] = await Promise.all([
          health(g, fetcher, now),
          summary(g, fetcher, now).then(
            (s) => ({ summary: s, error: null }),
            (e: unknown) => ({ summary: null, error: e instanceof GameError ? e.message : `${g.name} could not be read.` }),
          ),
        ]);
        return { ...listed(g), health: up, ...numbers };
      }),
    );
    return c.json({ games: rows, at: now() }, 200, { 'cache-control': 'no-store' });
  });

  /** One admin tool of one game. Reads and actions alike are POSTs, from this site's own pages only. */
  app.post('/api/games/:game/tools/:tool', async (c) => {
    if (!sameOrigin(c)) return forbidden(c);
    const who = await staffOnly(c);
    if (who instanceof Response) return who;
    const game = gameById(c.req.param('game'));
    if (!game) return c.json(errorBody('E_NOT_FOUND', 'There is no such game.'), 404);
    const tool = c.req.param('tool');
    const sent = (await c.req.json().catch(() => ({}))) as { arguments?: unknown };
    const args = sent.arguments && typeof sent.arguments === 'object' && !Array.isArray(sent.arguments) ? (sent.arguments as Record<string, unknown>) : {};
    try {
      const result = await callTool(game, fetcher, tool, args);
      if (isAction(game, tool)) {
        log(JSON.stringify({ games_admin: 'action', at: new Date(now()).toISOString(), staff: who.email, game: game.id, tool, args }));
      }
      return c.json({ result }, 200, { 'cache-control': 'no-store' });
    } catch (error) {
      return gameRefusal(c, error);
    }
  });

  return app;
}
