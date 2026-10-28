import { randomUUID } from 'node:crypto';
import { Hono, type Context } from 'hono';
import { getCookie, setCookie } from 'hono/cookie';
import { LIMITS as DEMO_LIMITS, Refusal, Window, type DemoConfig } from './demo.js';

/**
 * demo.glyphh.ai/voice: a game, Ada reading how you sound against how you usually sound. No audio leaves the browser:
 * the page measures each take there (pitch, loudness, pace, pauses, wobble, length), sends only those numbers, each
 * as a change from the visitor's own usual voice, and throws the recording away. The name stays in the browser too.
 *
 * One model, `launch-demo-voice`, named here and nowhere else, never reset: it is everyone's takes, each carrying its
 * visitor's id (the cookie), so a visitor who comes back is still known and their own takes count most. Forget takes
 * every one of a visitor's precedents out of the model, checked against that id before each is deleted.
 */

export const VOICE_MODEL = 'launch-demo-voice';

export const MOODS = ['truth', 'lie', 'stressed', 'angry'] as const;
export type Mood = (typeof MOODS)[number];
export const PHRASES = ['self', 'truth', 'lie', 'free'] as const;
export type Phrase = (typeof PHRASES)[number];

/** Each measure as a change from the visitor's usual voice, and the range it is read over. */
export const MEASURES = {
  pitch: { min: -12, max: 12, bin: 1 }, // semitones up or down
  range: { min: 0.25, max: 3, bin: 0.15 }, // how far the pitch roams, × usual
  loudness: { min: -18, max: 18, bin: 1.5 }, // dB
  pace: { min: 0.4, max: 2.5, bin: 0.1 }, // syllables a second, × usual
  pauses: { min: -0.6, max: 0.6, bin: 0.05 }, // share of the take that is silence, against usual
  wobble: { min: 0.25, max: 3, bin: 0.15 }, // frame-to-frame pitch jumps, × usual
  length: { min: 0.25, max: 4, bin: 0.15 }, // seconds spoken, × usual for that phrase
} as const;
export type Measures = Record<keyof typeof MEASURES, number>;

export const VOICE_SPEC = {
  name: VOICE_MODEL,
  layers: [
    {
      name: 'take',
      segments: [
        {
          name: 'voice',
          roles: [
            { name: 'speaker', similarity_weight: 0.8 },
            { name: 'phrase', similarity_weight: 0.3 },
            ...Object.entries(MEASURES).map(([name, m]) => ({ name, numeric_config: { min_value: m.min, max_value: m.max, bin_width: m.bin } })),
          ],
        },
      ],
    },
  ],
  // Under 60% sure of one mood, the page says Ada cannot tell.
  output: { ask_below: 0.6 },
};

export const VOICE_LIMITS = {
  /** A visitor's takes kept in the model; past it, their oldest are not deleted, new ones are refused. */
  takes: 60,
  /** Precedents in the model, all visitors together. */
  precedents: 20_000,
  forgetEveryMs: 60 * 1000,
};

const VISITOR_COOKIE = 'glyphh_voice';
const MINUTE = 60 * 1000;
const DAY = 24 * 60 * MINUTE;

type Take = { phrase: Phrase; measures: Measures };

const asData = (speaker: string, t: Take) => ({ take: { voice: { speaker, phrase: t.phrase, ...t.measures } } });

/** The speaker a stored precedent carries, wherever the kernel's terms put it (`situation`, nested by layer). */
export function speakerOf(situation: unknown, depth = 0): string | undefined {
  if (typeof situation !== 'object' || situation === null || depth > 4) return undefined;
  for (const [k, v] of Object.entries(situation)) {
    if (k === 'speaker' && typeof v === 'string') return v;
    const found = speakerOf(v, depth + 1);
    if (found) return found;
  }
  return undefined;
}

/** One take from the page, as the model takes it; anything else is refused. */
export function readTake(value: unknown): Take {
  if (typeof value !== 'object' || value === null) throw new Refusal(400, 'No take was sent.');
  const t = value as Record<string, unknown>;
  if (!PHRASES.includes(t.phrase as Phrase)) throw new Refusal(400, 'The phrase is not one the demo knows.');
  const m = (typeof t.measures === 'object' && t.measures !== null ? t.measures : {}) as Record<string, unknown>;
  const extra = Object.keys(m).find((k) => !(k in MEASURES));
  if (extra) throw new Refusal(400, 'The demo takes numbers about the voice and nothing else.');
  const measures = {} as Measures;
  for (const [name, range] of Object.entries(MEASURES) as [keyof Measures, (typeof MEASURES)[keyof Measures]][]) {
    const v = m[name];
    if (typeof v !== 'number' || !Number.isFinite(v)) throw new Refusal(400, `The take is missing its ${name}.`);
    measures[name] = Math.round(Math.min(range.max, Math.max(range.min, v)) * 1000) / 1000;
  }
  return { phrase: t.phrase as Phrase, measures };
}

