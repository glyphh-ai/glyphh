import { http, HttpResponse } from 'msw';
import type { Bot, BotKey, BotModels, BotRun, Connection, ConnectionTool, ConnectorApp, Permission } from '@/api/bots';
import type { BotTemplate } from '@/api/botTemplates';
import { apiError } from './server';

/**
 * Bots, templates and connections as the server answers them (/v1/bots, /v1/bot-runs, /v1/bot-approvals,
 * /v1/bot-templates, /v1/bot-key, /v1/connections), held in state so each write shows on the next read. A run is
 * queued, then running, then waits on the person (needs_input) with a batch question, one step per read of it; an
 * answer finishes it.
 */
const v1 = (path: string) => `*/api/v1${path}`;
const at = '2026-11-20T09:00:00Z';

export const look = { head: 'classic', tail: 'spike', eye: 'dot', extra: 'none', accessory: 'none', pose: 'stand' } as const;

export const gmail = (): Connection => ({
  id: 'c-gmail',
  app: 'gmail',
  app_name: 'Gmail',
  app_icon: null,
  account_id: 'apn_1',
  label: 'chris@example.com',
  permissions: { 'gmail-find-email': 'allow' },
  created_at: at,
});
export const slack = (): Connection => ({
  id: 'c-slack',
  app: 'slack',
  app_name: 'Slack',
  app_icon: null,
  account_id: 'apn_2',
  label: null,
  permissions: {},
  created_at: at,
});

const tools: Record<string, Omit<ConnectionTool, 'permission'>[]> = {
  'c-gmail': [
    { key: 'gmail-send-email', name: 'Send email', description: 'Sends an email.' },
    { key: 'gmail-find-email', name: 'Find email', description: 'Finds emails that match a search.' },
    { key: 'gmail-delete-email', name: 'Delete email', description: null },
  ],
  'c-slack': [{ key: 'slack-send-message', name: 'Send message', description: 'Posts in a channel.' }],
};
/** A connection's tools with the permission it holds for each (one never set asks). */
export const toolsOf = (c: Connection): ConnectionTool[] =>
  (tools[c.id] ?? []).map((t) => ({ ...t, permission: c.permissions[t.key] ?? 'ask' }));

export const apps: ConnectorApp[] = [
  { slug: 'gmail', name: 'Gmail', description: 'Google’s email.', icon: null },
  { slug: 'slack', name: 'Slack', description: 'Team chat.', icon: null },
  { slug: 'notion', name: 'Notion', description: 'Notes and docs.', icon: null },
];

const model = (n: number, name: string, input: number, output: number, isDefault = false) => ({
  id: `claude-${name.toLowerCase().replace(/[^a-z0-9]+/g, '-')}`,
  name: `Claude ${name}`,
  input_cents_per_mtok: Math.round(input * 1.2),
  output_cents_per_mtok: Math.round(output * 1.2),
  own_key_input_cents_per_mtok: Math.round(input * 0.2),
  own_key_output_cents_per_mtok: Math.round(output * 0.2),
  default: isDefault,
  n,
});
/** Twelve models: more than one page of the picker. */
export const botModels: BotModels = {
  markup_pct: 20,
  models: [
    model(1, 'Sonnet 5.5', 300, 1500, true),
    model(2, 'Haiku 5.5', 100, 500),
    model(3, 'Opus 5.5', 1500, 7500),
    model(4, 'Fable 5.1', 2000, 10000),
    model(5, 'Sonnet 5', 300, 1500),
    model(6, 'Haiku 5', 80, 400),
    model(7, 'Opus 5', 1500, 7500),
    model(8, 'Sonnet 4.6', 300, 1500),
    model(9, 'Haiku 4.6', 80, 400),
    model(10, 'Opus 4.6', 1500, 7500),
    model(11, 'Sonnet 4.5', 300, 1500),
    model(12, 'Haiku 4.5', 100, 500),
  ].map(({ n: _, ...m }) => m),
};

export const spec = () => ({
  loop: [
    { step: 'fetch', tool: 'gmail-find-email' },
    { step: 'decide', gate: 'easy' },
    { step: 'reply', tool: 'gmail-send-email', ask: true },
  ],
  gates: { easy: { options: ['answer', 'leave'] } },
});

