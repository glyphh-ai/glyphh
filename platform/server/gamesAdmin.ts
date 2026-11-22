/**
 * The games' admin (his ruling, 2026-11-19: "one admin, games keep their own DBs"). Each game keeps its own server
 * and database; the platform reaches each one's admin MCP endpoint (`POST {site}/mcp?admin=<key>`, JSON-RPC
 * tools/call), server-side only, with that game's own ADMIN_MCP_KEY, which the platform holds as
 * GAME_ADMIN_KEY_<GAME>. A key never reaches the browser.
 */

export type GameId = 'frank' | 'crabby' | 'mahj' | 'carol';

type GameDef = {
  id: GameId;
  name: string;
  site: string;
  /** A path on the game's own site. */
  icon: string;
  /** The admin tools the platform may call, every one the game has today: those that only read, and the actions. */
  reads: readonly string[];
  actions: readonly string[];
};

export const gameDefs: readonly GameDef[] = [
  {
    id: 'frank',
    name: 'Free Fall Frank',
    site: 'https://freefallfrank.com',
    icon: '/icon-192.png',
    reads: ['admin_stats', 'admin_queue', 'admin_levels', 'admin_players', 'admin_player', 'admin_payments', 'admin_ads'],
    actions: ['admin_review', 'admin_campaign_set', 'admin_ad_set'],
  },
  {
    id: 'crabby',
    name: 'Crabby Knife Fight',
    site: 'https://crabbyknifefight.com',
    icon: '/icon-192.png',
    reads: ['admin_overview', 'admin_list'],
    actions: ['admin_ban', 'admin_hide', 'admin_report', 'admin_drop_time'],
  },
  {
    id: 'mahj',
    name: 'Bams & Brags',
    site: 'https://bamsandbrags.com',
    icon: '/icon-192.png',
    reads: ['admin_guide', 'admin_queue', 'admin_overview', 'admin_live', 'admin_list', 'admin_player', 'admin_league', 'admin_event', 'admin_money', 'admin_claude', 'admin_audit'],
    actions: ['admin_ban', 'admin_close', 'admin_hide', 'admin_review', 'admin_report', 'admin_score', 'admin_pass', 'admin_balance', 'admin_transfer', 'admin_registrations', 'admin_revoke'],
  },
  {
    id: 'carol',
    name: 'Send a Carol',
    site: 'https://sendacarol.com',
    icon: '/favicon.ico',
    reads: ['admin_overview', 'admin_cards', 'admin_card', 'admin_accounts', 'admin_reports', 'admin_jobs', 'admin_templates', 'admin_occasions', 'admin_prices', 'admin_audit'],
    actions: ['admin_take_down', 'admin_delete_media', 'admin_grant', 'admin_ban', 'admin_report', 'admin_retry_job', 'admin_template', 'admin_occasion', 'admin_limit'],
  },
];

export const isAction = (game: Game, tool: string) => game.actions.includes(tool);

export type Game = GameDef & {
  /** Where the platform reaches the game: its site, or GAME_URL_<GAME> to point it elsewhere. */
  base: string;
  /** The game's ADMIN_MCP_KEY, from GAME_ADMIN_KEY_<GAME>; none, and the game shows as not connected. */
  key: string | undefined;
};

export const keyName = (id: GameId) => `GAME_ADMIN_KEY_${id.toUpperCase()}`;

export function readGames(env: NodeJS.ProcessEnv = process.env): Game[] {
  return gameDefs.map((def) => ({
    ...def,
    base: (env[`GAME_URL_${def.id.toUpperCase()}`]?.trim() || def.site).replace(/\/$/, ''),
    key: env[keyName(def.id)]?.trim() || undefined,
  }));
}

/** A game said no, or could not be reached; `status` is what the platform answers the page with. */
export class GameError extends Error {
  constructor(
    readonly status: 404 | 422 | 502 | 503,
    readonly code: string,
    message: string,
  ) {
    super(message);
  }
}

const timeoutMs = 15_000;

/** One admin tool of one game, called through its MCP endpoint; its structured answer. */
export async function callTool(game: Game, fetcher: typeof fetch, tool: string, args: Record<string, unknown> = {}): Promise<unknown> {
  if (!game.reads.includes(tool) && !game.actions.includes(tool)) throw new GameError(404, 'E_NO_TOOL', `${game.name} has no admin tool ${tool}.`);
  if (!game.key) throw new GameError(503, 'E_GAME_NOT_SET', `${keyName(game.id)} is not set on the platform.`);
  let response: Response;
  try {
    response = await fetcher(`${game.base}/mcp?admin=${encodeURIComponent(game.key)}`, {
      method: 'POST',
      headers: { 'content-type': 'application/json', accept: 'application/json, text/event-stream' },
      body: JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'tools/call', params: { name: tool, arguments: args } }),
      signal: AbortSignal.timeout(timeoutMs),
    });
  } catch {
    throw new GameError(502, 'E_GAME_DOWN', `${game.name} did not answer.`);
  }
  if (response.status === 401) throw new GameError(502, 'E_GAME_KEY', `${game.name} refused the admin key.`);
  if (response.status === 429) throw new GameError(502, 'E_GAME_BUSY', `${game.name} says too many requests. Try again in a minute.`);
  type Answer = { result?: { isError?: boolean; structuredContent?: unknown; content?: Array<{ type: string; text?: string }> }; error?: { message?: string } };
  let message: Answer;
  try {
    message = (await response.json()) as Answer;
  } catch {
    throw new GameError(502, 'E_GAME_DOWN', `${game.name} answered ${response.status}, not JSON.`);
  }
  if (message.error) throw new GameError(502, 'E_GAME', `${game.name}: ${message.error.message ?? 'refused'}`);
  const result = message.result;
  const text = result?.content?.find((c) => c.type === 'text')?.text ?? '';
  if (result?.isError) throw new GameError(422, 'E_GAME_SAID', text.replace(/^Could not do that: /, '') || `${game.name} could not do that.`);
  if (result?.structuredContent !== undefined) return result.structuredContent;
  try {
    return JSON.parse(text);
  } catch {
    return { text };
  }
}

