import { readFileSync } from 'node:fs';
import { Hono } from 'hono';
import { createDemo, hostOf, LIMITS, MODEL, readClaim, readDemoConfig, Refusal, serveDemoPage, Window, type DemoConfig, type HistoryRow } from './demo.js';

const body = async (res: Response): Promise<any> => res.json();
const history = JSON.parse(readFileSync('demo/history.json', 'utf8')) as HistoryRow[];

const config: DemoConfig = { host: 'demo.test', key: 'glyphh_ak_demo', adaUrl: 'https://ada.test', dailyCalls: 1000 };

type Seen = { method: string; path: string; search: string; auth: string | null; body: any };

/** A fake Ada Cloud: models, record_many, decide; recording every call. */
function fakeAda({ precedents = null as number | null, failDecide = 0 } = {}) {
  const seen: Seen[] = [];
  const models = new Map<string, number>();
  if (precedents !== null) models.set(MODEL, precedents);
  let id = 0;
  const ada = new Hono();
  ada.use('*', async (c, next) => {
    const url = new URL(c.req.url);
    const raw = await c.req.raw.clone().text();
    seen.push({ method: c.req.method, path: url.pathname, search: url.search, auth: c.req.header('authorization') ?? null, body: raw ? JSON.parse(raw) : null });
    await next();
  });
  ada.get('/v1/models', (c) => c.json({ models: [...models].map(([name, n]) => ({ name, precedents: n })) }));
  ada.post('/v1/models', async (c) => {
    const { name } = await c.req.json();
    models.set(name, 0);
    return c.json({ name, version: 1 }, 201);
  });
  ada.delete('/v1/models/:name', (c) => {
    const had = models.delete(c.req.param('name'));
    return had ? c.json({ deleted: true }) : c.json({ error: { code: 'E_NOT_FOUND' } }, 404);
  });
  ada.post('/v1/models/:name/record_many', async (c) => {
    const { cases } = await c.req.json();
    const name = c.req.param('name');
    const refs = new Set<string>();
    const ids = cases.map((k: any) => {
      refs.add(k.data.expense.claim.ref);
      return `p${++id}`;
    });
    // Recording the history again replaces it: only new refs add.
    const was = models.get(name) ?? 0;
    models.set(name, cases.length === history.length ? history.length : was + cases.length);
    return c.json({ ids, added: cases.length, replaced: 0, precedents: models.get(name) });
  });
  ada.post('/v1/decide', (c) => {
    if (failDecide) return c.json({ error: { code: 'E_RATE' } }, 429, { 'retry-after': '3' });
    return c.json({ outcome: 'approve', probabilities: { approve: 0.98, reject: 0.02 }, ask: false, receipts: [{ id: 'p1', sim: 0.9, outcome: 'approve', extra: 'x' }], model: MODEL });
  });
  return { seen, models, fetch: (input: RequestInfo | URL, init?: RequestInit) => ada.fetch(new Request(input, init)) };
}

function setup(opts: Parameters<typeof fakeAda>[0] = {}, demoConfig: DemoConfig = config) {
  const ada = fakeAda(opts);
  let clock = Date.UTC(2026, 9, 28, 12);
  const app = createDemo({ config: demoConfig, history, fetch: ada.fetch as typeof fetch, now: () => clock });
  const request = (path: string, init: RequestInit & { ip?: string } = {}) => {
    const headers = new Headers(init.headers);
    headers.set('host', 'demo.test');
    headers.set('fly-client-ip', init.ip ?? '1.2.3.4');
    if (init.method && init.method !== 'GET' && !headers.has('sec-fetch-site')) headers.set('sec-fetch-site', 'same-origin');
    return app.request(`https://demo.test${path}`, { ...init, headers });
  };
  const post = (path: string, json: unknown, init: RequestInit & { ip?: string } = {}) =>
    request(path, { ...init, method: 'POST', headers: { 'content-type': 'application/json', ...(init.headers as object) }, body: JSON.stringify(json) });
  return { ada, request, post, advance: (ms: number) => (clock += ms) };
}

const claim = {
  employee: 'Ethan Clarke',
  department: 'sales',
  category: 'ground transport',
  amount: 62,
  receipt: true,
  preapproved: false,
  limit: 350,
  policy: 'within limit',
  description: 'Uber to JFK from the Manhattan office',
};

describe('readDemoConfig', () => {
  it('defaults to demo.glyphh.ai, no key, 150 calls a day', () => {
    expect(readDemoConfig({})).toEqual({ host: 'demo.glyphh.ai', key: undefined, adaUrl: 'https://ada.glyphh.ai', dailyCalls: 150 });
  });
  it('reads its settings', () => {
    expect(readDemoConfig({ DEMO_HOST: 'Demo.Test', DEMO_GLYPHH_API_KEY: ' k ', GLYPHH_ADA_URL: 'https://a.test/', DEMO_DAILY_CALLS: '20' })).toEqual({
      host: 'demo.test',
      key: 'k',
      adaUrl: 'https://a.test',
      dailyCalls: 20,
    });
  });
});

