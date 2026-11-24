import { spawn } from 'node:child_process';
import { Hono, type Context } from 'hono';
import { Window, type DemoConfig } from './demo.js';

/**
 * demo.glyphh.ai/screener: the Resume Screener, on the page. A visitor pastes an application's email (with its
 * headers when they have them), attaches the cover letter and the resume, and sees the verdict: is this a real
 * person, signal by signal, then the fit, then how it was written.
 *
 * One source. The reading, the checks, the order of the steps and the verdict's rule are not written here: this runs
 * the Resume Screener plugin's own `run.py` (github.com/glyphh-ai/plugins, plugins/resume-screener, at the commit
 * demo/screener/plugin.ref names; the image fetches it, see the Dockerfile). The models that decide are Ada models in
 * the demo's own org, named `demo-screener-...`, made and seeded by the plugin's own `seed.py` from the plugin's own
 * examples.
 *
 * Nothing is stored. The upload is read into memory, handed to the plugin's code on its standard input, and dropped
 * when the answer is sent: no file is written, and the application is never recorded in a model (`run.py` records
 * only with `--keep`, which is never passed here).
 */

export const SCREENER_PREFIX = 'demo-screener-';

export const SCREENER_LIMITS = {
  /** Screenings per visitor (their address). Each is about ten Ada calls. */
  perMinute: 3,
  perDay: 20,
  /** The email's characters, a file's bytes, how many files, and the whole request's bytes. */
  emailChars: 100_000,
  fileBytes: 3 * 1024 * 1024,
  files: 2,
  bodyBytes: 7 * 1024 * 1024,
  roleChars: 120,
  /** How long the plugin's code may take. */
  timeoutMs: 60_000,
};

const MINUTE = 60 * 1000;
const DAY = 24 * 60 * MINUTE;

export type ScreenRequest = { email: string; role: string; files: { name: string; base64: string }[] };
/** The plugin's code: one request in, its verdict (or `{refused}`) out. */
export type Screen = (request: ScreenRequest) => Promise<unknown>;

export type ScreenerConfig = DemoConfig & {
  /** Screenings a day for the whole page (`DEMO_SCREENER_DAILY`, default 300), so the org's plan is never spent by it. */
  screenerDaily?: number;
  /** Where the plugin's scripts are (`DEMO_SCREENER_SCRIPTS`; the image puts them at /opt/screener/scripts). */
  scripts?: string;
};

class Refusal extends Error {
  constructor(
    readonly status: 400 | 403 | 413 | 429 | 502 | 503,
    message: string,
    readonly retryAfter?: number,
  ) {
    super(message);
  }
}

/** The plugin's run.py as a child process: the request on its standard input, the verdict on its standard output. */
export function pluginScreen(config: ScreenerConfig, timeoutMs = SCREENER_LIMITS.timeoutMs, python = 'python3'): Screen {
  const scripts = config.scripts ?? '/opt/screener/scripts';
  return (request) =>
    new Promise((resolve, reject) => {
      const child = spawn(python, [`${scripts}/run.py`, '--stdin', '--prefix', SCREENER_PREFIX], {
        env: { PATH: process.env.PATH, GLYPHH_API_KEY: config.key, GLYPHH_ADA_URL: config.adaUrl, PYTHONDONTWRITEBYTECODE: '1' },
        stdio: ['pipe', 'pipe', 'pipe'],
      });
      let out = '';
      let err = '';
      const timer = setTimeout(() => child.kill('SIGKILL'), timeoutMs);
      child.stdout.on('data', (d) => (out += d));
      child.stderr.on('data', (d) => (err = (err + d).slice(-2000)));
      child.on('error', (e) => (clearTimeout(timer), reject(e)));
      child.on('close', (code) => {
        clearTimeout(timer);
        if (code !== 0) return reject(new Error(`the screener's code ended with ${code}: ${err}`));
        try {
          resolve(JSON.parse(out));
        } catch {
          reject(new Error('the screener answered something that is not JSON'));
        }
      });
      child.stdin.on('error', () => undefined);
      child.stdin.end(JSON.stringify(request));
    });
}

type Deps = { config: ScreenerConfig; screen?: Screen; now?: () => number };

