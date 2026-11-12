import { Hono } from 'hono';
import { BOT_BAR, BOT_LIMITS, BOT_PREFIX, botSpec, createBot, isBotPath, makeItems, serveBotRedirect } from './bot.js';
import { createDemo, serveDemoPage, type DemoConfig } from './demo.js';

const body = async (res: Response): Promise<any> => res.json();
const config: DemoConfig = { host: 'demo.test', key: 'glyphh_ak_demo', adaUrl: 'https://ada.test', dailyCalls: 1000 };

type Seen = { method: string; path: string; body: any };

/**
 * A fake Ada Cloud: models by name, each with its cases; decide answers what `decide` says (sure of approve by
 * default); learn is a job, done when read, that found the receipt is what counts.
 */
function fakeAda({ left = [] as string[], decide = (): object => ({ outcome: 'approve', probabilities: { approve: 0.9, reject: 0.1 }, ask: false, receipts: [{ id: 'p1', sim: 0.8, outcome: 'approve' }] }) } = {}) {
  const seen: Seen[] = [];
  const models = new Map<string, { data: any; outcome: string }[]>(left.map((name) => [name, []]));
  let id = 0;
  const ada = new Hono();
  ada.use('*', async (c, next) => {
    const raw = await c.req.raw.clone().text();
    seen.push({ method: c.req.method, path: new URL(c.req.url).pathname, body: raw ? JSON.parse(raw) : null });
    await next();
  });
  ada.get('/v1/models', (c) => c.json({ models: [...models.keys()].map((name) => ({ name })) }));
  ada.post('/v1/models', async (c) => {
    const { name } = await c.req.json();
    models.set(name, []);
    return c.json({ name, version: 1 }, 201);
  });
  ada.delete('/v1/models/:name', (c) => (models.delete(c.req.param('name')) ? c.json({ deleted: true }) : c.json({}, 404)));
  ada.post('/v1/models/:name/record_many', async (c) => {
    const { cases } = await c.req.json();
    const store = models.get(c.req.param('name'));
    if (!store) return c.json({ error: { code: 'E_MODEL_MISSING' } }, 404);
    store.push(...cases);
    return c.json({ ids: cases.map(() => `p${++id}`), precedents: store.length });
  });
  ada.post('/v1/models/:name/learn', (c) => c.json({ id: 'job1', state: 'queued', result: null }));
  ada.get('/v1/jobs/:id', (c) =>
    c.json({ id: c.req.param('id'), state: 'done', result: { learned: { roles: { 'expense.claim.receipt': 1, 'expense.claim.amount': 0.2512, 'expense.claim.department': 0 } } } }),
  );
  ada.post('/v1/decide', () => Response.json(decide()));
  return { seen, models, fetch: (input: RequestInfo | URL, init?: RequestInit) => ada.fetch(new Request(input, init)) };
}

const cookieOf = (res: Response) => res.headers.get('set-cookie')?.match(/glyphh_bot=([^;]+)/)?.[1] ?? '';

function setup(cfg: DemoConfig & { botDailyCalls?: number } = config, opts: Parameters<typeof fakeAda>[0] = {}) {
  const ada = fakeAda(opts);
  const clock = { now: Date.UTC(2026, 10, 12, 12) };
  const app = createBot({ config: cfg, fetch: ada.fetch as typeof fetch, now: () => clock.now, pollMs: 0 });
  const post = (path: string, json: unknown, { cookie = '', ip = '1.2.3.4', site = 'same-origin' } = {}) =>
    app.request(`https://demo.test${path}`, {
      method: 'POST',
      headers: { 'content-type': 'application/json', host: 'demo.test', 'fly-client-ip': ip, 'sec-fetch-site': site, ...(cookie ? { cookie: `glyphh_bot=${cookie}` } : {}) },
      body: JSON.stringify(json),
    });
  const get = (path: string, cookie = '') =>
    app.request(`https://demo.test${path}`, { headers: { host: 'demo.test', 'fly-client-ip': '1.2.3.4', ...(cookie ? { cookie: `glyphh_bot=${cookie}` } : {}) } });
  /** A take started; `answer` gives the visitor's word on the expense in front of them. */
  const start = async (ip = '1.2.3.4') => {
    const res = await post('/api/bot/start', {}, { ip });
    const cookie = cookieOf(res);
    let take = (await body(res)).take;
    const answer = async (outcome: string, n = take.n) => {
      const got = await post('/api/bot/answer', { n, outcome }, { cookie, ip });
      const json = await body(got);
      if (json.take) take = json.take;
      return { status: got.status, ...json };
    };
    return { res, cookie, answer, take: () => take };
  };
  return { ada, clock, post, get, start };
}