export const inbox = (given: Partial<Bot> = {}): Bot => ({
  id: 'b-inbox',
  slug: 'inbox-helper',
  name: 'Inbox helper',
  summary: 'Answers the easy emails.',
  look: { ...look },
  instructions: 'Read new emails and answer the easy ones.',
  model: 'claude-sonnet-5-5',
  spec: spec(),
  skills: { tone: 'Write short, warm replies.' },
  gate_models: ['inbox-helper-easy'],
  connections: [{ connection_id: 'c-gmail', app: 'gmail', app_name: 'Gmail', tools: ['gmail-find-email'] }],
  created_at: at,
  updated_at: at,
  last_run: null,
  ...given,
});

export const triage = (): BotTemplate => ({
  slug: 'support-triage',
  name: 'Support triage',
  summary: 'Sorts new tickets and posts the urgent ones.',
  description: 'Reads each new support email, decides how urgent it is, and posts the urgent ones in Slack.',
  look: { ...look, head: 'round' } as BotTemplate['look'],
  model: 'claude-haiku-5-5',
  spec: spec(),
  skills: { urgency: 'Urgent means a customer is down.' },
  required_apps: [
    { slug: 'gmail', name: 'Gmail', icon: null },
    { slug: 'notion', name: 'Notion', icon: null },
  ],
  tools: ['gmail-find-email', 'slack-send-message'],
  gates: ['urgent'],
});
export const digest = (): BotTemplate => ({
  ...triage(),
  slug: 'daily-digest',
  name: 'Daily digest',
  summary: 'A morning summary of yesterday.',
  description: 'Every morning it writes what happened yesterday.',
  required_apps: [{ slug: 'slack', name: 'Slack', icon: null }],
  tools: ['slack-send-message'],
  gates: [],
});

export const waiting = (given: Partial<BotRun> = {}): BotRun => ({
  id: 'r-wait',
  bot_slug: 'inbox-helper',
  status: 'needs_input',
  input: 'Check the inbox',
  output: '',
  error: '',
  log: ['Found 2 emails.', 'Asking which to answer.'],
  data: { emails: 2 },
  question: {
    question: 'Answer these emails?',
    options: ['answer', 'leave'],
    batch: [
      { n: 1, label: 'Lunch on Friday?' },
      { n: 2, label: 'Invoice overdue' },
    ],
    answer_with: '1=answer 2=leave',
  },
  input_tokens: 900,
  output_tokens: 120,
  cost_micros: 4200,
  own_key: false,
  created_at: at,
  started_at: at,
  finished_at: null,
  ...given,
});

const slugOf = (name: string) => name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');

type Options = {
  bots?: Bot[];
  connections?: Connection[];
  runs?: BotRun[];
  /** The Marketplace's bots, answered by this fake; none leaves /v1/bot-templates to the test. */
  templates?: BotTemplate[];
  key?: BotKey;
  off?: boolean;
  /** Problems the server finds in every spec it is given (422). */
  problems?: string[];
};

