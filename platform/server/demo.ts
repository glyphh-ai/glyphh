import { randomUUID } from 'node:crypto';
import { Hono, type Context } from 'hono';
import { getCookie, setCookie } from 'hono/cookie';
import { serveStatic } from '@hono/node-server/serve-static';

/**
 * demo.glyphh.ai: Ada deciding expense claims, open to anyone, no sign-in. The page (demo/public) calls /api here;
 * these handlers hold the demo's Ada Cloud key (DEMO_GLYPHH_API_KEY) and never send it to the browser.
 *
 * The key can reach every model in its org, so the handlers reach one: `launch-demo-expenses`, named here and
 * nowhere else, with decide and record only (reset makes it again from the 40 past expenses in demo/history.json).
 * Every call is bounded: a visitor's calls a minute and a day, the demo's Ada calls a day, the precedents a take can
 * add, and the model goes back to the 40 an hour after anything was recorded into it.
 */

export const MODEL = 'launch-demo-expenses';

export type DemoConfig = {
  /** The host the demo answers on (`DEMO_HOST`, default demo.glyphh.ai). */
  host: string;
  /** The demo's Ada Cloud key (`DEMO_GLYPHH_API_KEY`). Unset: the page shows, the API answers 503. */
  key: string | undefined;
  adaUrl: string;
  /** Ada calls a day for the whole demo (`DEMO_DAILY_CALLS`, default 150), so the org's plan is never spent by it. */
  dailyCalls: number;
};

export function readDemoConfig(env: NodeJS.ProcessEnv = process.env): DemoConfig {
  const daily = Number(env.DEMO_DAILY_CALLS);
  return {
    host: (env.DEMO_HOST?.trim() || 'demo.glyphh.ai').toLowerCase(),
    key: env.DEMO_GLYPHH_API_KEY?.trim() || undefined,
    adaUrl: (env.GLYPHH_ADA_URL?.trim() || 'https://ada.glyphh.ai').replace(/\/$/, ''),
    dailyCalls: Number.isInteger(daily) && daily > 0 ? daily : 150,
  };
}

/** The host a request was made to, without its port. */
export function hostOf(req: Request): string {
  const host = req.headers.get('host') ?? new URL(req.url).host;
  return host.replace(/:\d+$/, '').toLowerCase();
}

export const LIMITS = {
  /** Decides and records, per visitor (their address). */
  perMinute: 10,
  perDay: 100,
  /** Resets, per visitor. */
  resetEveryMs: 5 * 60 * 1000,
  /** Precedents a take can add before the model goes back to the 40. */
  added: 20,
  /** An hour after the first thing recorded, the model goes back to the 40. */
  resetAfterMs: 60 * 60 * 1000,
  bodyBytes: 4096,
};

const MINUTE = 60 * 1000;
const DAY = 24 * 60 * MINUTE;
const VISITOR_COOKIE = 'glyphh_demo';

const POLICIES = ['within limit', 'over limit, pre-approved', 'over limit, not pre-approved'] as const;
type Policy = (typeof POLICIES)[number];
type Outcome = 'approve' | 'reject';

export type Claim = {
  employee: string;
  department: string;
  category: string;
  amount: number;
  receipt: boolean;
  policy: Policy;
  description: string;
};

export type HistoryRow = Claim & { ref: string; date: string; outcome: Outcome };
type Row = HistoryRow & { id: string; added?: boolean; by?: string };

/** What Ada is shown of an expense. Who filed it and when are for people; the decision rests on these. */
export const SPEC = {
  name: MODEL,
  layers: [
    {
      name: 'expense',
      segments: [
        {
          name: 'claim',
          roles: [
            { name: 'ref', key_part: true, similarity_weight: 0 },
            { name: 'department', similarity_weight: 0.3 },
            { name: 'category' },
            { name: 'amount', numeric_config: { min_value: 0, max_value: 3000, bin_width: 100 } },
            { name: 'receipt' },
            { name: 'policy' },
            { name: 'description', text_encoding: 'bag_of_words', similarity_weight: 0.4 },
          ],
        },
      ],
    },
  ],
  // Under 75% sure, Ada says so and a person decides.
  output: { ask_below: 0.75 },
};

