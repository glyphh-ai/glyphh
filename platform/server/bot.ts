import { randomUUID } from 'node:crypto';
import { Hono, type Context } from 'hono';
import { getCookie, setCookie } from 'hono/cookie';
import { LIMITS as DEMO_LIMITS, Refusal, Window, type DemoConfig } from './demo.js';

/**
 * demo.glyphh.ai/bot: a bot that approves expenses and starts knowing nothing. The visitor makes up a rule and keeps
 * it to themselves; the bot works through 40 expenses, asking them where Ada is not sure or has little to stand on
 * and deciding alone otherwise; the visitor answers, and says when a decision made alone was wrong. Every answer is a precedent, so the bot
 * asks less as it goes, and the page shows it happening.
 *
 * Each visitor's take has a model of its own (`launch-demo-bot-<id>`, made at Start, deleted when the 40 are done,
 * when they start again, or after 20 idle minutes), so one visitor's rule never reaches another's bot. The expenses
 * are made here, never sent by the page: the page sends an outcome and nothing else. No language model runs: the bot
 * is its learned gate alone.
 */

export const BOT_PREFIX = 'launch-demo-bot-';

export const BOT_LIMITS = {
  /** Expenses in a take. */
  items: 40,
  /** The bot asks about the first so many whatever Ada says: she has too little to go on. */
  askFirst: 5,
  /**
   * The bot's own gate on a decision Ada is sure of: it stands only when the two closest answers are each this alike
   * and both say what Ada says. Ada's `decide` can be sure with nothing close (it does not read `min_sim`), and most
   * of the bot's wrong decisions were those: measured 2026-11-12, this took right-when-alone from 92% to 97%.
   */
  alike: 0.5,
  /** Ada weighs the roles again (learn) from this many answers on, once both outcomes are there, every so many. */
  learnFrom: 10,
  learnEvery: 5,
  /** Takes going on at once, all visitors together; an idle one ends after so long. */
  live: 30,
  idleMs: 20 * 60 * 1000,
  /** Starts per visitor (their address), and answers. */
  starts: 4,
  startsMs: 10 * 60 * 1000,
  perMinute: 60,
  perDay: 600,
};

/** Under this sure, the bot asks: the spec's `ask_below`. */
export const BOT_BAR = 0.75;

const MINUTE = 60 * 1000;
const DAY = 24 * 60 * MINUTE;
const VISITOR_COOKIE = 'glyphh_bot';

export type Outcome = 'approve' | 'reject';
const POLICIES = ['within limit', 'over limit, pre-approved', 'over limit, not pre-approved'] as const;

export type Item = {
  employee: string;
  department: string;
  category: string;
  amount: number;
  limit: number;
  receipt: boolean;
  policy: (typeof POLICIES)[number];
  description: string;
};

/** What Ada is shown of an expense: these five, and the page says so. Who filed it and its wording are for people. */
export const botSpec = (name: string) => ({
  name,
  layers: [
    {
      name: 'expense',
      segments: [
        {
          name: 'claim',
          roles: [
            { name: 'department' },
            { name: 'category' },
            { name: 'amount', numeric_config: { min_value: 0, max_value: 3000, bin_width: 100 } },
            { name: 'receipt' },
            { name: 'policy' },
          ],
        },
      ],
    },
  ],
  output: { ask_below: BOT_BAR },
});

const asData = (i: Item) => ({
  expense: { claim: { department: i.department, category: i.category, amount: i.amount, receipt: i.receipt ? 'yes' : 'no', policy: i.policy } },
});

