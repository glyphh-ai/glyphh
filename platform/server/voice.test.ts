import { Hono } from 'hono';
import { createDemo, serveDemoPage, type DemoConfig } from './demo.js';
import {
  createVoice,
  isVoicePath,
  MEASURES,
  MOODS,
  readMood,
  readTake,
  sameSpec,
  SEED_SPEAKER,
  seeds,
  serveVoiceRedirect,
  speakerOf,
  VOICE_LIMITS,
  VOICE_MODEL,
  VOICE_SPEC,
} from './voice.js';
// @ts-expect-error the page's own module, plain JS
import { against, features, usual } from '../demo/public/voice/measure.js';

const body = async (res: Response): Promise<any> => res.json();
const config: DemoConfig = { host: 'demo.test', key: 'glyphh_ak_demo', adaUrl: 'https://ada.test', dailyCalls: 1000 };

type Seen = { method: string; path: string; body: any };

/**
 * A fake Ada Cloud holding precedents by id: models (none, or one on this spec or an older one), a spec's new
 * version and its job, record_many (research takes get s ids, visitors' p ids), decide, the map, a precedent, its
 * deletion.
 */
function fakeAda({ exists = false as false | 'same' | 'old' } = {}) {
  const seen: Seen[] = [];
  const store = new Map<string, { situation: any; outcome: string }>();
  let made = Boolean(exists);
  let spec: unknown = exists === 'old' ? { ...VOICE_SPEC, output: { ask_below: 0.6 } } : JSON.parse(JSON.stringify(VOICE_SPEC));
  let id = 0;
  let seeded = 0;
  const ada = new Hono();
  ada.use('*', async (c, next) => {
    const raw = await c.req.raw.clone().text();
    seen.push({ method: c.req.method, path: new URL(c.req.url).pathname, body: raw ? JSON.parse(raw) : null });
    await next();
  });
  ada.get('/v1/models', (c) => c.json({ models: made ? [{ name: VOICE_MODEL, precedents: store.size }] : [] }));
  ada.post('/v1/models', (c) => {
    made = true;
    return c.json({ name: VOICE_MODEL, version: 1 }, 201);
  });
  ada.get('/v1/models/:name', (c) => c.json({ name: VOICE_MODEL, spec }));
  ada.put('/v1/models/:name/spec', async (c) => {
    spec = (await c.req.json()).spec;
    return c.json({ version: 2, active: false, job: 'job1' });
  });
  ada.get('/v1/jobs/:id', (c) => c.json({ id: c.req.param('id'), state: 'done' }));
  ada.get('/v1/models/:name/map', () =>
    Response.json({ version: 1, dim: 64, layers: ['take'], layer: null, total: store.size, points: [...store].map(([pid, p]) => ({ id: pid, outcome: p.outcome, outcomes: {}, bits: 'AAAA' })), edges: [[0, 1, 0.9]] }),
  );
  ada.post('/v1/models/:name/record_many', async (c) => {
    const { cases } = await c.req.json();
    const ids = cases.map((k: any) => {
      const pid = k.data.take.voice.speaker === SEED_SPEAKER ? `s${++seeded}` : `p${++id}`;
      store.set(pid, { situation: k.data, outcome: k.outcome });
      return pid;
    });
    return c.json({ ids, precedents: store.size });
  });
  ada.get('/v1/models/:name/precedents/:id', (c) => {
    const p = store.get(c.req.param('id'));
    return p ? c.json({ id: c.req.param('id'), ...p }) : c.json({ error: { code: 'E_PRECEDENT_MISSING' } }, 404);
  });
  ada.delete('/v1/models/:name/precedents/:id', (c) => (store.delete(c.req.param('id')) ? c.json({ forgotten: true }) : c.json({}, 404)));
  ada.post('/v1/decide', () =>
    Response.json({ outcome: 'lie', probabilities: { lie: 0.7, truth: 0.2, stressed: 0.1 }, ask: false, receipts: [{ id: 'p3', sim: 0.8, outcome: 'lie', situation: 'x' }] }),
  );
  return { seen, store, fetch: (input: RequestInfo | URL, init?: RequestInit) => ada.fetch(new Request(input, init)) };
}