describe('hostOf', () => {
  it('is the host header, without its port, lower case', () => {
    expect(hostOf(new Request('http://x/', { headers: { host: 'Demo.Glyphh.ai:443' } }))).toBe('demo.glyphh.ai');
  });
});

describe('readClaim', () => {
  it('keeps what the model takes and drops the rest', () => {
    expect(readClaim({ ...claim, department: ' Sales ' })).toEqual({
      employee: 'Ethan Clarke',
      department: 'sales',
      category: 'ground transport',
      amount: 62,
      receipt: true,
      policy: 'within limit',
      description: 'Uber to JFK from the Manhattan office',
    });
  });
  it.each([
    ['no claim', null],
    ['an amount as text', { ...claim, amount: '62' }],
    ['an amount over $3,000', { ...claim, amount: 3001 }],
    ['a negative amount', { ...claim, amount: -1 }],
    ['no receipt answer', { ...claim, receipt: 'yes' }],
    ['an unknown policy', { ...claim, policy: 'whatever' }],
    ['markup in a department', { ...claim, department: '<b>sales</b>' }],
    ['markup in a description', { ...claim, description: '<script>alert(1)</script>' }],
    ['a long description', { ...claim, description: 'a'.repeat(121) }],
    ['no description', { ...claim, description: ' ' }],
  ])('refuses %s', (_name, value) => expect(() => readClaim(value)).toThrow(Refusal));
});

describe('Window', () => {
  it('allows max calls a window, then says how long to wait', () => {
    const w = new Window(2, 60_000);
    expect(w.take('a', 0)).toBe(0);
    expect(w.take('a', 1000)).toBe(0);
    expect(w.take('a', 2000)).toBe(58);
    expect(w.take('b', 2000)).toBe(0);
    expect(w.take('a', 60_001)).toBe(0);
  });
  it('forgets the oldest keys past its size', () => {
    const w = new Window(1, 60_000, 2);
    w.take('a', 0);
    w.take('b', 0);
    w.take('c', 0);
    expect(w.take('a', 1)).toBe(0);
  });
});

describe('GET /api/state', () => {
  it('makes the model and records the 40 when it is missing, with the demo key, and sets a visitor cookie', async () => {
    const ctx = setup();
    const res = await ctx.request('/api/state');
    const out = await body(res);
    expect(out.model).toBe(MODEL);
    expect(out.ledger).toHaveLength(40);
    expect(out.ledger[0]).toMatchObject({ ref: 'E-2041', id: 'p1' });
    expect(res.headers.get('set-cookie')).toMatch(/glyphh_demo=.*HttpOnly/);
    expect(res.headers.get('cache-control')).toBe('no-store');
    expect(ctx.ada.seen.map((s) => `${s.method} ${s.path}`)).toEqual([
      'GET /v1/models',
      `DELETE /v1/models/${MODEL}`,
      'POST /v1/models',
      `POST /v1/models/${MODEL}/record_many`,
    ]);
    expect(ctx.ada.seen.every((s) => s.auth === 'Bearer glyphh_ak_demo')).toBe(true);
  });

  it('records the history again when the model already holds exactly 40, once per process', async () => {
    const ctx = setup({ precedents: 40 });
    await ctx.request('/api/state');
    await ctx.request('/api/state');
    expect(ctx.ada.seen.map((s) => `${s.method} ${s.path}`)).toEqual(['GET /v1/models', `POST /v1/models/${MODEL}/record_many`]);
  });

  it('makes it again when it holds more than the 40', async () => {
    const ctx = setup({ precedents: 55 });
    await ctx.request('/api/state');
    expect(ctx.ada.seen.map((s) => s.method)).toEqual(['GET', 'DELETE', 'POST', 'POST']);
  });

  it('never sends the key to the browser', async () => {
    const ctx = setup();
    const res = await ctx.request('/api/state');
    expect(JSON.stringify(await body(res)) + JSON.stringify([...res.headers])).not.toContain('glyphh_ak_demo');
  });

  it('is 503 when the demo has no key, and calls nothing', async () => {
    const ctx = setup({}, { ...config, key: undefined });
    const res = await ctx.request('/api/state');
    expect(res.status).toBe(503);
    expect(ctx.ada.seen).toHaveLength(0);
  });
});

