import { Hono } from 'hono';
import type { DemoConfig } from './demo.js';
import { createVoice, isVoicePath, MEASURES, readMood, readTake, serveVoicePage, speakerOf, VOICE_LIMITS, VOICE_MODEL, VOICE_SPEC } from './voice.js';
// @ts-expect-error the page's own module, plain JS
import { against, features, usual } from '../demo/voice/measure.js';

const body = async (res: Response): Promise<any> => res.json();
const config: DemoConfig = { host: 'demo.test', key: 'glyphh_ak_demo', adaUrl: 'https://ada.test', dailyCalls: 1000 };

type Seen = { method: string; path: string; body: any };

/** A fake Ada Cloud holding precedents by id: models, record_many, decide, a precedent, its deletion. */
function fakeAda({ exists = false } = {}) {
  const seen: Seen[] = [];
  const store = new Map<string, { situation: any; outcome: string }>();
  let made = exists;
  let id = 0;
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
  ada.post('/v1/models/:name/record_many', async (c) => {
    const { cases } = await c.req.json();
    const ids = cases.map((k: any) => {
      const pid = `p${++id}`;
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
  return { ada, post };
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
  it('reads every measure and the speaker, and asks below 60%', () => {
    const roles = VOICE_SPEC.layers[0]!.segments[0]!.roles.map((r) => r.name);
    expect(roles).toEqual(['speaker', 'phrase', ...Object.keys(MEASURES)]);
    expect(VOICE_SPEC.output.ask_below).toBe(0.6);
  });
});

describe('the voice API', () => {
  it('makes the model the first time and records the three phrases as truth, truth, lie, under the visitor id', async () => {
    const { ada, post } = setup();
    const res = await post('/api/voice/enrol', enrolment);
    expect(res.status).toBe(200);
    expect((await body(res)).ids).toEqual(['p1', 'p2', 'p3']);
    const visitor = cookieOf(res);
    expect(visitor).toMatch(/^[a-f0-9-]{36}$/);
    expect(ada.seen.find((s) => s.method === 'POST' && s.path === '/v1/models')?.body).toEqual({ name: VOICE_MODEL, spec: VOICE_SPEC });
    const rec = ada.seen.find((s) => s.path.endsWith('/record_many'))!;
    expect(rec.path).toBe(`/v1/models/${VOICE_MODEL}/record_many`);
    expect(rec.body.cases.map((c: any) => c.outcome)).toEqual(['truth', 'truth', 'lie']);
    expect(rec.body.cases.every((c: any) => c.data.take.voice.speaker === visitor)).toBe(true);
    expect(JSON.stringify(rec.body)).not.toMatch(/name|audio/);
  });

  it('never makes the model again when it is there', async () => {
    const { ada, post } = setup(config, { exists: true });
    await post('/api/voice/enrol', enrolment);
    expect(ada.seen.some((s) => s.method === 'POST' && s.path === '/v1/models')).toBe(false);
    expect(ada.seen.some((s) => s.method === 'DELETE')).toBe(false);
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
    expect([...ada.store.values()][0]!.outcome).toBe('stressed');
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
    expect([...ada.store.keys()]).toEqual(['p4', 'p5', 'p6']);
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
  const page = () => serveVoicePage(createVoice({ config: { ...config, key: undefined } }));

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

  it('has nothing outside /voice', async () => {
    expect((await page().request('https://demo.test/history.json')).status).toBe(404);
    expect((await page().request('https://demo.test/voice/../server/voice.ts')).status).toBe(404);
  });

  it('routes /voice and /api/voice only', () => {
    expect(['/voice', '/voice/', '/api/voice/read'].every(isVoicePath)).toBe(true);
    expect(['/', '/api/decide', '/voiceover'].some(isVoicePath)).toBe(false);
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