export function botsFake({
  bots = [inbox()],
  connections = [gmail(), slack()],
  runs = [],
  templates,
  key = { set: false, hint: '', set_at: null, glyphh_key: true },
  off = false,
  problems = [],
}: Options = {}) {
  const state = {
    bots: structuredClone(bots),
    connections: structuredClone(connections),
    runs: structuredClone(runs),
    key: { ...key },
    reads: new Map<string, number>(),
    /** Connections that appear on the next sync, as if signed in to in the popup. */
    pending: [] as Connection[],
    seen: [] as string[],
    bodies: [] as unknown[],
  };
  let next = 1;
  const off503 = () => apiError(503, 'E_UNAVAILABLE', 'Connections are not set up.', { reason: 'pipedream_off' });
  const find = (slug: unknown) => state.bots.find((b) => b.slug === slug);
  const run = (id: unknown) => state.runs.find((r) => r.id === id);
  const missing = () => apiError(404, 'E_NOT_FOUND', 'There is no such bot.');
  const noRun = () => apiError(404, 'E_NOT_FOUND', 'There is no such run.');
  const stamp = () => new Date(Date.parse(at) + next++ * 1000).toISOString();
  const bad = () => apiError(422, 'E_INVALID', 'The bot is not valid.', { problems });
  const settle = (r: BotRun) => {
    const bot = find(r.bot_slug);
    if (bot?.last_run?.id === r.id) bot.last_run.status = r.status;
  };

  const handlers = [
    http.get(v1('/bots/models'), () => HttpResponse.json(botModels)),
    http.get(v1('/bots'), ({ request }) => {
      // As the server: words of its name, slug or summary.
      const q = (new URL(request.url).searchParams.get('q') ?? '').toLowerCase().trim();
      if (q) state.seen.push(`search ${q}`);
      return HttpResponse.json({ bots: state.bots.filter((b) => !q || `${b.name} ${b.slug} ${b.summary ?? ''}`.toLowerCase().includes(q)) });
    }),
    http.post(v1('/bots'), async ({ request }) => {
      const body = (await request.json()) as Partial<Bot>;
      state.bodies.push(body);
      if (problems.length && body.spec) return bad();
      const slug = slugOf(body.name ?? '');
      if (find(slug)) return apiError(409, 'E_CONFLICT', 'A bot has that name already.');
      const bot = inbox({ spec: {}, skills: {}, gate_models: [], ...body, id: `b-${next++}`, slug, summary: body.summary ?? null, connections: [] });
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
      if (problems.length && change.spec) return bad();
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
    http.get(v1('/bots/:slug/gates'), ({ params }) =>
      find(params.slug)
        ? HttpResponse.json({ gates: Object.fromEntries(find(params.slug)!.gate_models.map((g) => [g.replace(`${params.slug}-`, ''), { precedents: 14, asked: 6, right: 5 }])) })
        : missing(),
    ),
    http.get(v1('/bots/:slug/runs'), ({ params }) => HttpResponse.json({ runs: state.runs.filter((r) => r.bot_slug === params.slug) })),
    http.post(v1('/bots/:slug/runs'), async ({ params, request }) => {
      const bot = find(params.slug);
      if (!bot) return missing();
      const { input } = (await request.json()) as { input: string };
      const created = stamp();
      const made = waiting({
        id: `r-${next++}`,
        bot_slug: bot.slug,
        status: 'queued',
        input,
        log: [],
        data: {},
        question: null,
        input_tokens: 0,
        output_tokens: 0,
        cost_micros: 0,
        own_key: state.key.set,
        created_at: created,
        started_at: null,
      });
      state.runs.unshift(made);
      bot.last_run = { id: made.id, status: 'queued', created_at: created };
      state.seen.push(`run ${bot.slug}`);
      return HttpResponse.json(made, { status: 202 });
    }),
    http.get(v1('/bot-runs/:id'), ({ params }) => {
      const r = run(params.id);
      if (!r) return noRun();
      const reads = (state.reads.get(r.id) ?? 0) + 1;
      state.reads.set(r.id, reads);
      if (reads === 2 && r.status === 'queued') r.status = 'running';
      if (reads >= 3 && r.status === 'running') {
        const asked = waiting();
        Object.assign(r, { status: 'needs_input', log: asked.log, data: asked.data, question: asked.question, input_tokens: 900, output_tokens: 120, cost_micros: 4200 });
        settle(r);
      }
      return HttpResponse.json(r);
    }),
    http.post(v1('/bot-runs/:id/answer'), async ({ params, request }) => {
      const r = run(params.id);
      if (!r) return noRun();
      if (r.status !== 'needs_input') return apiError(409, 'E_CONFLICT', 'The run is not waiting on an answer.');
      const { answer } = (await request.json()) as { answer: unknown };
      state.bodies.push(answer);
      Object.assign(r, { status: 'done', question: null, output: 'Answered 1 email.', log: [...r.log, 'Answered.'], finished_at: stamp() });
      settle(r);
      state.seen.push(`answer ${r.id}`);
      return HttpResponse.json(r);
    }),
    http.post(v1('/bot-runs/:id/cancel'), ({ params }) => {
      const r = run(params.id);
      if (!r) return noRun();
      Object.assign(r, { status: 'skipped', question: null, finished_at: stamp() });
      settle(r);
      state.seen.push(`cancel ${r.id}`);
      return HttpResponse.json(r);
    }),
    http.post(v1('/bot-runs/:id/wrong'), async ({ params, request }) => {
      const r = run(params.id);
      if (!r) return noRun();
      const body = (await request.json()) as { outcome: string; gate?: string };
      state.bodies.push(body);
      state.seen.push(`wrong ${r.id}`);
      return HttpResponse.json({ gate: body.gate ?? 'easy', said: 'answer', now: body.outcome });
    }),
    http.get(v1('/bot-approvals'), () => HttpResponse.json({ runs: state.runs.filter((r) => r.status === 'needs_input') })),

    http.get(v1('/bot-key'), () => HttpResponse.json(state.key)),
    http.put(v1('/bot-key'), async ({ request }) => {
      const { key: given } = (await request.json()) as { key: string };
      if (!given.startsWith('sk-ant-')) return apiError(422, 'E_INVALID', 'That is not a Claude key.');
      state.key = { set: true, hint: `…${given.slice(-4)}`, set_at: at, glyphh_key: true };
      state.seen.push('key set');
      return HttpResponse.json(state.key);
    }),
    http.delete(v1('/bot-key'), () => {
      state.key = { set: false, hint: '', set_at: null, glyphh_key: true };
      state.seen.push('key removed');
      return HttpResponse.json(state.key);
    }),

    // The Marketplace's bots, only when given: without them a test's own handlers answer (msw goes on to the next).
    http.get(v1('/bot-templates'), ({ request }) => {
      if (!templates) return;
      const q = (new URL(request.url).searchParams.get('q') ?? '').toLowerCase();
      // As the server sends them: the apps a template needs are slugs.
      const served = templates
        .filter((t) => `${t.name} ${t.summary}`.toLowerCase().includes(q))
        .map(({ required_apps, ...t }) => ({ ...t, apps: required_apps.map((a) => a.slug) }));
      return HttpResponse.json({ templates: served });
    }),
    http.get(v1('/bot-templates/:slug'), ({ params }) => {
      if (!templates) return;
      const t = templates.find((x) => x.slug === params.slug);
      return t ? HttpResponse.json(t) : apiError(404, 'E_NOT_FOUND', 'There is no such template.');
    }),
    http.post(v1('/bot-templates/:slug/install'), async ({ params, request }) => {
      if (!templates) return;
      const t = templates.find((x) => x.slug === params.slug);
      if (!t) return apiError(404, 'E_NOT_FOUND', 'There is no such template.');
      const text = await request.text();
      const body = (text ? JSON.parse(text) : {}) as { name?: string };
      const name = body.name || t.name;
      const slug = slugOf(name);
      if (find(slug)) return apiError(409, 'E_CONFLICT', 'A bot has that name already.');
      // As the server: every app it needs connected first, then its tools scoped to the org's first connection of each.
      const missing = t.required_apps.map((a) => a.slug).filter((a) => !state.connections.some((c) => c.app === a));
      if (missing.length) return apiError(422, 'E_INVALID', `Connect ${missing.join(', ')} first: the bot uses it.`, { reason: 'connections', apps: missing });
      const scopes = t.required_apps.map((a) => {
        const c = state.connections.find((x) => x.app === a.slug)!;
        return { connection_id: c.id, app: c.app, app_name: c.app_name, tools: t.tools.filter((k) => k.startsWith(`${a.slug}-`)) };
      });
      const bot = inbox({
        id: `b-${next++}`,
        slug,
        name,
        summary: t.summary,
        look: t.look,
        instructions: t.description,
        model: t.model,
        spec: t.spec,
        skills: t.skills,
        gate_models: t.gates.map((g) => `${slug}-${g}`),
        connections: scopes,
      });
      state.bots.push(bot);
      state.seen.push(`install ${t.slug}`);
      return HttpResponse.json(bot, { status: 201 });
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
      state.pending.push({ id: `c-${app}`, app, app_name: found.name, app_icon: null, account_id: `apn_${app}`, label: null, permissions: {}, created_at: at });
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
    http.get(v1('/connections/:id/tools'), ({ params }) => {
      const c = state.connections.find((x) => x.id === params.id);
      return HttpResponse.json({ tools: c ? toolsOf(c) : [] });
    }),
    http.put(v1('/connections/:id/permissions'), async ({ params, request }) => {
      const c = state.connections.find((x) => x.id === params.id);
      if (!c) return apiError(404, 'E_NOT_FOUND', 'The org has no such connection.');
      const { permissions } = (await request.json()) as { permissions: Record<string, Permission> };
      state.bodies.push(permissions);
      c.permissions = { ...c.permissions, ...permissions };
      state.seen.push(`permissions ${c.id}`);
      return HttpResponse.json(c);
    }),
  ];
  return { state, handlers };
}