/** Each category's limit without pre-approval, and what such an expense is usually for. */
const CATEGORIES: Record<string, { limit: number; what: string[] }> = {
  'ground transport': { limit: 350, what: ['Taxi to the airport', 'Train to a client site', 'Car hire for a site visit', 'Parking at the conference centre'] },
  airfare: { limit: 800, what: ['Economy flight to Chicago', 'Flight to the Denver office', 'Business class to London', 'Return flight for a client pitch'] },
  hotel: { limit: 300, what: ['One night near the client', 'Two nights for the offsite', 'Hotel for the trade show', 'Airport hotel after a cancelled flight'] },
  meals: { limit: 300, what: ['Team lunch', 'Dinner with a client', 'Coffee for a customer meeting', 'Working dinner before the launch'] },
  'office supplies': { limit: 250, what: ['Printer paper and toner', 'Whiteboard and markers', 'Desk lamp', 'Notebooks for the workshop'] },
  software: { limit: 200, what: ['Design tool, annual licence', 'Screen recorder', 'Extra seats on the project tracker', 'Diagramming tool'] },
  equipment: { limit: 500, what: ['Second monitor', 'Standing desk', 'Noise-cancelling headphones', 'Replacement laptop charger'] },
  'client gifts': { limit: 100, what: ['Gift basket for a renewal', 'Bottle of wine for a client', 'Flowers for a customer', 'Branded notebooks'] },
  conference: { limit: 0, what: ['Ticket to an industry conference', 'Workshop registration', 'Speaker fee for a meetup', 'Booth at a trade show'] },
};
const DEPARTMENTS = ['sales', 'engineering', 'marketing', 'customer success', 'finance'];
const PEOPLE = ['Maya Patel', 'Ethan Clarke', 'Grace Kim', 'Sofia Alvarez', 'Daniel Osei', 'Hannah Weiss', 'Omar Haddad', 'Lucy Tran', 'Ben Carter', 'Priya Nair'];

/** The take's expenses: every category and department, small, middling and large amounts, a quarter without a receipt. */
export function makeItems(random: () => number = Math.random, n = BOT_LIMITS.items): Item[] {
  const pick = <T>(xs: readonly T[]) => xs[Math.min(xs.length - 1, Math.floor(random() * xs.length))]!;
  const between = (lo: number, hi: number) => Math.round(lo + random() * (hi - lo));
  return Array.from({ length: n }, () => {
    const category = pick(Object.keys(CATEGORIES));
    const { limit, what } = CATEGORIES[category]!;
    const amount = pick([() => between(5, 150), () => between(100, 600), () => between(400, 2800)])();
    const preapproved = random() < 0.4;
    return {
      employee: pick(PEOPLE),
      department: pick(DEPARTMENTS),
      category,
      amount,
      limit,
      receipt: random() < 0.75,
      policy: amount <= limit ? 'within limit' : preapproved ? 'over limit, pre-approved' : 'over limit, not pre-approved',
      description: pick(what),
    };
  });
}

type Pending =
  | { ask: true; why: 'new' | 'unsure' | 'thin'; lean: Outcome | null; sure: number | null; basis: Basis[]; ms: number | null }
  | { ask: false; outcome: Outcome; sure: number; basis: Basis[]; ms: number };
type Basis = { n: number; sim: number; outcome: Outcome };
type Entry = { asked: boolean; wrong: boolean; outcome: Outcome };

type Session = {
  model: string;
  items: Item[];
  i: number;
  log: Entry[];
  /** Ada's id for each answer recorded → the expense it was, for "based on". */
  ids: Map<string, number>;
  seen: Set<Outcome>;
  sinceLearn: number;
  weights: Record<string, number> | null;
  pending: Pending | null;
  touched: number;
  ended: boolean;
  queue: Promise<unknown>;
};

type Deps = {
  config: DemoConfig & { botDailyCalls?: number };
  fetch?: typeof fetch;
  now?: () => number;
  random?: () => number;
  secureCookies?: boolean;
  /** Between looks at a learn job (ms); the tests look at once. */
  pollMs?: number;
};

const isOutcome = (v: unknown): v is Outcome => v === 'approve' || v === 'reject';

