import { http, HttpResponse } from 'msw';
import type { Bot, BotModel, BotRun, Connection, ConnectionTool, ConnectorApp } from '@/api/bots';
import { apiError } from './server';

/**
 * Bots and connections as the server answers them (/v1/bots, /v1/bot-runs, /v1/connections), held in state so each
 * write shows on the next read. A run is queued, then running, then done, one step per read of it.
 */
const v1 = (path: string) => `*/api/v1${path}`;
const at = '2026-11-20T09:00:00Z';

export const look = { head: 'classic', tail: 'spike', eye: 'dot', extra: 'none', accessory: 'none', pose: 'stand' } as const;

export const gmail = (): Connection => ({ id: 'c-gmail', app: 'gmail', app_name: 'Gmail', app_icon: null, account_id: 'apn_1', label: 'chris@example.com', created_at: at });
export const slack = (): Connection => ({ id: 'c-slack', app: 'slack', app_name: 'Slack', app_icon: null, account_id: 'apn_2', label: null, created_at: at });

export const toolsOf: Record<string, ConnectionTool[]> = {
  'c-gmail': [
    { key: 'gmail-send-email', name: 'Send email', description: 'Sends an email.' },
    { key: 'gmail-find-email', name: 'Find email', description: 'Finds emails that match a search.' },
    { key: 'gmail-delete-email', name: 'Delete email', description: null },
  ],
  'c-slack': [{ key: 'slack-send-message', name: 'Send message', description: 'Posts in a channel.' }],
};

export const apps: ConnectorApp[] = [
  { slug: 'gmail', name: 'Gmail', description: 'Google’s email.', icon: null },
  { slug: 'slack', name: 'Slack', description: 'Team chat.', icon: null },
  { slug: 'notion', name: 'Notion', description: 'Notes and docs.', icon: null },
];

export const botModels: BotModel[] = [
  { id: 'claude-sonnet-5-5', name: 'Claude Sonnet 5.5', input_cents_per_mtok: 300, output_cents_per_mtok: 1500, default: true },
  { id: 'claude-haiku-5-5', name: 'Claude Haiku 5.5', input_cents_per_mtok: 100, output_cents_per_mtok: 500, default: false },
];

export const inbox = (given: Partial<Bot> = {}): Bot => ({
  id: 'b-inbox',
  slug: 'inbox-helper',
  name: 'Inbox helper',
  summary: 'Answers the easy emails.',
  look: { ...look },
  instructions: 'Read new emails and answer the easy ones.',
  model: 'claude-sonnet-5-5',
  models: [],
  connections: [{ connection_id: 'c-gmail', app: 'gmail', app_name: 'Gmail', tools: ['gmail-find-email'] }],
  limits: { max_turns: 20, usd_per_run: 1 },
  created_at: at,
  updated_at: at,
  last_run: null,
  ...given,
});

const slugOf = (name: string) => name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');

