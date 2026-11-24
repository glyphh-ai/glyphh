import { mkdtempSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { createDemo, serveDemoPage, type DemoConfig } from './demo.js';
import { SCREENER_LIMITS, SCREENER_PREFIX, createScreener, isScreenerPath, pluginScreen, serveScreenerRedirect, type ScreenRequest } from './screener.js';

const config: DemoConfig = { host: 'demo.test', key: 'glyphh_ak_demo', adaUrl: 'https://ada.test', dailyCalls: 1000 };
const PDF = new Uint8Array([...Buffer.from('%PDF-1.4 a resume')]);
const DOCX = new Uint8Array([...Buffer.from('PK\u0003\u0004 a letter')]);
const VERDICT = {
  applicant: 'Ann Lee - data analyst',
  person: { verdict: 'unsure', signals: [{ signal: 'timing', title: 'Email timestamps', says: 'not checked', by: 'rule', found: ['there was nothing to check'] }], ask: [] },
  fit: { outcome: 'strong', confidence: 0.9, ask: false, found: [] },
  made: { outcome: 'some', confidence: 0.6, ask: false, found: [] },
};

function setup(cfg: Partial<DemoConfig> & { screenerDaily?: number } = {}, screen?: (r: ScreenRequest) => Promise<unknown>) {
  const seen: ScreenRequest[] = [];
  const clock = { now: Date.UTC(2026, 10, 24, 12) };
  const app = createScreener({
    config: { ...config, ...cfg },
    now: () => clock.now,
    screen: screen ?? (async (r) => (seen.push(r), VERDICT)),
  });
  const send = (form: FormData, headers: Record<string, string> = {}) =>
    app.request('https://demo.test/api/screener/screen', { method: 'POST', body: form, headers: { 'sec-fetch-site': 'same-origin', ...headers } });
  return { app, seen, clock, send };
}

function form({ email = 'Hello, my resume is attached.', role = '', files = [['resume.pdf', PDF]] as [string, Uint8Array][] } = {}) {
  const f = new FormData();
  f.set('email', email);
  f.set('role', role);
  for (const [name, bytes] of files) f.append('file', new File([bytes], name));
  return f;
}

describe('screening', () => {
  it('hands the email, the role and the files to the plugin’s code and answers its verdict unchanged', async () => {
    const { send, seen } = setup();
    const res = await send(form({ role: ' Data Analyst ', files: [['letter.docx', DOCX], ['cv.pdf', PDF]] }));
    expect(res.status).toBe(200);
    expect(res.headers.get('cache-control')).toBe('no-store');
    expect(await res.json()).toEqual(VERDICT);
    expect(seen).toEqual([
      {
        email: 'Hello, my resume is attached.',
        role: 'Data Analyst',
        files: [
          { name: 'letter.docx', base64: Buffer.from(DOCX).toString('base64') },
          { name: 'cv.pdf', base64: Buffer.from(PDF).toString('base64') },
        ],
      },
    ]);
  });

  it('screens an email alone, and files alone; an empty file field is no file', async () => {
    const { send, seen } = setup();
    expect((await send(form({ files: [['', new Uint8Array()]] }))).status).toBe(200);
    expect((await send(form({ email: '' }))).status).toBe(200);
    expect(seen.map((r) => r.files.length)).toEqual([0, 1]);
  });

  it.each([
    ['nothing at all', form({ email: ' ', files: [] }), 400, 'Paste the email or attach a file.'],
    ['a file that is neither PDF nor Word', form({ files: [['resume.pdf', new Uint8Array([1, 2, 3, 4, 5])]] }), 400, 'The files must be PDF or Word (DOCX).'],
    ['three files', form({ files: [['a.pdf', PDF], ['b.pdf', PDF], ['c.pdf', PDF]] }), 400, 'Attach the resume and the cover letter: two files at most.'],
    ['a file too big', form({ files: [['big.pdf', new Uint8Array(SCREENER_LIMITS.fileBytes + 1).fill(37)]] }), 413, 'A file is too big: 3 MB at most.'],
    ['an email too long', form({ email: 'x'.repeat(SCREENER_LIMITS.emailChars + 1) }), 413, 'That is too much to screen here.'],
    ['a role too long', form({ role: 'x'.repeat(SCREENER_LIMITS.roleChars + 1) }), 413, 'That is too much to screen here.'],
  ])('refuses %s before the plugin’s code is run', async (_what, sent, status, message) => {
    const { send, seen } = setup();
    const res = await send(sent);
    expect(res.status).toBe(status);
    expect(await res.json()).toEqual({ error: message });
    expect(seen).toEqual([]);
  });

  it('refuses a request that says it is too big, and one that is not a form', async () => {
    const { send, app, seen } = setup();
    expect((await send(form(), { 'content-length': String(SCREENER_LIMITS.bodyBytes + 1) })).status).toBe(413);
    const res = await app.request('https://demo.test/api/screener/screen', {
      method: 'POST',
      body: 'not a form',
      headers: { 'sec-fetch-site': 'same-origin', 'content-type': 'multipart/form-data' },
    });
    expect(res.status).toBe(400);
    expect(seen).toEqual([]);
  });

  it('answers only the demo page: same origin, or its origin when the browser does not say', async () => {
    const { send, app } = setup();
    expect((await send(form(), { 'sec-fetch-site': 'cross-site' })).status).toBe(403);
    const by = (origin: string) => app.request('https://demo.test/api/screener/screen', { method: 'POST', body: form(), headers: { origin } });
    expect((await by('https://evil.test')).status).toBe(403);
    expect((await by('https://demo.test')).status).toBe(200);
  });

  it('is not set up without the demo’s key', async () => {
    const { send } = setup({ key: undefined });
    const res = await send(form());
    expect(res.status).toBe(503);
    expect(await res.json()).toEqual({ error: 'The demo is not set up yet.' });
  });

  it('lets a visitor screen a few a minute, by their address, and says when to come back', async () => {
    const { send, clock } = setup();
    const from = (ip: string) => send(form(), { 'fly-client-ip': ip });
    for (let i = 0; i < SCREENER_LIMITS.perMinute; i++) expect((await from('1.1.1.1')).status).toBe(200);
    const res = await from('1.1.1.1');
    expect(res.status).toBe(429);
    expect(Number(res.headers.get('retry-after'))).toBeGreaterThan(0);
    expect((await from('2.2.2.2')).status).toBe(200);
    expect((await send(form(), { 'cf-connecting-ip': '3.3.3.3', 'fly-client-ip': '1.1.1.1' })).status).toBe(200);
    expect((await send(form(), { 'x-forwarded-for': '4.4.4.4, 9.9.9.9' })).status).toBe(200);
    clock.now += 61_000;
    expect((await from('1.1.1.1')).status).toBe(200);
  });

  it('stops for the day when the whole page has screened its share', async () => {
    const { send } = setup({ screenerDaily: 2 });
    const from = (n: number) => send(form(), { 'fly-client-ip': `5.5.5.${n}` });
    expect((await from(1)).status).toBe(200);
    expect((await from(2)).status).toBe(200);
    const res = await from(3);
    expect(res.status).toBe(429);
    expect(await res.json()).toEqual({ error: 'The demo has screened all it can today. Come back tomorrow.' });
  });

  it('says it hit a snag when the plugin’s code fails, and nothing of why', async () => {
    const quiet = vi.spyOn(console, 'error').mockImplementation(() => undefined);
    const { send } = setup({}, async () => Promise.reject(new Error('the key glyphh_ak_demo was refused')));
    const res = await send(form());
    expect(res.status).toBe(502);
    expect(await res.text()).not.toContain('glyphh_ak_demo');
    const { app } = setup({}, () => {
      throw 'not an error';
    });
    expect((await app.request('https://demo.test/api/screener/screen', { method: 'POST', body: form(), headers: { 'sec-fetch-site': 'same-origin' } })).status).toBe(502);
    quiet.mockRestore();
  });

  it('passes the plugin’s refusal through', async () => {
    const { send } = setup({}, async () => ({ refused: { why: 'the sender’s domain did not vouch for it' } }));
    expect(await (await send(form())).json()).toEqual({ refused: { why: 'the sender’s domain did not vouch for it' } });
  });
});

describe('the plugin’s code as a process', () => {
  // A stand-in for run.py, run by node: it answers what it was given, so the test sees exactly what is handed over.
  const scripts = mkdtempSync(join(tmpdir(), 'screener-'));
  const stand = (body: string) => writeFileSync(join(scripts, 'run.py'), body);
  const request: ScreenRequest = { email: 'Hello', role: 'Analyst', files: [{ name: 'cv.pdf', base64: 'JVBERi0=' }] };
  const run = (timeoutMs = 5000) => pluginScreen({ ...config, scripts }, timeoutMs, process.execPath)(request);

  it('gives the request on standard input, the demo’s key and model names by argument and environment, and reads the verdict', async () => {
    stand(`let s='';process.stdin.on('data',d=>s+=d).on('end',()=>console.log(JSON.stringify({got:JSON.parse(s),args:process.argv.slice(2),key:process.env.GLYPHH_API_KEY,url:process.env.GLYPHH_ADA_URL,home:process.env.HOME??null})))`);
    expect(await run()).toEqual({ got: request, args: ['--stdin', '--prefix', SCREENER_PREFIX], key: 'glyphh_ak_demo', url: 'https://ada.test', home: null });
  });

  it('fails when the code ends badly, answers no JSON, or takes too long', async () => {
    stand(`console.error('boom');process.exit(3)`);
    await expect(run()).rejects.toThrow('ended with 3: boom');
    stand(`console.log('not json')`);
    await expect(run()).rejects.toThrow('not JSON');
    stand(`setTimeout(()=>{},60000)`);
    await expect(run(200)).rejects.toThrow('ended with null');
    await expect(pluginScreen({ ...config, scripts }, 5000, join(scripts, 'no-such-python'))(request)).rejects.toThrow();
  });

  it('looks for the plugin where the image puts it', () => {
    expect(() => pluginScreen(config)).not.toThrow();
  });
});

describe('the page', () => {
  const page = () => serveDemoPage(createDemo({ config: { ...config, key: undefined }, history: [] }));

  it.each([
    ['/screener/', 'text/html'],
    ['/screener/screener.js', 'text/javascript'],
    ['/screener/screener.css', 'text/css'],
  ])('serves %s', async (path, type) => {
    const res = await page().request(`https://demo.test${path}`);
    expect(res.status).toBe(200);
    expect(res.headers.get('content-type')).toContain(type);
  });

  it('says the upload is not stored, what decides, and that nothing is proven on real people', async () => {
    const html = await (await page().request('https://demo.test/screener/')).text();
    expect(html).toContain('Nothing you upload is stored.');
    expect(html).toContain('read in memory');
    expect(html).toContain('every example is a generated, fictional application');
    expect(html).toContain('It is not proven to tell a real person from a fake one.');
    expect(html).toContain('No language model runs on this page');
  });

  it('links the plugin in the open repository and takes the email, the role and two files', async () => {
    const html = await (await page().request('https://demo.test/screener/')).text();
    expect(html).toContain('https://github.com/glyphh-ai/plugins/tree/main/plugins/resume-screener');
    expect(html.match(/type="file"/g)).toHaveLength(2);
    expect(html).toContain('<textarea id="email" name="email"');
  });

  it('wears the platform’s look: its stylesheet last, the logo as its image, labels never darker than #999', async () => {
    const html = await (await page().request('https://demo.test/screener/')).text();
    const sheets = [...html.matchAll(/rel="stylesheet" href="([^"]+)"/g)].map((m) => m[1]);
    expect(sheets.at(-1)).toBe('/platform.css');
    expect(html).toContain('<img src="/glyphh-logo-text-white.png" alt="Glyphh" class="logo">');
    expect(html.replace(/alt="Glyphh"/g, '').replace(/glyphh-ai|glyphh-logo|glyphh-mascot/g, '')).not.toMatch(/glyphh/i);
    const css = await (await page().request('https://demo.test/screener/screener.css')).text();
    const greys = [...css.matchAll(/--text(?:-\d)?: #([0-9a-f]{6})/g)].map((m) => parseInt(m[1]!.slice(0, 2), 16));
    expect(greys.length).toBeGreaterThan(3);
    expect(Math.min(...greys)).toBeGreaterThanOrEqual(0x99);
  });

  it('holds no key and draws only what the server answered', async () => {
    const js = await (await page().request('https://demo.test/screener/screener.js')).text();
    expect(js).not.toMatch(/glyphh_ak_|authorization/i);
    expect(js).toContain("fetch('/api/screener/screen', { method: 'POST', body: new FormData($('form')) })");
    expect(js).not.toContain('innerHTML');
  });

  it('sends /screener on to /screener/ and takes /screener and /api/screener only', async () => {
    const res = await serveScreenerRedirect(createScreener({ config })).request('https://demo.test/screener');
    expect(res.status).toBe(308);
    expect(res.headers.get('location')).toBe('/screener/');
    expect(['/screener', '/api/screener/screen'].every(isScreenerPath)).toBe(true);
    expect(['/', '/screener/', '/screener/screener.js', '/api/bot/start', '/screeners'].some(isScreenerPath)).toBe(false);
  });
});