export const readMood = (value: unknown): Mood => {
  if (!MOODS.includes(value as Mood)) throw new Refusal(400, 'Say whether it was the truth, a lie, stressed or angry.');
  return value as Mood;
};

type Deps = {
  config: DemoConfig & { voiceDailyCalls?: number };
  fetch?: typeof fetch;
  now?: () => number;
  secureCookies?: boolean;
};

export function createVoice({ config, fetch: fetcher = fetch, now = Date.now, secureCookies = true }: Deps) {
  const app = new Hono();
  const base = `${config.adaUrl}/v1/models/${encodeURIComponent(VOICE_MODEL)}`;
  const dailyCalls = config.voiceDailyCalls ?? 300;

  let ready: Promise<void> | null = null;
  let precedents = 0;
  let day = Math.floor(now() / DAY);
  let calls = 0;
  // Takes per visitor since this process started: a cap, not a record (the model holds the takes).
  const takes = new Map<string, number>();

  const minute = new Window(DEMO_LIMITS.perMinute, MINUTE);
  const daily = new Window(DEMO_LIMITS.perDay, DAY);
  const forgets = new Window(1, VOICE_LIMITS.forgetEveryMs);

  async function ada<T>(method: string, url: string, body?: unknown): Promise<T> {
    const today = Math.floor(now() / DAY);
    if (today !== day) {
      day = today;
      calls = 0;
    }
    if (calls >= dailyCalls) throw new Refusal(429, 'Ada has listened enough for today. The game opens again at midnight UTC.');
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
    if (res.status === 404 && method !== 'POST') throw new Refusal(400, 'Ada does not have that take.');
    if (res.status === 429) throw new Refusal(429, 'Ada Cloud is busy. Try again in a moment.', Number(res.headers.get('retry-after')) || 5);
    if (!res.ok) throw new Refusal(502, `Ada Cloud did not answer (${json.error?.code ?? res.status}).`);
    return json;
  }

  /** The model there, once per process; made the first time, never emptied. */
  function prepare() {
    ready ??= (async () => {
      const { models = [] } = await ada<{ models?: { name: string; precedents?: number }[] }>('GET', `${config.adaUrl}/v1/models`);
      const found = models.find((m) => m.name === VOICE_MODEL);
      if (found) precedents = found.precedents ?? 0;
      else await ada('POST', `${config.adaUrl}/v1/models`, { name: VOICE_MODEL, spec: VOICE_SPEC });
    })().catch((e) => {
      ready = null;
      throw e;
    });
    return ready;
  }

  const addressOf = (c: Context) =>
    c.req.header('cf-connecting-ip') ?? c.req.header('fly-client-ip') ?? c.req.header('x-forwarded-for')?.split(',')[0]?.trim() ?? 'unknown';

  /** The visitor's id: a year in an HttpOnly cookie, so Ada knows their voice when they come back. */
  const visitorOf = (c: Context) => {
    let id = getCookie(c, VISITOR_COOKIE);
    if (!id || !/^[a-f0-9-]{36}$/.test(id)) {
      id = randomUUID();
      setCookie(c, VISITOR_COOKIE, id, { httpOnly: true, secure: secureCookies, sameSite: 'Lax', path: '/', maxAge: 365 * 24 * 3600 });
    }
    return id;
  };

  const limit = (c: Context) => {
    const who = addressOf(c);
    const wait = minute.take(who, now()) || daily.take(who, now());
    if (wait) throw new Refusal(429, 'That is a lot of talking. Give it a minute.', wait);
  };

  async function readBody(c: Context): Promise<Record<string, unknown>> {
    const raw = await c.req.text();
    if (raw.length > DEMO_LIMITS.bodyBytes) throw new Refusal(413, 'That is more than a take.');
    try {
      const body: unknown = raw ? JSON.parse(raw) : {};
      return typeof body === 'object' && body !== null ? (body as Record<string, unknown>) : {};
    } catch {
      throw new Refusal(400, 'The demo could not read that.');
    }
  }

  async function record(visitor: string, cases: { take: Take; mood: Mood }[]) {
    const had = takes.get(visitor) ?? 0;
    if (had + cases.length > VOICE_LIMITS.takes) throw new Refusal(429, `Ada keeps ${VOICE_LIMITS.takes} takes a person. Forget yours to start again.`);
    if (precedents + cases.length > VOICE_LIMITS.precedents) throw new Refusal(503, 'Ada has heard all the voices she can for now.');
    const got = await ada<{ ids?: string[]; precedents?: number }>('POST', `${base}/record_many`, {
      cases: cases.map((k) => ({ data: asData(visitor, k.take), outcome: k.mood })),
    });
    takes.set(visitor, had + cases.length);
    precedents = got.precedents ?? precedents + cases.length;
    return got.ids ?? [];
  }

  app.use('/api/voice/*', async (c, next) => {
    c.header('cache-control', 'no-store');
    if (!config.key) throw new Refusal(503, 'The demo is not set up yet.');
    if (c.req.method !== 'GET') {
      const site = c.req.header('sec-fetch-site');
      const same = site ? site === 'same-origin' : c.req.header('origin') === `https://${config.host}`;
      if (!same) throw new Refusal(403, 'Writes come from the demo page only.');
    }
    await prepare();
    await next();
  });

  /** The three set phrases: the visitor's own words, the truth and the lie, each recorded as what it is. */
  app.post('/api/voice/enrol', async (c) => {
    const body = await readBody(c);
    const list = Array.isArray(body.takes) ? body.takes : [];
    if (list.length !== 3) throw new Refusal(400, 'Enrolling takes the three phrases.');
    const set = list.map(readTake);
    if (set.map((t) => t.phrase).join() !== 'self,truth,lie') throw new Refusal(400, 'The three phrases come in order: yours, the truth, the lie.');
    const visitor = visitorOf(c);
    limit(c);
    const ids = await record(visitor, set.map((take) => ({ take, mood: take.phrase === 'lie' ? 'lie' : 'truth' })));
    return c.json({ ids });
  });

  app.post('/api/voice/read', async (c) => {
    const take = readTake((await readBody(c)).take);
    const visitor = visitorOf(c);
    limit(c);
    const started = performance.now();
    const d = await ada<{ outcome?: string; probabilities?: Record<string, number>; ask?: boolean; receipts?: { id: string; sim: number; outcome: string }[] }>(
      'POST',
      `${config.adaUrl}/v1/decide`,
      { model: VOICE_MODEL, data: asData(visitor, take) },
    );
    return c.json({
      outcome: d.outcome ?? null,
      probabilities: Object.fromEntries(MOODS.map((m) => [m, d.probabilities?.[m] ?? 0])),
      ask: Boolean(d.ask),
      receipts: (d.receipts ?? []).slice(0, 5).map((r) => ({ sim: r.sim, outcome: r.outcome })),
      ms: Math.round(performance.now() - started),
    });
  });

  /** The visitor says what the take really was; Ada keeps it, and knows their voice a little better. */
  app.post('/api/voice/teach', async (c) => {
    const body = await readBody(c);
    const take = readTake(body.take);
    const mood = readMood(body.mood);
    const visitor = visitorOf(c);
    limit(c);
    const [id] = await record(visitor, [{ take, mood }]);
    return c.json({ id });
  });

  /** Every take of the visitor's out of the model: each checked to be theirs, then deleted. */
  app.post('/api/voice/forget', async (c) => {
    const body = await readBody(c);
    const ids = (Array.isArray(body.ids) ? body.ids : []).filter((x): x is string => typeof x === 'string' && /^[\w-]{1,80}$/.test(x));
    if (ids.length > VOICE_LIMITS.takes) throw new Refusal(400, 'That is more takes than a person has.');
    const visitor = visitorOf(c);
    const wait = forgets.take(addressOf(c), now());
    if (wait) throw new Refusal(429, 'Ada forgot you a moment ago.', wait);
    let forgotten = 0;
    for (const id of ids) {
      const path = `${base}/precedents/${encodeURIComponent(id)}`;
      let p: { situation?: unknown };
      try {
        p = await ada('GET', path);
      } catch (e) {
        if (e instanceof Refusal && e.status === 400) continue; // already gone
        throw e;
      }
      if (speakerOf(p.situation) !== visitor) continue;
      await ada('DELETE', path).catch((e) => {
        if (!(e instanceof Refusal && e.status === 400)) throw e;
      });
      forgotten += 1;
    }
    takes.delete(visitor);
    precedents = Math.max(0, precedents - forgotten);
    // A new id from here on: what was left of the old one, if anything, is no longer theirs.
    setCookie(c, VISITOR_COOKIE, randomUUID(), { httpOnly: true, secure: secureCookies, sameSite: 'Lax', path: '/', maxAge: 365 * 24 * 3600 });
    return c.json({ forgotten });
  });

  app.all('/api/voice/*', () => {
    throw new Refusal(403, 'The voice demo answers enrol, read, teach and forget only.');
  });

  app.onError((e, c) => {
    if (e instanceof Refusal) {
      if (e.retryAfter) c.header('retry-after', String(e.retryAfter));
      c.header('cache-control', 'no-store');
      return c.json({ error: e.message }, e.status);
    }
    console.error('voice demo:', e);
    return c.json({ error: 'The demo hit a snag. Try again.' }, 502);
  });

  return app;
}

/** Requests the voice demo answers on the demo's host: its API, and /voice sent on to the page. The page itself
 * (demo/public/voice) is served with the other demos' (serveDemoPage). */
export const isVoicePath = (path: string) => path === '/voice' || path.startsWith('/api/voice/');

export function serveVoiceRedirect(app: Hono) {
  app.get('/voice', (c) => c.redirect('/voice/', 308));
  app.notFound((c) => c.text('Not found', 404));
  return app;
}