function setup(cfg: DemoConfig = config, opts: Parameters<typeof fakeAda>[0] = {}) {
  const ada = fakeAda(opts);
  const app = createVoice({ config: cfg, fetch: ada.fetch as typeof fetch, now: () => Date.UTC(2026, 9, 28, 12) });
  const post = (path: string, json: unknown, { cookie = '', ip = '1.2.3.4', site = 'same-origin' } = {}) =>
    app.request(`https://demo.test${path}`, {
      method: 'POST',
      headers: { 'content-type': 'application/json', host: 'demo.test', 'fly-client-ip': ip, 'sec-fetch-site': site, ...(cookie ? { cookie } : {}) },
      body: JSON.stringify(json),
    });
  const get = (path: string) => app.request(`https://demo.test${path}`, { headers: { host: 'demo.test', 'fly-client-ip': '1.2.3.4' } });
  return { ada, post, get };
}

const usualTake = { pitch: 0, range: 1, loudness: 0, pace: 1, pauses: 0, wobble: 1, length: 1 };
const take = (phrase: string, m: Partial<typeof usualTake> = {}) => ({ phrase, measures: { ...usualTake, ...m } });
const enrolment = { takes: [take('self'), take('truth'), take('lie', { pitch: 2, pauses: 0.1 })] };
const cookieOf = (res: Response) => res.headers.get('set-cookie')?.match(/glyphh_voice=([^;]+)/)?.[1] ?? '';

describe('readTake', () => {
  it('takes a phrase and the seven numbers, clamped to their ranges', () => {
    expect(readTake(take('free', { pitch: 40, pace: 0.1 }))).toEqual({ phrase: 'free', measures: { ...usualTake, pitch: MEASURES.pitch.max, pace: MEASURES.pace.min } });
  });
  it.each([
    [null, 'No take'],
    [{ phrase: 'song', measures: usualTake }, 'phrase'],
    [{ phrase: 'free', measures: { ...usualTake, audio: [1, 2] } }, 'nothing else'],
    [{ phrase: 'free', measures: { ...usualTake, pitch: 'high' } }, 'pitch'],
    [{ phrase: 'free', measures: { ...usualTake, wobble: Number.NaN } }, 'wobble'],
  ])('refuses %j', (value, words) => {
    expect(() => readTake(value)).toThrow(words);
  });
  it('knows the four moods only', () => {
    expect(readMood('angry')).toBe('angry');
    expect(() => readMood('sad')).toThrow('truth');
  });
});

describe('speakerOf', () => {
  it('finds the speaker however the situation nests it', () => {
    expect(speakerOf({ take: { voice: { speaker: 'a' } } })).toBe('a');
    expect(speakerOf({ voice: { speaker: 'b', pitch: 1 } })).toBe('b');
    expect(speakerOf(null)).toBeUndefined();
  });
});

describe('the spec', () => {
  it('reads every measure, the speaker a little, the phrase not at all, and asks below 45%', () => {
    const roles = VOICE_SPEC.layers[0]!.segments[0]!.roles;
    expect(roles.map((r) => r.name)).toEqual(['speaker', 'phrase', ...Object.keys(MEASURES)]);
    expect(roles.slice(0, 2).map((r) => r.similarity_weight)).toEqual([0.3, 0]);
    expect(VOICE_SPEC.output.ask_below).toBe(0.45);
  });
  it('knows itself in another key order, and not with any lever changed', () => {
    const reordered = JSON.parse(JSON.stringify(VOICE_SPEC, (_k, v) => (v && typeof v === 'object' && !Array.isArray(v) ? Object.fromEntries(Object.entries(v).reverse()) : v)));
    expect(sameSpec(reordered)).toBe(true);
    expect(sameSpec({ ...VOICE_SPEC, output: { ask_below: 0.6 } })).toBe(false);
  });
});