describe('POST /api/decide', () => {
  it('asks launch-demo-expenses with the claim as the model takes it, and answers only the decision', async () => {
    const ctx = setup({ precedents: 40 });
    const res = await ctx.post('/api/decide', { claim });
    const out = await body(res);
    expect(res.status).toBe(200);
    expect(out).toMatchObject({ outcome: 'approve', ask: false, probabilities: { approve: 0.98, reject: 0.02 }, receipts: [{ id: 'p1', sim: 0.9, outcome: 'approve' }] });
    expect(out.receipts[0].extra).toBeUndefined();
    const decide = ctx.ada.seen.find((s) => s.path === '/v1/decide')!;
    expect(decide.body).toEqual({
      model: MODEL,
      data: { expense: { claim: { department: 'sales', category: 'ground transport', amount: 62, receipt: 'yes', policy: 'within limit', description: 'Uber to JFK from the Manhattan office' } } },
    });
  });

  it('ignores a model named by the page', async () => {
    const ctx = setup({ precedents: 40 });
    await ctx.post('/api/decide', { claim, model: 'bots-edge' });
    expect(ctx.ada.seen.find((s) => s.path === '/v1/decide')!.body.model).toBe(MODEL);
    expect(ctx.ada.seen.some((s) => JSON.stringify(s).includes('bots-edge'))).toBe(false);
  });

  it('refuses a bad claim without calling Ada', async () => {
    const ctx = setup({ precedents: 40 });
    const res = await ctx.post('/api/decide', { claim: { ...claim, amount: 99999 } });
    expect(res.status).toBe(400);
    expect((await body(res)).error).toMatch(/amount/);
    expect(ctx.ada.seen).toHaveLength(0);
  });

  it('refuses a write from another site', async () => {
    const ctx = setup({ precedents: 40 });
    const res = await ctx.post('/api/decide', { claim }, { headers: { 'sec-fetch-site': 'cross-site' } });
    expect(res.status).toBe(403);
  });

  it('refuses a body bigger than an expense', async () => {
    const ctx = setup({ precedents: 40 });
    const res = await ctx.post('/api/decide', { claim, pad: 'x'.repeat(LIMITS.bodyBytes) });
    expect(res.status).toBe(413);
  });

  it('holds a visitor to their calls a minute, with Retry-After, and others go on', async () => {
    const ctx = setup({ precedents: 40 });
    for (let i = 0; i < LIMITS.perMinute; i++) expect((await ctx.post('/api/decide', { claim })).status).toBe(200);
    const res = await ctx.post('/api/decide', { claim });
    expect(res.status).toBe(429);
    expect(Number(res.headers.get('retry-after'))).toBeGreaterThan(0);
    expect((await ctx.post('/api/decide', { claim }, { ip: '5.6.7.8' })).status).toBe(200);
    ctx.advance(60_000);
    expect((await ctx.post('/api/decide', { claim })).status).toBe(200);
  });

  it('holds a visitor to their calls a day', async () => {
    const ctx = setup({ precedents: 40 });
    for (let i = 0; i < LIMITS.perDay; i++) {
      if (i % LIMITS.perMinute === 0) ctx.advance(60_000);
      expect((await ctx.post('/api/decide', { claim })).status).toBe(200);
    }
    ctx.advance(60_000);
    expect((await ctx.post('/api/decide', { claim })).status).toBe(429);
  });

  it('stops at the demo’s Ada calls a day, then opens again the next day', async () => {
    const ctx = setup({ precedents: 40 }, { ...config, dailyCalls: 4 });
    for (let i = 0; i < 2; i++) expect((await ctx.post('/api/decide', { claim }, { ip: `9.0.0.${i}` })).status).toBe(200);
    const res = await ctx.post('/api/decide', { claim }, { ip: '9.0.0.9' });
    expect(res.status).toBe(429);
    expect((await body(res)).error).toMatch(/today/);
    const calls = ctx.ada.seen.length;
    expect(calls).toBe(4);
    ctx.advance(24 * 3600 * 1000);
    expect((await ctx.post('/api/decide', { claim }, { ip: '9.0.0.10' })).status).toBe(200);
  });

  it('passes Ada Cloud’s rate refusal on as 429', async () => {
    const ctx = setup({ precedents: 40, failDecide: 1 });
    const res = await ctx.post('/api/decide', { claim });
    expect(res.status).toBe(429);
    expect(res.headers.get('retry-after')).toBe('3');
  });
});

