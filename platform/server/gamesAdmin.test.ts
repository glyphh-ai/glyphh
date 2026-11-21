import { createApp } from './app.js';
import { callTool, fromDays, GameError, readGames } from './gamesAdmin.js';
import { seal } from './seal.js';
import { fakeGames, fakeServer, testConfig, testGames } from './testing.js';
import type { Tokens } from './oauth.js';

const body = async (res: Response): Promise<any> => res.json();
const origin = { origin: testConfig.platformUrl, 'sec-fetch-site': 'same-origin' };
const noon = Date.parse('1970-01-12T12:00:00Z');

function setup({ staff = true, unset = [] as string[] } = {}) {
  const server = fakeServer();
  server.state.staff = staff;
  const games = fakeGames();
  const lines: string[] = [];
  const fetcher = ((input: Request | string | URL, init?: RequestInit) => {
    const host = new URL(input instanceof Request ? input.url : String(input)).host;
    return host === 'api.test' ? server.fetch(input, init) : games.fetch(input, init);
  }) as typeof fetch;
  const app = createApp({ config: testConfig, games: testGames(unset), fetch: fetcher, now: () => noon, log: (line) => lines.push(line) });
  const request = (path: string, init: RequestInit = {}) => app.request(`${testConfig.platformUrl}${path}`, init);
  return { server, games, lines, request };
}

function cookie(tokens: Partial<Tokens> = {}) {
  const value: Tokens = { accessToken: 'access-1', refreshToken: 'refresh-1', expiresAt: noon + 3_000_000, ...tokens };
  return `__Host-glyphh_session=${seal(value, testConfig.sessionKey, 'glyphh.session')}`;
}

const tool = (ctx: ReturnType<typeof setup>, game: string, name: string, args: unknown = {}, headers: Record<string, string> = { ...origin, cookie: cookie() }) =>
  ctx.request(`/api/games/${game}/tools/${name}`, { method: 'POST', headers: { ...headers, 'content-type': 'application/json' }, body: JSON.stringify({ arguments: args }) });

describe('readGames', () => {
  it('reads each game’s key and address from the environment, and none without', () => {
    const games = readGames({ GAME_ADMIN_KEY_FRANK: ' k1 ', GAME_URL_CRABBY: 'http://localhost:8787/' });
    expect(games.map((g) => g.id)).toEqual(['frank', 'crabby', 'mahj', 'carol']);
    expect(games[0]).toMatchObject({ key: 'k1', base: 'https://freefallfrank.com' });
    expect(games[1]).toMatchObject({ key: undefined, base: 'http://localhost:8787' });
    expect(games[3]).toMatchObject({ name: 'Send a Carol', base: 'https://sendacarol.com' });
  });
});

describe('fromDays', () => {
  it('adds today and the six days before it', () => {
    expect(fromDays([{ d: '1970-01-12', revenue: 5 }, { d: '1970-01-06', revenue: 7 }, { d: '1970-01-05', revenue: 100 }], '1970-01-12')).toEqual({ today: 5, d7: 12 });
  });
});

describe('callTool', () => {
  const [frank, crabby] = testGames();
  it('calls the game’s MCP endpoint with its key and gives back the structured answer', async () => {
    const games = fakeGames();
    expect(await callTool(frank!, games.fetch, 'admin_queue')).toMatchObject({ waiting: 2 });
    expect(games.calls).toEqual([{ game: 'frank', key: 'key-frank', tool: 'admin_queue', args: {} }]);
  });

  it('refuses a tool the game does not have, without calling it', async () => {
    const games = fakeGames();
    await expect(callTool(frank!, games.fetch, 'admin_ban')).rejects.toMatchObject({ status: 404, code: 'E_NO_TOOL' });
    expect(games.calls).toEqual([]);
  });

  it('says what the game said when it could not do it', async () => {
    await expect(callTool(crabby!, fakeGames().fetch, 'admin_ban', { uid: 'x' })).rejects.toEqual(new GameError(422, 'E_GAME_SAID', 'There is no such player.'));
  });

  it('says when the key is wrong, missing, or the game is down', async () => {
    const games = fakeGames();
    await expect(callTool({ ...frank!, key: 'wrong' }, games.fetch, 'admin_stats')).rejects.toMatchObject({ code: 'E_GAME_KEY', message: 'Free Fall Frank refused the admin key.' });
    await expect(callTool({ ...frank!, key: undefined }, games.fetch, 'admin_stats')).rejects.toMatchObject({ status: 503, message: 'GAME_ADMIN_KEY_FRANK is not set on the platform.' });
    games.down.add('frank');
    await expect(callTool(frank!, games.fetch, 'admin_stats')).rejects.toMatchObject({ code: 'E_GAME_DOWN' });
  });
});