export function botsFake({ bots = [inbox()], connections = [gmail(), slack()], off = false } = {}) {
  const state = {
    bots: structuredClone(bots),
    connections: structuredClone(connections),
    runs: [] as BotRun[],
    reads: new Map<string, number>(),
    /** Connections that appear on the next sync, as if signed in to in the popup. */
    pending: [] as Connection[],
    seen: [] as string[],
    bodies: [] as unknown[],
  };
  let next = 1;
  const off503 = () => apiError(503, 'E_UNAVAILABLE', 'Connections are not set up.', { reason: 'pipedream_off' });
  const find = (slug: unknown) => state.bots.find((b) => b.slug === slug);
  const missing = () => apiError(404, 'E_NOT_FOUND', 'There is no such bot.');
  const stamp = () => new Date(Date.parse(at) + next++ * 1000).toISOString();

  const handlers = [
    http.get(v1('/bots/models'), () => HttpResponse.json({ models: botModels })),
    http.get(v1('/bots'), () => HttpResponse.json({ bots: state.bots })),
    http.post(v1('/bots'), async ({ request }) => {
      const body = (await request.json()) as Partial<Bot>;
      state.bodies.push(body);
      const slug = slugOf(body.name ?? '');
      if (find(slug)) return apiError(409, 'E_CONFLICT', 'A bot has that name already.');
      const bot = inbox({ ...body, id: `b-${next++}`, slug, summary: body.summary ?? null, connections: [], models: body.models ?? [] });
      state.bots.push(bot);
      state.seen.push(`create ${slug}`);
      return HttpResponse.json(bot, { status: 201 });
    }),
    http.get(v1('/bots/:slug'), ({ params }) => (find(params.slug) ? HttpResponse.json(find(params.slug)) : missing())),
    http.patch(v1('/bots/:slug'), async ({ params, request }) => {
      const bot = find(params.slug);
      if (!bot) return missing();
      const change = (await request.json()) as Partial<Bot>;
      state.bodies.push(change);
      Object.assign(bot, change, { updated_at: stamp() });
      if (change.name) bot.slug = slugOf(change.name);
      state.seen.push(`update ${params.slug}`);
      return HttpResponse.json(bot);
    }),
    http.delete(v1('/bots/:slug'), ({ params }) => {
      if (!find(params.slug)) return missing();
      state.bots = state.bots.filter((b) => b.slug !== params.slug);
      state.seen.push(`delete ${params.slug}`);
      return new HttpResponse(null, { status: 204 });
    }),
    http.put(v1('/bots/:slug/connections'), async ({ params, request }) => {
      const bot = find(params.slug);
      if (!bot) return missing();
      const { connections: scopes } = (await request.json()) as { connections: { connection_id: string; tools: string[] }[] };
      state.bodies.push(scopes);
      bot.connections = scopes.map((s) => {
        const c = state.connections.find((x) => x.id === s.connection_id)!;
        return { connection_id: s.connection_id, app: c.app, app_name: c.app_name, tools: s.tools };
      });
      bot.updated_at = stamp();
      state.seen.push(`scope ${params.slug}`);
      return HttpResponse.json(bot);
    }),
    http.get(v1('/bots/:slug/runs'), ({ params }) => HttpResponse.json({ runs: state.runs.filter((r) => r.bot_slug === params.slug) })),
    http.post(v1('/bots/:slug/runs'), async ({ params, request }) => {
      const bot = find(params.slug);
      if (!bot) return missing();
      const { input } = (await request.json()) as { input: string };
      const created = stamp();
      const run: BotRun = {
        id: `r-${next++}`,
        bot_slug: bot.slug,
        status: 'queued',
        input,
        output: null,
        error: null,
        steps: [],
        input_tokens: 0,
        output_tokens: 0,
        cost_micros: 0,
        created_at: created,
        started_at: null,
        finished_at: null,
      };
      state.runs.unshift(run);
      bot.last_run = { id: run.id, status: 'queued', created_at: created };
      state.seen.push(`run ${bot.slug}`);
      return HttpResponse.json(run, { status: 202 });
    }),
    http.get(v1('/bot-runs/:id'), ({ params }) => {
      const run = state.runs.find((r) => r.id === params.id);
      if (!run) return apiError(404, 'E_NOT_FOUND', 'There is no such run.');
      const reads = (state.reads.get(run.id) ?? 0) + 1;
      state.reads.set(run.id, reads);
      if (reads === 2) run.status = 'running';
      if (reads >= 3 && run.status === 'running') {
        Object.assign(run, {
          status: 'done',
          output: 'Answered 2 emails.',
          steps: [
            { kind: 'tool', name: 'gmail-find-email', input: { q: 'is:unread' }, output: '2 emails', is_error: false, at },
            { kind: 'text', name: null, input: null, output: 'Both are easy.', is_error: false, at },
          ],
          input_tokens: 1200,
          output_tokens: 300,
          cost_micros: 8100,
          finished_at: stamp(),
        });
        const bot = find(run.bot_slug);
        if (bot?.last_run?.id === run.id) bot.last_run.status = 'done';
      }
      return HttpResponse.json(run);
    }),

    http.get(v1('/connections'), () => (off ? off503() : HttpResponse.json({ connections: state.connections }))),
    http.get(v1('/connections/apps'), ({ request }) => {
      if (off) return off503();
      const q = (new URL(request.url).searchParams.get('q') ?? '').toLowerCase();
      return HttpResponse.json({ apps: apps.filter((a) => a.name.toLowerCase().includes(q)), next_cursor: null });
    }),
    http.post(v1('/connections/link'), async ({ request }) => {
      if (off) return off503();
      const { app } = (await request.json()) as { app: string };
      state.seen.push(`link ${app}`);
      const found = apps.find((a) => a.slug === app)!;
      state.pending.push({ id: `c-${app}`, app, app_name: found.name, app_icon: null, account_id: `apn_${app}`, label: null, created_at: at });
      return HttpResponse.json({ url: `https://pipedream.test/connect/${app}`, expires_at: '2026-11-20T10:00:00Z' });
    }),
    http.post(v1('/connections/sync'), () => {
      state.seen.push('sync');
      state.connections.push(...state.pending.splice(0));
      return HttpResponse.json({ connections: state.connections });
    }),
    http.delete(v1('/connections/:id'), ({ params }) => {
      state.connections = state.connections.filter((c) => c.id !== params.id);
      for (const bot of state.bots) bot.connections = bot.connections.filter((c) => c.connection_id !== params.id);
      state.seen.push(`remove ${params.id}`);
      return new HttpResponse(null, { status: 204 });
    }),
    http.get(v1('/connections/:id/tools'), ({ params }) => HttpResponse.json({ tools: toolsOf[String(params.id)] ?? [] })),
  ];
  return { state, handlers };
}