describe('the research takes', () => {
  const all = seeds();
  const mean = (mood: string, k: keyof typeof usualTake) => {
    const of = all.filter((s) => s.mood === mood);
    return of.reduce((n, s) => n + s.measures[k], 0) / of.length;
  };
  it('are eight of each mood, the same every time, inside every range', () => {
    expect(MOODS.map((m) => all.filter((s) => s.mood === m).length)).toEqual([8, 8, 8, 8]);
    expect(seeds()).toEqual(all);
    // Inside every range: reading one as a take clamps nothing.
    for (const s of all) expect(readTake({ phrase: 'free', measures: s.measures }).measures).toEqual(s.measures);
  });
  it('sound as the research says: anger loudest and widest, stress shakiest, a lie slowest with the most pauses', () => {
    expect(mean('angry', 'loudness')).toBeGreaterThan(mean('stressed', 'loudness') + 3);
    expect(mean('angry', 'range')).toBeGreaterThan(1.3);
    expect(mean('stressed', 'wobble')).toBeGreaterThan(mean('angry', 'wobble'));
    expect(mean('lie', 'pauses')).toBeGreaterThan(mean('truth', 'pauses') + 0.05);
    expect(Math.abs(mean('truth', 'pitch'))).toBeLessThan(0.5);
  });
});