describe('the expenses', () => {
  it('are 40, each with a category the demo knows, its limit, and the policy check worked out from them', () => {
    const items = makeItems();
    expect(items).toHaveLength(BOT_LIMITS.items);
    for (const i of items) {
      expect(i.amount).toBeGreaterThan(0);
      expect(i.amount).toBeLessThanOrEqual(3000);
      expect(i.policy === 'within limit').toBe(i.amount <= i.limit);
      expect(i.description).not.toBe('');
    }
  });

  it('are the same for the same dice', () => {
    const dice = () => {
      let x = 7;
      return () => ((x = (x * 48271) % 2147483647) / 2147483647);
    };
    expect(makeItems(dice())).toEqual(makeItems(dice()));
  });
});

describe('the spec', () => {
  it('shows Ada five things, the amount by its range, and asks under the bar', () => {
    const spec = botSpec('launch-demo-bot-x');
    expect(spec.layers[0]!.segments[0]!.roles.map((r) => r.name)).toEqual(['department', 'category', 'amount', 'receipt', 'policy']);
    expect(spec.output).toEqual({ ask_below: BOT_BAR });
  });
});

describe('the bot API', () => {
  it('starts a take: a model of its own on the spec, 40 expenses, the bot asking about the first', async () => {
    const { ada, start } = setup();
    const t = await start();
    expect(t.res.status).toBe(200);
    expect(t.cookie).toMatch(/^[a-f0-9-]{36}$/);
    const made = ada.seen.find((s) => s.method === 'POST' && s.path === '/v1/models')!;
    expect(made.body.name).toMatch(new RegExp(`^${BOT_PREFIX}[a-f0-9]{12}$`));
    expect(made.body.spec).toEqual(botSpec(made.body.name));
    const take = t.take();
    expect(take).toMatchObject({ total: 40, n: 0, done: false, bar: BOT_BAR, log: [], counts: { asked: 0, alone: 0, wrong: 0 }, weights: null });
    expect(take.bot).toMatchObject({ ask: true, why: 'new', lean: null });
    expect(take.item.description).toBeTruthy();
    expect(ada.seen.some((s) => s.path === '/v1/decide')).toBe(false);
  });

  it('records each answer as the expense Ada is shown and nothing else, and asks about the first five whatever Ada thinks', async () => {
    const { ada, start } = setup();
    const t = await start();
    const first = t.take().item;
    for (let i = 0; i < BOT_LIMITS.askFirst; i++) {
      expect(t.take().bot.ask).toBe(true);
      await t.answer(i % 2 ? 'reject' : 'approve');
    }
    const recs = ada.seen.filter((s) => s.path.endsWith('/record_many'));
    expect(recs).toHaveLength(BOT_LIMITS.askFirst);
    expect(recs[0]!.body.cases).toEqual([
      { data: { expense: { claim: { department: first.department, category: first.category, amount: first.amount, receipt: first.receipt ? 'yes' : 'no', policy: first.policy } } }, outcome: 'approve' },
    ]);
    expect(JSON.stringify(recs[0]!.body)).not.toContain(first.employee);
    // The sixth is Ada's to call: she is sure, so the bot decides alone and names the answer it stands on.
    expect(ada.seen.filter((s) => s.path === '/v1/decide')).toHaveLength(1);
    expect(t.take().bot).toMatchObject({ ask: false, outcome: 'approve', sure: 0.9 });
    expect(t.take().bot.basis).toEqual([{ n: 0, sim: 0.8, outcome: 'approve', item: first }]);
    expect(t.take().counts).toEqual({ asked: 5, alone: 0, wrong: 0 });
  });

  it('counts a decision made alone as right or wrong by the visitor’s word, and records their word', async () => {
    const { ada, start } = setup();
    const t = await start();
    for (let i = 0; i < 5; i++) await t.answer('approve');
    await t.answer('approve'); // right
    await t.answer('reject'); // wrong: the bot approved
    expect(t.take().log.slice(5)).toEqual([{ asked: false, wrong: false }, { asked: false, wrong: true }]);
    expect(t.take().counts).toEqual({ asked: 5, alone: 2, wrong: 1 });
    expect(ada.seen.filter((s) => s.path.endsWith('/record_many')).at(-1)!.body.cases[0].outcome).toBe('reject');
  });

  it('asks where Ada is under the bar, saying which way she leans', async () => {
    const { start } = setup(config, { decide: () => ({ outcome: 'reject', probabilities: { approve: 0.4, reject: 0.6 }, ask: true, receipts: [] }) });
    const t = await start();
    for (let i = 0; i < 5; i++) await t.answer('approve');
    expect(t.take().bot).toMatchObject({ ask: true, why: 'unsure', lean: 'reject', sure: 0.6 });
    await t.answer('approve');
    expect(t.take().log.at(-1)).toEqual({ asked: true, wrong: false });
  });

  it('has Ada learn from the tenth answer on, every five, once both outcomes are there, and shows what she found', async () => {
    const { ada, start } = setup();
    const t = await start();
    for (let i = 0; i < 9; i++) await t.answer('approve');
    await t.answer('approve');
    // Ten answers, all approve: nothing to tell apart yet.
    expect(ada.seen.some((s) => s.path.endsWith('/learn'))).toBe(false);
    expect(t.take().weights).toBeNull();
    await t.answer('reject');
    expect(ada.seen.filter((s) => s.path.endsWith('/learn'))).toHaveLength(1);
    expect(t.take().weights).toEqual({ receipt: 1, amount: 0.25, department: 0 });
    for (let i = 0; i < 4; i++) await t.answer('approve');
    expect(ada.seen.filter((s) => s.path.endsWith('/learn'))).toHaveLength(1);
    await t.answer('approve');
    expect(ada.seen.filter((s) => s.path.endsWith('/learn'))).toHaveLength(2);
  });

  it('ends after the 40: the model deleted, the take still there to read, no more answers taken', async () => {
    const { ada, start, get } = setup();
    const t = await start();
    for (let i = 0; i < 40; i++) await t.answer('approve');
    const take = t.take();
    expect(take).toMatchObject({ done: true, n: 40, item: null, bot: null });
    expect(take.log).toHaveLength(40);
    expect(take.counts).toEqual({ asked: 5, alone: 35, wrong: 0 });
    expect(ada.models.size).toBe(0);
    const calls = ada.seen.length;
    expect((await t.answer('approve', 40)).take.done).toBe(true);
    expect((await body(await get('/api/bot/state', t.cookie))).take.done).toBe(true);
    expect(ada.seen.length).toBe(calls);
  });

  it('takes an answer once: the same expense answered again changes nothing', async () => {
    const { ada, start } = setup();
    const t = await start();
    await t.answer('approve', 0);
    const again = await t.answer('reject', 0);
    expect(again.take.n).toBe(1);
    expect(again.take.log).toHaveLength(1);
    expect(ada.seen.filter((s) => s.path.endsWith('/record_many'))).toHaveLength(1);
  });

  it('gives the take back to a page loaded again, and nothing to a visitor without one', async () => {
    const { start, get } = setup();
    expect((await body(await get('/api/bot/state'))).take).toBeNull();
    const t = await start();
    await t.answer('approve');
    const again = (await body(await get('/api/bot/state', t.cookie))).take;
    expect(again.n).toBe(1);
    expect(again.item).toEqual(t.take().item);
  });

  it('keeps each visitor’s answers in their own model', async () => {
    const { ada, start } = setup();
    const a = await start('1.1.1.1');
    const b = await start('2.2.2.2');
    await a.answer('approve');
    await b.answer('reject');
    expect(ada.models.size).toBe(2);
    expect([...ada.models.values()].map((cases) => cases.map((k) => k.outcome))).toEqual([['approve'], ['reject']]);
  });

  it('starting again ends the visitor’s earlier take and deletes its model', async () => {
    const { ada, post, start } = setup();
    const t = await start();
    const [first] = [...ada.models.keys()];
    const res = await post('/api/bot/start', {}, { cookie: t.cookie });
    expect((await body(res)).take.n).toBe(0);
    expect([...ada.models.keys()]).not.toContain(first);
    expect(ada.models.size).toBe(1);
  });

  it('deletes the models an earlier process left, and a take idle for 20 minutes', async () => {
    const { ada, clock, start, get } = setup(config, { left: [`${BOT_PREFIX}0123456789ab`, 'launch-demo-expenses'] });
    const t = await start('1.1.1.1');
    expect([...ada.models.keys()]).toEqual(['launch-demo-expenses', expect.stringMatching(BOT_PREFIX)]);
    clock.now += BOT_LIMITS.idleMs;
    await start('2.2.2.2');
    expect(ada.models.size).toBe(2);
    expect((await body(await get('/api/bot/state', t.cookie))).take).toBeNull();
  });

  it(`teaches ${BOT_LIMITS.live} bots at once and no more`, async () => {
    const { start, post } = setup();
    for (let i = 0; i < BOT_LIMITS.live; i++) expect((await start(`9.9.9.${i}`)).res.status).toBe(200);
    const res = await post('/api/bot/start', {}, { ip: '8.8.8.8' });
    expect(res.status).toBe(503);
    expect(res.headers.get('retry-after')).toBe('120');
  });

  it(`lets a visitor start ${BOT_LIMITS.starts} bots in ten minutes`, async () => {
    const { post } = setup();
    for (let i = 0; i < BOT_LIMITS.starts; i++) expect((await post('/api/bot/start', {})).status).toBe(200);
    expect((await post('/api/bot/start', {})).status).toBe(429);
  });

  it('stops at the demo’s Ada calls a day', async () => {
    const { start } = setup({ ...config, botDailyCalls: 4 });
    const t = await start(); // the sweep's list, the model
    expect((await t.answer('approve')).status).toBe(200);
    expect((await t.answer('approve')).status).toBe(200);
    const res = await t.answer('approve');
    expect(res.status).toBe(429);
    expect(res.error).toContain('midnight UTC');
  });

  it('goes on from where it was when Ada fails after an answer was recorded', async () => {
    let fail = false;
    const { ada, start, get } = setup(config, {
      decide: () => {
        if (fail) throw new Error('down');
        return { outcome: 'approve', probabilities: { approve: 0.9 }, ask: false, receipts: [] };
      },
    });
    const t = await start();
    for (let i = 0; i < 4; i++) await t.answer('approve');
    fail = true;
    expect((await t.answer('approve')).status).toBe(502);
    fail = false;
    const take = (await body(await get('/api/bot/state', t.cookie))).take;
    expect(take.n).toBe(5);
    expect(take.bot.ask).toBe(false);
    expect(ada.seen.filter((s) => s.path.endsWith('/record_many'))).toHaveLength(5);
  });

  it('takes approve or reject, from a visitor with a take', async () => {
    const { post, start } = setup();
    expect((await post('/api/bot/answer', { n: 0, outcome: 'approve' })).status).toBe(400);
    const t = await start();
    expect((await t.answer('maybe')).status).toBe(400);
    expect((await t.answer('approve')).status).toBe(200);
  });

  it('refuses writes from other sites, unknown paths, and everything without a key', async () => {
    expect((await setup().post('/api/bot/start', {}, { site: 'cross-site' })).status).toBe(403);
    expect((await setup().post('/api/bot/models', {})).status).toBe(403);
    const off = setup({ ...config, key: undefined });
    expect((await off.post('/api/bot/start', {})).status).toBe(503);
    expect(off.ada.seen).toEqual([]);
  });
});