describe('GET /api/games', () => {
  it('lists the games for staff, never their keys', async () => {
    const res = await setup({ unset: ['carol'] }).request('/api/games', { headers: { cookie: cookie() } });
    expect(res.status).toBe(200);
    const text = await res.text();
    expect(text).not.toContain('key-');
    expect(JSON.parse(text).games).toEqual([
      { id: 'frank', name: 'Free Fall Frank', site: 'https://freefallfrank.com', icon: 'https://freefallfrank.com/icon-192.png', connected: true },
      { id: 'crabby', name: 'Crabby Knife Fight', site: 'https://crabbyknifefight.com', icon: 'https://crabbyknifefight.com/icon-192.png', connected: true },
      { id: 'mahj', name: 'Bams & Brags', site: 'https://bamsandbrags.com', icon: 'https://bamsandbrags.com/icon-192.png', connected: true },
      { id: 'carol', name: 'Send a Carol', site: 'https://sendacarol.com', icon: 'https://sendacarol.com/favicon.ico', connected: false },
    ]);
  });

  it('refuses anyone who is not staff, and anyone signed out', async () => {
    const ctx = setup({ staff: false });
    const res = await ctx.request('/api/games', { headers: { cookie: cookie() } });
    expect(res.status).toBe(403);
    expect((await body(res)).error.code).toBe('E_STAFF_ONLY');
    expect((await ctx.request('/api/games')).status).toBe(401);
  });

  it('renews an expired session before asking who it is', async () => {
    const ctx = setup();
    const res = await ctx.request('/api/games', { headers: { cookie: cookie({ expiresAt: noon - 1 }) } });
    expect(res.status).toBe(200);
    expect(ctx.server.state.seen.find((s) => s.path === '/v1/me')?.headers.get('authorization')).toBe('Bearer access-2');
  });
});

describe('GET /api/games/overview', () => {
  it('reads every game’s health and numbers, in one shape', async () => {
    const res = await setup().request('/api/games/overview', { headers: { cookie: cookie() } });
    const { games } = await body(res);
    const [frank, crabby, mahj, carol] = games;
    expect(frank).toMatchObject({
      id: 'frank',
      health: { ok: true, build: 'build-frank' },
      error: null,
      summary: { players: 1200, new24: 30, active24: 80, revenue: { today: 99, d7: 297, d30: null, all: 4500 }, pending: [{ label: 'Levels to review', count: 2, tab: 'review' }] },
    });
    expect(crabby.summary).toMatchObject({ players: 300, revenue: null, pending: [{ label: 'Open reports', count: 3 }] });
    expect(mahj.summary).toMatchObject({ revenue: { today: 999, d7: 999, all: 2997 }, pending: [{ count: 5 }, { count: 1 }] });
    expect(carol.summary).toMatchObject({ players: 64, playersAre: 'accounts', revenue: { today: 499, d7: 1996, d30: 4990, all: 12050 }, pending: [{ count: 2 }, { count: 1 }] });
  });

  it('shows a game that is down or not connected beside the others', async () => {
    const ctx = setup({ unset: ['carol'] });
    ctx.games.down.add('crabby');
    const { games } = await body(await ctx.request('/api/games/overview', { headers: { cookie: cookie() } }));
    expect(games[1]).toMatchObject({ health: { ok: false, build: null }, summary: null, error: 'Crabby Knife Fight did not answer.' });
    expect(games[3]).toMatchObject({ connected: false, summary: null, error: 'GAME_ADMIN_KEY_CAROL is not set on the platform.' });
    expect(games[0].summary.players).toBe(1200);
  });

  it('is for staff only', async () => {
    expect((await setup({ staff: false }).request('/api/games/overview', { headers: { cookie: cookie() } })).status).toBe(403);
  });
});

describe('POST /api/games/:game/tools/:tool', () => {
  it('runs a game’s admin tool with the arguments given, and writes an action to the log', async () => {
    const ctx = setup();
    const res = await tool(ctx, 'frank', 'admin_review', { id: 'lv1', decision: 'approve' });
    expect(res.status).toBe(200);
    expect(await body(res)).toEqual({ result: { id: 'lv1', status: 'public' } });
    expect(ctx.games.calls).toEqual([{ game: 'frank', key: 'key-frank', tool: 'admin_review', args: { id: 'lv1', decision: 'approve' } }]);
    expect(ctx.lines).toHaveLength(1);
    expect(JSON.parse(ctx.lines[0]!)).toMatchObject({ games_admin: 'action', staff: 'chris@example.com', game: 'frank', tool: 'admin_review' });
  });

  it('does not log a read', async () => {
    const ctx = setup();
    expect((await tool(ctx, 'frank', 'admin_queue')).status).toBe(200);
    expect(ctx.lines).toEqual([]);
  });

  it('passes on what the game said when it could not', async () => {
    const res = await tool(setup(), 'crabby', 'admin_ban', { uid: 'nobody', why: 'test' });
    expect(res.status).toBe(422);
    expect((await body(res)).error).toEqual({ code: 'E_GAME_SAID', message: 'There is no such player.' });
  });

  it('refuses an unknown game, a tool the game lacks, another site, and anyone not staff', async () => {
    const ctx = setup();
    expect((await tool(ctx, 'pong', 'admin_stats')).status).toBe(404);
    expect((await body(await tool(ctx, 'crabby', 'delete_place'))).error.code).toBe('E_NO_TOOL');
    expect((await tool(ctx, 'frank', 'admin_stats', {}, { cookie: cookie(), 'sec-fetch-site': 'cross-site' })).status).toBe(403);
    expect((await tool(setup({ staff: false }), 'frank', 'admin_stats')).status).toBe(403);
    expect(ctx.games.calls).toEqual([]);
  });
});