describe('POST /api/record', () => {
  it('records the claim with the next ref into launch-demo-expenses, and adds it to the ledger', async () => {
    const ctx = setup({ precedents: 40 });
    const res = await ctx.post('/api/record', { claim: { ...claim, receipt: false }, outcome: 'reject' });
    const row = await body(res);
    expect(row).toMatchObject({ ref: 'E-2081', outcome: 'reject', added: true, receipt: false, date: '2026-10-28' });
    expect(row.by).toBeUndefined();
    const rec = ctx.ada.seen.filter((s) => s.path === `/v1/models/${MODEL}/record_many`).at(-1)!;
    expect(rec.body.cases).toEqual([{ data: { expense: { claim: expect.objectContaining({ ref: 'E-2081', receipt: 'no' }) } }, outcome: 'reject' }]);
    const state = await body(await ctx.request('/api/state', { headers: { cookie: res.headers.get('set-cookie')!.split(';')[0]! } }));
    expect(state.ledger).toHaveLength(41);
    expect(state.ledger.at(-1).employee).toBe('Ethan Clarke');
  });

  it('shows another visitor’s expense without their name', async () => {
    const ctx = setup({ precedents: 40 });
    await ctx.post('/api/record', { claim, outcome: 'approve' });
    const state = await body(await ctx.request('/api/state', { ip: '5.6.7.8' }));
    expect(state.ledger.at(-1)).toMatchObject({ ref: 'E-2081', employee: 'Another visitor', description: claim.description });
  });

  it('refuses an outcome that is not approve or reject', async () => {
    const ctx = setup({ precedents: 40 });
    expect((await ctx.post('/api/record', { claim, outcome: 'delete' })).status).toBe(400);
  });

  it('goes back to the 40 once a take has added its fill', async () => {
    const ctx = setup({ precedents: 40 });
    for (let i = 0; i < LIMITS.added; i++) {
      if (i % LIMITS.perMinute === 0) ctx.advance(60_000);
      expect((await ctx.post('/api/record', { claim, outcome: 'approve' })).status).toBe(200);
    }
    expect(ctx.ada.models.get(MODEL)).toBe(40 + LIMITS.added);
    ctx.advance(60_000);
    const row = await body(await ctx.post('/api/record', { claim, outcome: 'approve' }));
    expect(row.ref).toBe('E-2081');
    expect(ctx.ada.models.get(MODEL)).toBe(41);
  });

  it('goes back to the 40 an hour after something was recorded', async () => {
    const ctx = setup({ precedents: 40 });
    await ctx.post('/api/record', { claim, outcome: 'approve' });
    ctx.advance(LIMITS.resetAfterMs);
    const state = await body(await ctx.request('/api/state'));
    expect(state.ledger).toHaveLength(40);
    expect(ctx.ada.models.get(MODEL)).toBe(40);
  });
});

describe('POST /api/reset', () => {
  it('makes the model again when something was recorded, and once per visitor every few minutes', async () => {
    const ctx = setup({ precedents: 40 });
    await ctx.post('/api/record', { claim, outcome: 'approve' });
    const res = await ctx.post('/api/reset', {});
    expect((await body(res)).ledger).toHaveLength(40);
    expect(ctx.ada.seen.filter((s) => s.method === 'DELETE')).toHaveLength(1);
    expect(ctx.ada.seen.find((s) => s.method === 'DELETE')!.search).toBe(`?confirm=${MODEL}`);
    expect((await ctx.post('/api/reset', {})).status).toBe(429);
  });

  it('calls nothing when the model already holds exactly the 40', async () => {
    const ctx = setup({ precedents: 40 });
    await ctx.request('/api/state');
    const before = ctx.ada.seen.length;
    await ctx.post('/api/reset', {});
    expect(ctx.ada.seen.length).toBe(before);
  });
});

describe('the page', () => {
  const page = () => serveDemoPage(createDemo({ config: { ...config, key: undefined }, history }));

  it.each([
    ['/', 'text/html'],
    ['/app.js', 'text/javascript'],
    ['/styles.css', 'text/css'],
  ])('serves %s', async (path, type) => {
    const res = await page().request(`https://demo.test${path}`);
    expect(res.status).toBe(200);
    expect(res.headers.get('content-type')).toContain(type);
  });

  it.each(['/history.json', '/../history.json', '/../server/demo.ts', '/login', '/auth/session'])('has nothing at %s', async (path) => {
    expect((await page().request(`https://demo.test${path}`)).status).toBe(404);
  });

  it('holds no key in what it serves', async () => {
    const js = await (await page().request('https://demo.test/app.js')).text();
    expect(js).not.toMatch(/glyphh_ak_|authorization/i);
  });
});

describe('the rest of /api', () => {
  it.each([
    ['GET', '/api/v1/models'],
    ['POST', '/api/delete'],
    ['GET', '/api/ada/v1/models'],
  ])('%s %s is refused and calls nothing', async (method, path) => {
    const ctx = setup({ precedents: 40 });
    const res = await ctx.request(path, { method });
    expect(res.status).toBe(403);
    expect(ctx.ada.seen).toHaveLength(0);
  });
});