export function createBot({ config, fetch: fetcher = fetch, now = Date.now, random = Math.random, secureCookies = true, pollMs = 300 }: Deps) {
  const app = new Hono();
  const dailyCalls = config.botDailyCalls ?? 6000;
  const path = (model: string, rest = '') => `${config.adaUrl}/v1/models/${encodeURIComponent(model)}${rest}`;

  const sessions = new Map<string, Session>();
  let swept: Promise<void> | null = null;
  let day = Math.floor(now() / DAY);
  let calls = 0;

  const starts = new Window(BOT_LIMITS.starts, BOT_LIMITS.startsMs);
  const minute = new Window(BOT_LIMITS.perMinute, MINUTE);
  const daily = new Window(BOT_LIMITS.perDay, DAY);

  /** One call to Ada Cloud, counted against the bot demo's day. */
  async function ada<T>(method: string, url: string, body?: unknown): Promise<T> {
    const today = Math.floor(now() / DAY);
    if (today !== day) {
      day = today;
      calls = 0;
    }
    if (calls >= dailyCalls) throw new Refusal(429, 'The bot has had its fill of Ada for today. It opens again at midnight UTC.');
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

  const drop = (model: string) => ada('DELETE', `${path(model)}?confirm=${encodeURIComponent(model)}`).catch(() => undefined);

  /** A take over: its model deleted, what happened kept for the page until the visitor starts again or goes idle. */
  async function end(s: Session) {
    if (s.ended) return;
    s.ended = true;
    s.pending = null;
    await drop(s.model);
  }

  /** Idle takes ended, and, once per process, the models an earlier process left behind. */
  async function sweep() {
    for (const [visitor, s] of sessions) {
      if (now() - s.touched < BOT_LIMITS.idleMs) continue;
      sessions.delete(visitor);
      await end(s);
    }
    swept ??= (async () => {
      const { models = [] } = await ada<{ models?: { name: string }[] }>('GET', `${config.adaUrl}/v1/models`);
      const mine = new Set([...sessions.values()].map((s) => s.model));
      for (const m of models) if (m.name.startsWith(BOT_PREFIX) && !mine.has(m.name)) await drop(m.name);
    })().catch(() => {
      swept = null;
    });
    await swept;
  }

  /** Ada weighs the roles again from the answers so far; what she found is what the visitor's decisions turn on. */
  async function learn(s: Session) {
    try {
      type Job = { id?: string; state?: string; result?: { learned?: { roles?: Record<string, number> } } };
      let job = await ada<Job>('POST', path(s.model, '/learn'), {});
      for (let i = 0; job.id && job.state !== 'done' && job.state !== 'failed' && job.state !== 'cancelled' && i < 20; i++) {
        if (pollMs) await new Promise((r) => setTimeout(r, pollMs));
        job = await ada<Job>('GET', `${config.adaUrl}/v1/jobs/${encodeURIComponent(job.id)}`);
      }
      const roles = job.state === 'done' ? job.result?.learned?.roles : undefined;
      if (roles) s.weights = Object.fromEntries(Object.entries(roles).map(([k, v]) => [k.split('.').pop()!, Math.round(Number(v) * 100) / 100]));
    } catch (e) {
      // The bot goes on with the weights it has; a day's fill or a busy Ada shows at the next decide.
      if (!(e instanceof Refusal)) throw e;
    }
    s.sinceLearn = 0;
  }

  /** What the bot does with the expense in front of it: asks, or decides alone. Worked out once, kept until answered. */
  async function pend(s: Session) {
    if (s.ended || s.pending || s.i >= s.items.length) return;
    if (s.log.length < BOT_LIMITS.askFirst) {
      s.pending = { ask: true, why: 'new', lean: null, sure: null, basis: [], ms: null };
      return;
    }
    const started = performance.now();
    const d = await ada<{ outcome?: string | null; probabilities?: Record<string, number>; ask?: boolean; receipts?: { id: string; sim: number; outcome: string }[] }>(
      'POST',
      `${config.adaUrl}/v1/decide`,
      { model: s.model, data: asData(s.items[s.i]!) },
    );
    const ms = Math.round(performance.now() - started);
    const outcome = isOutcome(d.outcome) ? d.outcome : null;
    const sure = outcome ? (d.probabilities?.[outcome] ?? 0) : null;
    const basis = (d.receipts ?? [])
      .filter((r) => s.ids.has(r.id) && isOutcome(r.outcome))
      .slice(0, 3)
      .map((r) => ({ n: s.ids.get(r.id)!, sim: r.sim, outcome: r.outcome as Outcome }));
    const closest = (d.receipts ?? []).slice(0, 2);
    const stands = closest.length === 2 && closest.every((r) => r.sim >= BOT_LIMITS.alike && r.outcome === outcome);
    s.pending =
      d.ask || !outcome || sure === null
        ? { ask: true, why: 'unsure', lean: outcome, sure, basis, ms }
        : stands
          ? { ask: false, outcome, sure, basis, ms }
          : { ask: true, why: 'thin', lean: outcome, sure, basis, ms };
  }

  /** The take as the page shows it. */
  function view(s: Session) {
    const done = s.i >= s.items.length;
    const asked = s.log.filter((e) => e.asked).length;
    const wrong = s.log.filter((e) => e.wrong).length;
    return {
      total: s.items.length,
      n: s.i,
      done,
      bar: BOT_BAR,
      askFirst: BOT_LIMITS.askFirst,
      alike: BOT_LIMITS.alike,
      item: done ? null : s.items[s.i],
      bot: done || !s.pending ? null : { ...s.pending, basis: s.pending.basis.map((b) => ({ ...b, item: s.items[b.n] })) },
      log: s.log.map((e) => ({ asked: e.asked, wrong: e.wrong })),
      counts: { asked, alone: s.log.length - asked, wrong },
      weights: s.weights,
    };
  }

  /** A take's work, one at a time, so two clicks never answer the same expense twice. */
  function serial<T>(s: Session, work: () => Promise<T>): Promise<T> {
    const out = s.queue.then(work, work);
    s.queue = out.catch(() => undefined);
    return out;
  }

  const addressOf = (c: Context) =>
    c.req.header('cf-connecting-ip') ?? c.req.header('fly-client-ip') ?? c.req.header('x-forwarded-for')?.split(',')[0]?.trim() ?? 'unknown';

  const visitorOf = (c: Context) => {
    let id = getCookie(c, VISITOR_COOKIE);
    if (!id || !/^[a-f0-9-]{36}$/.test(id)) {
      id = randomUUID();
      setCookie(c, VISITOR_COOKIE, id, { httpOnly: true, secure: secureCookies, sameSite: 'Lax', path: '/', maxAge: 24 * 3600 });
    }
    return id;
  };

  const limit = (c: Context) => {
    const who = addressOf(c);
    const wait = minute.take(who, now()) || daily.take(who, now());
    if (wait) throw new Refusal(429, 'That is a lot of answers. Give it a minute.', wait);
  };

  async function readBody(c: Context): Promise<Record<string, unknown>> {
    const raw = await c.req.text();
    if (raw.length > DEMO_LIMITS.bodyBytes) throw new Refusal(413, 'That is more than an answer.');
    try {
      const body: unknown = raw ? JSON.parse(raw) : {};
      return typeof body === 'object' && body !== null ? (body as Record<string, unknown>) : {};
    } catch {
      throw new Refusal(400, 'The demo could not read that.');
    }
  }

  app.use('/api/bot/*', async (c, next) => {
    c.header('cache-control', 'no-store');
    if (!config.key) throw new Refusal(503, 'The demo is not set up yet.');
    if (c.req.method !== 'GET') {
      const site = c.req.header('sec-fetch-site');
      const same = site ? site === 'same-origin' : c.req.header('origin') === `https://${config.host}`;
      if (!same) throw new Refusal(403, 'Writes come from the demo page only.');
    }
    await next();
  });

  /** The visitor's take, if they have one: a page loaded again goes on where it was. */
  app.get('/api/bot/state', async (c) => {
    const s = sessions.get(visitorOf(c));
    if (!s) return c.json({ take: null });
    limit(c);
    s.touched = now();
    return c.json({ take: await serial(s, async () => (await pend(s), view(s))) });
  });

  /** A new take: a new bot that knows nothing, a model of its own, 40 expenses. An earlier take of theirs ends. */
  app.post('/api/bot/start', async (c) => {
    const visitor = visitorOf(c);
    const wait = starts.take(addressOf(c), now());
    if (wait) throw new Refusal(429, 'You have started a few bots just now. Give it a few minutes.', wait);
    await sweep();
    const old = sessions.get(visitor);
    if (old) {
      sessions.delete(visitor);
      await end(old);
    }
    if (sessions.size >= BOT_LIMITS.live) throw new Refusal(503, 'Every bot is being taught right now. Try again in a few minutes.', 120);
    const model = `${BOT_PREFIX}${randomUUID().replace(/-/g, '').slice(0, 12)}`;
    const s: Session = {
      model,
      items: makeItems(random),
      i: 0,
      log: [],
      ids: new Map(),
      seen: new Set(),
      sinceLearn: 0,
      weights: null,
      pending: null,
      touched: now(),
      ended: false,
      queue: Promise.resolve(),
    };
    // Held before Ada is asked, so takes starting together cannot pass the cap.
    sessions.set(visitor, s);
    try {
      await ada('POST', `${config.adaUrl}/v1/models`, { name: model, spec: botSpec(model) });
    } catch (e) {
      sessions.delete(visitor);
      throw e;
    }
    await pend(s);
    return c.json({ take: view(s) });
  });

  /**
   * The visitor's word on the expense in front of them, `{n, outcome}`: their answer where the bot asked, the right
   * decision where it decided alone (the same as the bot's, or not). Recorded, and the next expense comes back. An
   * answer for an expense already answered changes nothing and gets the take as it is.
   */
  app.post('/api/bot/answer', async (c) => {
    const body = await readBody(c);
    if (!isOutcome(body.outcome)) throw new Refusal(400, 'Approve or reject.');
    const outcome = body.outcome;
    const s = sessions.get(visitorOf(c));
    if (!s) throw new Refusal(400, 'There is no bot being taught here. Start one.');
    limit(c);
    s.touched = now();
    const take = await serial(s, async () => {
      if (!s.ended && body.n === s.i && s.i < s.items.length) {
        await pend(s);
        const p = s.pending!;
        const got = await ada<{ ids?: string[] }>('POST', path(s.model, '/record_many'), { cases: [{ data: asData(s.items[s.i]!), outcome }] });
        if (got.ids?.[0]) s.ids.set(got.ids[0], s.i);
        s.log.push({ asked: p.ask, wrong: !p.ask && p.outcome !== outcome, outcome });
        s.seen.add(outcome);
        s.sinceLearn += 1;
        s.i += 1;
        s.pending = null;
        if (s.log.length >= BOT_LIMITS.learnFrom && s.seen.size === 2 && s.sinceLearn >= BOT_LIMITS.learnEvery) await learn(s);
        if (s.i >= s.items.length) await end(s);
      }
      await pend(s);
      return view(s);
    });
    return c.json({ take });
  });

  app.all('/api/bot/*', () => {
    throw new Refusal(403, 'The bot demo answers state, start and answer only.');
  });

  app.onError((e, c) => {
    if (e instanceof Refusal) {
      if (e.retryAfter) c.header('retry-after', String(e.retryAfter));
      c.header('cache-control', 'no-store');
      return c.json({ error: e.message }, e.status);
    }
    console.error('bot demo:', e);
    return c.json({ error: 'The demo hit a snag. Try again.' }, 502);
  });

  return app;
}

/** Requests the bot demo answers on the demo's host: its API, and /bot sent on to the page (served with the others'). */
export const isBotPath = (path: string) => path === '/bot' || path.startsWith('/api/bot/');

export function serveBotRedirect(app: Hono) {
  app.get('/bot', (c) => c.redirect('/bot/', 308));
  app.notFound((c) => c.text('Not found', 404));
  return app;
}