const asData = (c: Claim, ref?: string) => ({
  expense: {
    claim: {
      ...(ref ? { ref } : {}),
      department: c.department,
      category: c.category,
      amount: c.amount,
      receipt: c.receipt ? 'yes' : 'no',
      policy: c.policy,
      description: c.description,
    },
  },
});

export class Refusal extends Error {
  constructor(
    readonly status: 400 | 403 | 413 | 429 | 502 | 503,
    message: string,
    readonly retryAfter?: number,
  ) {
    super(message);
  }
}

const WORDS = /^[a-z][a-z &-]{0,39}$/;
const TEXT = /^[\p{L}\p{N} .,'&()\-/:$#+!?]*$/u;

function text(value: unknown, name: string, max: number, required = true): string {
  const s = typeof value === 'string' ? value.trim().replace(/\s+/g, ' ') : '';
  if (required && !s) throw new Refusal(400, `Fill in the ${name}.`);
  if (s.length > max) throw new Refusal(400, `The ${name} is too long (${max} characters at most).`);
  if (!TEXT.test(s)) throw new Refusal(400, `The ${name} has characters the demo does not take.`);
  return s;
}

function words(value: unknown, name: string): string {
  const s = typeof value === 'string' ? value.trim().toLowerCase().replace(/\s+/g, ' ') : '';
  if (!WORDS.test(s)) throw new Refusal(400, `The ${name} takes letters and spaces only, 40 at most.`);
  return s;
}

/** A claim from the page, as the model takes it; anything else is refused. */
export function readClaim(value: unknown): Claim {
  if (typeof value !== 'object' || value === null) throw new Refusal(400, 'No expense was sent.');
  const c = value as Record<string, unknown>;
  const amount = Number(c.amount);
  if (typeof c.amount !== 'number' || !Number.isFinite(amount) || amount < 0 || amount > 3000) {
    throw new Refusal(400, 'The amount is from $0 to $3,000.');
  }
  if (typeof c.receipt !== 'boolean') throw new Refusal(400, 'Say whether a receipt is attached.');
  if (!POLICIES.includes(c.policy as Policy)) throw new Refusal(400, 'The policy check is not one the demo knows.');
  return {
    employee: text(c.employee, 'employee', 60, false),
    department: words(c.department, 'department'),
    category: words(c.category, 'category'),
    amount: Math.round(amount * 100) / 100,
    receipt: c.receipt,
    policy: c.policy as Policy,
    description: text(c.description, 'description', 120),
  };
}

/** Calls kept per key over a window: allowed while fewer than `max` fall inside it. */
export class Window {
  private readonly hits = new Map<string, number[]>();
  constructor(
    private readonly max: number,
    private readonly ms: number,
    private readonly maxKeys = 10_000,
  ) {}

  /** Seconds until the next call is allowed, or 0 when it is allowed now (and counted). */
  take(key: string, now: number): number {
    const kept = (this.hits.get(key) ?? []).filter((t) => now - t < this.ms);
    if (kept.length >= this.max) return Math.max(1, Math.ceil((kept[0]! + this.ms - now) / 1000));
    kept.push(now);
    this.hits.delete(key);
    this.hits.set(key, kept);
    if (this.hits.size > this.maxKeys) this.hits.delete(this.hits.keys().next().value!);
    return 0;
  }
}

type Deps = {
  config: DemoConfig;
  history: HistoryRow[];
  fetch?: typeof fetch;
  now?: () => number;
  secureCookies?: boolean;
};

export function createDemo({ config, history, fetch: fetcher = fetch, now = Date.now, secureCookies = true }: Deps) {
  const app = new Hono();
  const base = `${config.adaUrl}/v1/models/${encodeURIComponent(MODEL)}`;

  let ledger: Row[] = [];
  let next = 2081;
  let added = 0;
  let dirtySince: number | null = null;
  let ready: Promise<void> | null = null;
  let queue: Promise<unknown> = Promise.resolve();
  let day = Math.floor(now() / DAY);
  let calls = 0;

  const minute = new Window(LIMITS.perMinute, MINUTE);
  const daily = new Window(LIMITS.perDay, DAY);
  const resets = new Window(1, LIMITS.resetEveryMs);

  /** One call to Ada Cloud, counted against the demo's day. */
  async function ada<T>(method: string, url: string, body?: unknown): Promise<T> {
    const today = Math.floor(now() / DAY);
    if (today !== day) {
      day = today;
      calls = 0;
    }
    if (calls >= config.dailyCalls) throw new Refusal(429, 'The demo has had its fill of Ada for today. It opens again at midnight UTC.');
    calls += 1;
    const headers: Record<string, string> = { authorization: `Bearer ${config.key}`, accept: 'application/json' };
    if (body !== undefined) headers['content-type'] = 'application/json';
    if (method !== 'GET') headers['idempotency-key'] = randomUUID();
    let res: Response;
    try {
      res = await fetcher(url, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) });
    } catch {
      throw new Refusal(502, 'Ada Cloud could not be reached.');
    }
    const json = (await res.json().catch(() => ({}))) as T & { error?: { code?: string } };
    if (res.status === 404 && method === 'DELETE') return json;
    if (res.status === 429) throw new Refusal(429, 'Ada Cloud is busy. Try again in a moment.', Number(res.headers.get('retry-after')) || 5);
    if (!res.ok) throw new Refusal(502, `Ada Cloud did not answer (${json.error?.code ?? res.status}).`);
    return json;
  }

  const record = (cases: { data: unknown; outcome: Outcome }[]) =>
    ada<{ ids?: string[]; precedents?: number }>('POST', `${base}/record_many`, { cases });

  async function loadHistory() {
    const got = await record(history.map((c) => ({ data: asData(c, c.ref), outcome: c.outcome })));
    const ids = got.ids ?? [];
    ledger = history.map((c, i) => ({ ...c, id: ids[i] ?? c.ref }));
    next = 2081;
    added = 0;
    dirtySince = null;
  }

  /** Back to the 40 past expenses and nothing else: the model made again, the history recorded into it. */
  async function reset() {
    await ada('DELETE', `${base}?confirm=${encodeURIComponent(MODEL)}`);
    await ada('POST', `${config.adaUrl}/v1/models`, { name: MODEL, spec: SPEC });
    await loadHistory();
  }

  /** The model as the demo needs it, once per process: there, holding exactly the history. */
  async function prepare() {
    const { models = [] } = await ada<{ models?: { name: string; precedents?: number }[] }>('GET', `${config.adaUrl}/v1/models`);
    const found = models.find((m) => m.name === MODEL);
    if (found && found.precedents === history.length) await loadHistory();
    else await reset();
  }

  /** Ada's work, one at a time, after the model is ready; a take that has run long or full goes back to the 40 first. */
  function serial<T>(work: () => Promise<T>): Promise<T> {
    const run = async () => {
      ready ??= prepare().catch((e) => {
        ready = null;
        throw e;
      });
      await ready;
      if (dirtySince !== null && now() - dirtySince >= LIMITS.resetAfterMs) await reset();
      return work();
    };
    const out = queue.then(run, run);
    queue = out.catch(() => undefined);
    return out;
  }

  const addressOf = (c: Context) =>
    c.req.header('cf-connecting-ip') ?? c.req.header('fly-client-ip') ?? c.req.header('x-forwarded-for')?.split(',')[0]?.trim() ?? 'unknown';

  const visitorOf = (c: Context) => {
    let id = getCookie(c, VISITOR_COOKIE);
    if (!id || !/^[a-f0-9-]{36}$/.test(id)) {
      id = randomUUID();
      setCookie(c, VISITOR_COOKIE, id, { httpOnly: true, secure: secureCookies, sameSite: 'Lax', path: '/', maxAge: 30 * 24 * 3600 });
    }
    return id;
  };

  /** The ledger as one visitor sees it: what others recorded keeps its expense, never their name. */
  const view = (visitor: string) =>
    ledger.map(({ by, ...row }) => (row.added && by !== visitor ? { ...row, employee: 'Another visitor' } : row));

  const limit = (c: Context) => {
    const who = addressOf(c);
    const wait = minute.take(who, now()) || daily.take(who, now());
    if (wait) throw new Refusal(429, 'That is a lot of questions. Give it a minute.', wait);
  };

  async function readBody(c: Context): Promise<Record<string, unknown>> {
    const raw = await c.req.text();
    if (raw.length > LIMITS.bodyBytes) throw new Refusal(413, 'That is more than an expense.');
    try {
      const body: unknown = raw ? JSON.parse(raw) : {};
      return typeof body === 'object' && body !== null ? (body as Record<string, unknown>) : {};
    } catch {
      throw new Refusal(400, 'The demo could not read that.');
    }
  }

  app.use('/api/*', async (c, next) => {
    c.header('cache-control', 'no-store');
    if (!config.key) throw new Refusal(503, 'The demo is not set up yet.');
    if (c.req.method !== 'GET') {
      const site = c.req.header('sec-fetch-site');
      const same = site ? site === 'same-origin' : c.req.header('origin') === `https://${config.host}`;
      if (!same) throw new Refusal(403, 'Writes come from the demo page only.');
    }
    await next();
  });

  app.get('/api/state', async (c) => {
    const visitor = visitorOf(c);
    await serial(async () => undefined);
    return c.json({ model: MODEL, ledger: view(visitor) });
  });

  app.post('/api/decide', async (c) => {
    const claim = readClaim((await readBody(c)).claim);
    limit(c);
    const d = await serial(async () => {
      const started = performance.now();
      const body = await ada<{ outcome?: string; probabilities?: Record<string, number>; ask?: boolean; receipts?: { id: string; sim: number; outcome: string }[] }>(
        'POST',
        `${config.adaUrl}/v1/decide`,
        { model: MODEL, data: asData(claim) },
      );
      return { ...body, ms: Math.round(performance.now() - started) };
    });
    return c.json({
      outcome: d.outcome ?? null,
      probabilities: d.probabilities ?? {},
      ask: Boolean(d.ask),
      receipts: (d.receipts ?? []).map((r) => ({ id: r.id, sim: r.sim, outcome: r.outcome })),
      ms: d.ms,
    });
  });

  app.post('/api/record', async (c) => {
    const body = await readBody(c);
    const claim = readClaim(body.claim);
    if (body.outcome !== 'approve' && body.outcome !== 'reject') throw new Refusal(400, 'Approve or reject.');
    const outcome: Outcome = body.outcome;
    const visitor = visitorOf(c);
    limit(c);
    const row = await serial(async () => {
      if (added >= LIMITS.added) await reset();
      const ref = `E-${next}`;
      const got = await record([{ data: asData(claim, ref), outcome }]);
      next += 1;
      added += 1;
      // The model holds more than the demo put there: the next record starts from the 40 again.
      if ((got.precedents ?? 0) > history.length + LIMITS.added) added = LIMITS.added;
      dirtySince ??= now();
      const row: Row = { ...claim, ref, outcome, id: got.ids?.[0] ?? ref, date: new Date(now()).toISOString().slice(0, 10), added: true, by: visitor };
      ledger.push(row);
      return row;
    });
    const { by: _by, ...shown } = row;
    return c.json(shown);
  });

  app.post('/api/reset', async (c) => {
    const visitor = visitorOf(c);
    const wait = resets.take(addressOf(c), now());
    if (wait) throw new Refusal(429, 'The demo was reset a moment ago.', wait);
    // Nothing recorded since the last reset: the model already holds exactly the 40, so Ada is not called.
    await serial(async () => {
      if (added > 0) await reset();
    });
    return c.json({ model: MODEL, ledger: view(visitor) });
  });

  app.all('/api/*', () => {
    throw new Refusal(403, 'The demo answers decide, record and reset only.');
  });

  app.onError((e, c) => {
    if (e instanceof Refusal) {
      if (e.retryAfter) c.header('retry-after', String(e.retryAfter));
      c.header('cache-control', 'no-store');
      return c.json({ error: e.message }, e.status);
    }
    console.error('demo:', e);
    return c.json({ error: 'The demo hit a snag. Try again.' }, 502);
  });

  return app;
}

/** The demo's page (demo/public) after its /api; any other path is 404, never the platform's. */
export function serveDemoPage(app: Hono, root = 'demo/public') {
  app.use('*', serveStatic({ root }));
  app.notFound((c) => c.text('Not found', 404));
  return app;
}