export function createScreener({ config, screen = pluginScreen(config), now = Date.now }: Deps) {
  const app = new Hono();
  const minute = new Window(SCREENER_LIMITS.perMinute, MINUTE);
  const daily = new Window(SCREENER_LIMITS.perDay, DAY);
  const everyone = new Window(config.screenerDaily ?? 300, DAY, 1);

  const addressOf = (c: Context) =>
    c.req.header('cf-connecting-ip') ?? c.req.header('fly-client-ip') ?? c.req.header('x-forwarded-for')?.split(',')[0]?.trim() ?? 'unknown';

  /** The form as the plugin's code takes it; a file is PDF or DOCX by what it starts with, never by its name. */
  async function readForm(c: Context): Promise<ScreenRequest> {
    if (Number(c.req.header('content-length') ?? 0) > SCREENER_LIMITS.bodyBytes) throw new Refusal(413, 'That is too much to screen here.');
    let form: Record<string, string | File | (string | File)[]>;
    try {
      form = await c.req.parseBody({ all: true });
    } catch {
      throw new Refusal(400, 'The demo could not read that.');
    }
    const one = (v: unknown) => (typeof v === 'string' ? v : '');
    const email = one(form.email);
    const role = one(form.role).trim();
    const sent = [form.file ?? []].flat().filter((f): f is File => f instanceof File && f.size > 0);
    if (email.length > SCREENER_LIMITS.emailChars || role.length > SCREENER_LIMITS.roleChars) throw new Refusal(413, 'That is too much to screen here.');
    if (sent.length > SCREENER_LIMITS.files) throw new Refusal(400, 'Attach the resume and the cover letter: two files at most.');
    const files = [];
    for (const file of sent) {
      if (file.size > SCREENER_LIMITS.fileBytes) throw new Refusal(413, 'A file is too big: 3 MB at most.');
      const bytes = Buffer.from(await file.arrayBuffer());
      const pdf = bytes.subarray(0, 5).toString('latin1') === '%PDF-';
      const docx = bytes.subarray(0, 2).toString('latin1') === 'PK';
      if (!pdf && !docx) throw new Refusal(400, 'The files must be PDF or Word (DOCX).');
      files.push({ name: file.name.slice(0, 120) || (pdf ? 'file.pdf' : 'file.docx'), base64: bytes.toString('base64') });
    }
    if (!email.trim() && !files.length) throw new Refusal(400, 'Paste the email or attach a file.');
    return { email, role, files };
  }

  app.use('/api/screener/*', async (c, next) => {
    c.header('cache-control', 'no-store');
    if (!config.key) throw new Refusal(503, 'The demo is not set up yet.');
    const site = c.req.header('sec-fetch-site');
    const same = site ? site === 'same-origin' : c.req.header('origin') === `https://${config.host}`;
    if (!same) throw new Refusal(403, 'Screenings come from the demo page only.');
    await next();
  });

  app.post('/api/screener/screen', async (c) => {
    const who = addressOf(c);
    const wait = minute.take(who, now()) || daily.take(who, now());
    if (wait) throw new Refusal(429, 'That is a lot of screenings. Give it a minute.', wait);
    const request = await readForm(c);
    const full = everyone.take('all', now());
    if (full) throw new Refusal(429, 'The demo has screened all it can today. Come back tomorrow.', full);
    let answer: unknown;
    try {
      answer = await screen(request);
    } catch (e) {
      console.error('screener:', e instanceof Error ? e.message : e);
      throw new Refusal(502, 'The screener hit a snag. Try again.');
    }
    return c.json(answer as object);
  });

  app.onError((e, c) => {
    if (e instanceof Refusal) {
      if (e.retryAfter) c.header('retry-after', String(e.retryAfter));
      return c.json({ error: e.message }, e.status);
    }
    console.error('screener:', e);
    return c.json({ error: 'The screener hit a snag. Try again.' }, 502);
  });

  return app;
}

/** Requests the screener demo answers on the demo's host: its API, and /screener sent on to the page (served with the others'). */
export const isScreenerPath = (path: string) => path === '/screener' || path.startsWith('/api/screener/');

export function serveScreenerRedirect(app: Hono) {
  app.get('/screener', (c) => c.redirect('/screener/', 308));
  app.notFound((c) => c.text('Not found', 404));
  return app;
}