export type Health = { ok: boolean; build: string | null; ms: number };

export async function health(game: Game, fetcher: typeof fetch, now: () => number): Promise<Health> {
  const started = now();
  try {
    const response = await fetcher(`${game.base}/healthz`, { headers: { accept: 'application/json' }, signal: AbortSignal.timeout(8_000) });
    const body = (await response.json().catch(() => ({}))) as { ok?: boolean; build?: string };
    return { ok: response.ok && body.ok === true, build: body.build ?? null, ms: now() - started };
  } catch {
    return { ok: false, build: null, ms: now() - started };
  }
}

/** Money in cents; null where the game does not count it that way. */
export type Revenue = { today: number | null; d7: number | null; d30: number | null; all: number | null };

export type Summary = {
  players: number | null;
  /** What "players" counts in this game. */
  playersAre: string;
  new24: number | null;
  active24: number | null;
  /** What new24 and active24 count in this game. */
  labels: [string, string];
  revenue: Revenue | null;
  /** What waits for a person: levels to review, reports, failed jobs. */
  pending: Array<{ label: string; count: number; tab: string }>;
};

type Day = { d: string; revenue?: number };
const PLAYED: [string, string] = ['New today', 'Played today'];
type Obj = Record<string, any>;

/** Today and the six days before it (UTC), from a game's last 14 days, day by day. */
export function fromDays(days: Day[], today: string): { today: number; d7: number } {
  const start = new Date(`${today}T00:00:00Z`).getTime() - 6 * 864e5;
  let d7 = 0;
  let onDay = 0;
  for (const day of days) {
    const at = new Date(`${day.d}T00:00:00Z`).getTime();
    if (at >= start) d7 += day.revenue ?? 0;
    if (day.d === today) onDay += day.revenue ?? 0;
  }
  return { today: onDay, d7 };
}

/** Each game's own numbers, read the same way for the overview. */
export async function summary(game: Game, fetcher: typeof fetch, now: () => number): Promise<Summary> {
  const call = (tool: string, args: Record<string, unknown> = {}) => callTool(game, fetcher, tool, args) as Promise<Obj>;
  const today = new Date(now()).toISOString().slice(0, 10);
  if (game.id === 'frank') {
    const [stats, queue] = await Promise.all([call('admin_stats'), call('admin_queue')]);
    const o = stats.overview ?? {};
    return {
      players: o.players ?? null,
      playersAre: 'devices',
      new24: o.players24 ?? null,
      active24: o.active24 ?? null,
      labels: PLAYED,
      revenue: { ...fromDays(stats.days ?? [], today), d30: null, all: o.revenue ?? null },
      pending: [{ label: 'Levels to review', count: queue.waiting ?? 0, tab: 'review' }],
    };
  }
  if (game.id === 'crabby') {
    const o = (await call('admin_overview')).overview ?? {};
    return {
      players: o.players ?? null,
      playersAre: 'devices',
      new24: o.players24 ?? null,
      active24: o.active24 ?? null,
      labels: PLAYED,
      revenue: null,
      pending: [{ label: 'Open reports', count: o.reportsOpen ?? 0, tab: 'reports' }],
    };
  }
  if (game.id === 'mahj') {
    const x = await call('admin_overview');
    const o = x.overview ?? {};
    return {
      players: o.players ?? null,
      playersAre: 'devices',
      new24: o.players24 ?? null,
      active24: o.active24 ?? null,
      labels: PLAYED,
      revenue: { ...fromDays(x.days ?? [], today), d30: null, all: o.revenue ?? null },
      pending: [
        { label: 'Waiting for a decision', count: o.queue ?? 0, tab: 'queue' },
        { label: 'Open reports', count: o.reportsOpen ?? 0, tab: 'reports' },
      ],
    };
  }
  const [day, week, month] = await Promise.all([call('admin_overview', { days: 1 }), call('admin_overview', { days: 7 }), call('admin_overview', { days: 30 })]);
  const cents = (usd: unknown) => (typeof usd === 'number' ? Math.round(usd * 100) : null);
  return {
    players: day.accounts ?? null,
    playersAre: 'accounts',
    new24: day.recent?.made ?? null,
    active24: day.recent?.opened ?? null,
    labels: ['Made today', 'Opened today'],
    revenue: { today: cents(day.recent?.revenue_usd), d7: cents(week.recent?.revenue_usd), d30: cents(month.recent?.revenue_usd), all: cents(day.all_time?.revenue_usd) },
    pending: [
      { label: 'Open reports', count: day.open_reports ?? 0, tab: 'reports' },
      { label: 'Failed jobs', count: day.failed_jobs ?? 0, tab: 'jobs' },
    ],
  };
}