describe('the voice API', () => {
  it('makes the model the first time, seeds it with the research takes, then records the three phrases as truth, truth, lie, under the visitor id', async () => {
    const { ada, post } = setup();
    const res = await post('/api/voice/enrol', enrolment);
    expect(res.status).toBe(200);
    expect((await body(res)).ids).toEqual(['p1', 'p2', 'p3']);
    const visitor = cookieOf(res);
    expect(visitor).toMatch(/^[a-f0-9-]{36}$/);
    expect(ada.seen.find((s) => s.method === 'POST' && s.path === '/v1/models')?.body).toEqual({ name: VOICE_MODEL, spec: VOICE_SPEC });
    const [seeding, rec] = ada.seen.filter((s) => s.path.endsWith('/record_many'));
    expect(seeding!.body.cases.map((c: any) => c.outcome).sort()).toEqual(MOODS.flatMap((m) => Array(8).fill(m)).sort());
    expect(seeding!.body.cases.every((c: any) => c.data.take.voice.speaker === SEED_SPEAKER)).toBe(true);
    expect(rec).toBeDefined();
    if (!rec) return;
    expect(rec.path).toBe(`/v1/models/${VOICE_MODEL}/record_many`);
    expect(rec.body.cases.map((c: any) => c.outcome)).toEqual(['truth', 'truth', 'lie']);
    expect(rec.body.cases.every((c: any) => c.data.take.voice.speaker === visitor)).toBe(true);
    expect(JSON.stringify(rec.body)).not.toMatch(/name|audio/);
  });

  it('never makes the model again, nor seeds it, when it is there on this spec', async () => {
    const { ada, post } = setup(config, { exists: 'same' });
    await post('/api/voice/enrol', enrolment);
    expect(ada.seen.some((s) => s.method === 'POST' && s.path === '/v1/models')).toBe(false);
    expect(ada.seen.some((s) => s.method === 'DELETE' || s.method === 'PUT')).toBe(false);
    expect(ada.seen.filter((s) => s.path.endsWith('/record_many'))).toHaveLength(1);
  });

  it('gives a model on an older spec this one as a new version, waits for its job, then seeds it, keeping its takes', async () => {
    const { ada, post } = setup(config, { exists: 'old' });
    await post('/api/voice/enrol', enrolment);
    const order = ada.seen.map((s) => `${s.method} ${s.path}`);
    const put = order.indexOf(`PUT /v1/models/${VOICE_MODEL}/spec`);
    expect(put).toBeGreaterThan(-1);
    expect(ada.seen[put]!.body.spec).toEqual(VOICE_SPEC);
    expect(order.indexOf('GET /v1/jobs/job1')).toBeGreaterThan(put);
    expect(order.indexOf(`POST /v1/models/${VOICE_MODEL}/record_many`)).toBeGreaterThan(order.indexOf('GET /v1/jobs/job1'));
    expect(ada.seen.some((s) => s.method === 'DELETE')).toBe(false);
    expect([...ada.store.keys()].filter((k) => k.startsWith('s'))).toHaveLength(32);
  });

  it('shows the model in 3D: each take’s id, mood and bits, and its nearest; a new take shows at once', async () => {
    const { ada, post, get } = setup();
    const before = await body(await get('/api/voice/map'));
    expect(before.points[0]).toEqual({ id: 's1', outcome: 'truth', bits: 'AAAA' });
    expect(before.edges).toEqual([[0, 1, 0.9]]);
    expect(ada.seen.find((s) => s.path.endsWith('/map'))).toBeDefined();
    expect(before.points).toHaveLength(32);
    await post('/api/voice/teach', { take: take('free'), mood: 'angry' });
    expect((await body(await get('/api/voice/map'))).points).toHaveLength(33);
  });

  it.each([
    [{ takes: [take('self')] }, 'three'],
    [{ takes: [take('truth'), take('self'), take('lie')] }, 'order'],
  ])('refuses an enrolment of %j', async (json, words) => {
    const res = await setup().post('/api/voice/enrol', json);
    expect(res.status).toBe(400);
    expect((await body(res)).error).toContain(words);
  });

  it('reads a take: every mood with its likelihood, the closest takes without their cases', async () => {
    const { ada, post } = setup();
    const res = await post('/api/voice/read', { take: take('free', { pitch: 3 }) }, { cookie: 'glyphh_voice=11111111-1111-1111-1111-111111111111' });
    const a = await body(res);
    expect(a.probabilities).toEqual({ truth: 0.2, lie: 0.7, stressed: 0.1, angry: 0 });
    expect(a.outcome).toBe('lie');
    expect(a.receipts).toEqual([{ sim: 0.8, outcome: 'lie' }]);
    const d = ada.seen.find((s) => s.path === '/v1/decide')!;
    expect(d.body).toEqual({ model: VOICE_MODEL, data: { take: { voice: { speaker: '11111111-1111-1111-1111-111111111111', ...take('free', { pitch: 3 }) .measures, phrase: 'free' } } } });
  });

  it('is taught what a take really was', async () => {
    const { ada, post } = setup();
    const res = await post('/api/voice/teach', { take: take('free'), mood: 'stressed' });
    expect(await body(res)).toEqual({ id: 'p1' });
    expect(ada.store.get('p1')!.outcome).toBe('stressed');
  });

  it(`keeps ${VOICE_LIMITS.takes} takes a person`, async () => {
    const { post } = setup();
    const first = await post('/api/voice/enrol', enrolment);
    const cookie = `glyphh_voice=${cookieOf(first)}`;
    let last: Response = first;
    for (let i = 4; i <= VOICE_LIMITS.takes; i++) last = await post('/api/voice/teach', { take: take('free'), mood: 'truth' }, { cookie, ip: `9.9.${i}.1` });
    expect(last.status).toBe(200);
    const over = await post('/api/voice/teach', { take: take('free'), mood: 'truth' }, { cookie, ip: '9.9.9.9' });
    expect(over.status).toBe(429);
  });

  it('forgets only the visitor’s own takes, then gives them a new id', async () => {
    const { ada, post } = setup();
    const mine = await post('/api/voice/enrol', enrolment);
    const theirs = await post('/api/voice/enrol', enrolment, { ip: '5.6.7.8' });
    const cookie = `glyphh_voice=${cookieOf(mine)}`;
    const res = await post('/api/voice/forget', { ids: [...(await body(mine)).ids, ...(await body(theirs)).ids, 'p99'] }, { cookie });
    expect(await body(res)).toEqual({ forgotten: 3 });
    expect([...ada.store.keys()].filter((k) => k.startsWith('p'))).toEqual(['p4', 'p5', 'p6']);
    expect(cookieOf(res)).not.toBe(cookieOf(mine));
  });

  it('refuses writes from other sites, unknown paths, and everything without a key', async () => {
    expect((await setup().post('/api/voice/read', { take: take('free') }, { site: 'cross-site' })).status).toBe(403);
    expect((await setup().post('/api/voice/models', {})).status).toBe(403);
    const off = setup({ ...config, key: undefined });
    expect((await off.post('/api/voice/read', { take: take('free') })).status).toBe(503);
    expect(off.ada.seen).toEqual([]);
  });
});