describe('the page', () => {
  const page = () => serveDemoPage(createDemo({ config: { ...config, key: undefined }, history: [] }));

  it.each([
    ['/bot/', 'text/html'],
    ['/bot/bot.js', 'text/javascript'],
    ['/bot/bot.css', 'text/css'],
  ])('serves %s', async (path, type) => {
    const res = await page().request(`https://demo.test${path}`);
    expect(res.status).toBe(200);
    expect(res.headers.get('content-type')).toContain(type);
  });

  it('says what the bot sees and what the page is', async () => {
    const html = await (await page().request('https://demo.test/bot/')).text();
    expect(html).toContain('The bot never sees your rule, only your answers.');
    expect(html).toContain('No language model runs on this page');
  });

  it('wears the platform’s look: its stylesheet last, the wordmark', async () => {
    const html = await (await page().request('https://demo.test/bot/')).text();
    const sheets = [...html.matchAll(/rel="stylesheet" href="([^"]+)"/g)].map((m) => m[1]);
    expect(sheets.at(-1)).toBe('/platform.css');
    expect(html).toContain('/glyphh-logo-text-white.png');
  });

  it('holds no key and sends nothing but an outcome', async () => {
    const js = await (await page().request('https://demo.test/bot/bot.js')).text();
    expect(js).not.toMatch(/glyphh_ak_|authorization/i);
    expect(js).toContain("api('answer', { n: take.n, outcome })");
  });

  it('sends /bot on to /bot/', async () => {
    const res = await serveBotRedirect(createBot({ config })).request('https://demo.test/bot');
    expect(res.status).toBe(308);
    expect(res.headers.get('location')).toBe('/bot/');
  });

  it('takes /bot and /api/bot only, the page left to the demos’', () => {
    expect(['/bot', '/api/bot/start', '/api/bot/answer'].every(isBotPath)).toBe(true);
    expect(['/', '/bot/', '/bot/bot.js', '/api/decide', '/bots', '/api/voice/read'].some(isBotPath)).toBe(false);
  });
});