describe('the page', () => {
  // The page is served with the other demos' (serveDemoPage); /voice itself is sent on to it.
  const page = () => serveDemoPage(createDemo({ config: { ...config, key: undefined }, history: [] }));

  it.each([
    ['/voice/', 'text/html'],
    ['/voice/voice.js', 'text/javascript'],
    ['/voice/measure.js', 'text/javascript'],
    ['/voice/voice.css', 'text/css'],
  ])('serves %s', async (path, type) => {
    const res = await page().request(`https://demo.test${path}`);
    expect(res.status).toBe(200);
    expect(res.headers.get('content-type')).toContain(type);
  });

  it('says on the page that no audio is kept or sent', async () => {
    const html = await (await page().request('https://demo.test/voice/')).text();
    expect(html).toContain('No audio is kept or sent.');
  });

  it('has nothing of the server’s', async () => {
    expect((await page().request('https://demo.test/voice/../../server/voice.ts')).status).toBe(404);
  });

  it('sends /voice on to /voice/', async () => {
    const res = await serveVoiceRedirect(createVoice({ config })).request('https://demo.test/voice');
    expect(res.status).toBe(308);
    expect(res.headers.get('location')).toBe('/voice/');
  });

  it('serves the platform’s 3D view, built, at /voice/3d', async () => {
    const res = await serveVoiceRedirect(createVoice({ config }), 'server/testdata').request('https://demo.test/voice/3d/glyph-view.js');
    expect(res.status).toBe(200);
    expect(res.headers.get('content-type')).toContain('text/javascript');
    expect((await serveVoiceRedirect(createVoice({ config }), 'server/testdata').request('https://demo.test/voice/3d/other.js')).status).toBe(404);
  });

  it('takes /voice, /voice/3d and /api/voice only, the page left to the demos’', () => {
    expect(['/voice', '/voice/3d/glyph-view.js', '/api/voice/read'].every(isVoicePath)).toBe(true);
    expect(['/', '/voice/', '/voice/voice.js', '/api/decide', '/voiceover'].some(isVoicePath)).toBe(false);
  });

  it('wears the platform’s look: its stylesheet last, the wordmark', async () => {
    for (const path of ['/', '/expenses/', '/voice/']) {
      const html = await (await page().request(`https://demo.test${path}`)).text();
      const sheets = [...html.matchAll(/rel="stylesheet" href="([^"]+)"/g)].map((m) => m[1]);
      expect(sheets.at(-1)).toBe('/platform.css');
      expect(html).toContain('/glyphh-logo-text-white.png');
      expect(html).not.toContain('sentient');
    }
  });
});

describe('measuring a take', () => {
  const RATE = 12000;
  /** A voice-like tone at `hz`, loud for syllables of 200 ms with 100 ms between, then silence either side. */
  const tone = (hz: number, gain = 0.3, syllables = 8) => {
    const x = new Float32Array(RATE * 4);
    for (let i = 0; i < x.length; i++) {
      const t = i / RATE;
      const on = t > 0.5 && t < 0.5 + syllables * 0.3 && (t - 0.5) % 0.3 < 0.2;
      x[i] = on ? gain * (Math.sin(2 * Math.PI * hz * t) + 0.5 * Math.sin(4 * Math.PI * hz * t)) : 0.0005 * Math.sin(i);
    }
    return x;
  };

  it('hears the pitch, the syllables and the pauses', () => {
    const f = features(tone(200));
    expect(f.pitch).toBeCloseTo(12, 0); // 200 Hz is 12 semitones over 100
    expect(f.pace).toBeGreaterThan(2.5);
    expect(f.pace).toBeLessThan(4.5);
    expect(f.pauses).toBeGreaterThan(0.1); // the 100 ms gaps, less what the 43 ms frames smear
  });

  it('reads a higher, louder take against the usual voice', () => {
    const base = usual([{ ...features(tone(150)), perWord: 0.3 }, { ...features(tone(150)), perWord: 0.3 }]);
    const m = against({ ...features(tone(300, 0.6)), perWord: 0.3 }, base);
    expect(m.pitch).toBeCloseTo(12, 0);
    expect(m.loudness).toBeGreaterThan(4);
    expect(m.length).toBeCloseTo(1);
  });

  it('gives nothing for silence', () => {
    expect(features(new Float32Array(RATE * 2))).toBeNull();
  });
});
