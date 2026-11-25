import { mkdtempSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { createDemo, serveDemoPage, type DemoConfig } from './demo.js';
import { SCREENER_LIMITS, SCREENER_PREFIX, createScreener, isScreenerPath, pluginScreen, serveScreenerRedirect, type ScreenRequest } from './screener.js';

const config: DemoConfig = { host: 'demo.test', key: 'glyphh_ak_demo', adaUrl: 'https://ada.test', dailyCalls: 1000 };
const PDF = new Uint8Array([...Buffer.from('%PDF-1.4 a resume')]);
const DOCX = new Uint8Array([...Buffer.from('PK\u0003\u0004 a letter')]);
const ANSWER = {
  resume: {
    fake: { closeness: 0.91, nearest: [{ closeness: 0.91, like: 'Keisha Dubois - backend engineer' }] },
    real: { closeness: 0.62, nearest: [{ closeness: 0.62, like: 'FINANCE' }] },
    reads: 'reads like the fakes',
  },
  decision: { outcome: 'fake', confidence: 0.87, ask: false, on: 'resume', facts: [{ outcome: 'fake', tree: { key: '', weight: 1, score: 0.4, children: [] } }] },
};

function setup(cfg: Partial<DemoConfig> & { screenerDaily?: number } = {}, screen?: (r: ScreenRequest) => Promise<unknown>) {
  const seen: ScreenRequest[] = [];
  const clock = { now: Date.UTC(2026, 10, 24, 12) };
  const app = createScreener({
    config: { ...config, ...cfg },
    now: () => clock.now,
    screen: screen ?? (async (r) => (seen.push(r), ANSWER)),
  });
  const send = (form: FormData, headers: Record<string, string> = {}) =>
    app.request('https://demo.test/api/screener/screen', { method: 'POST', body: form, headers: { 'sec-fetch-site': 'same-origin', ...headers } });
  return { app, seen, clock, send };
}

function form({ resume = ['resume.pdf', PDF] as [string, Uint8Array] | null, letter = null as [string, Uint8Array] | null } = {}) {
  const f = new FormData();
  if (resume) f.set('resume', new File([resume[1]], resume[0]));
  if (letter) f.set('letter', new File([letter[1]], letter[0]));
  return f;
}

describe('the check', () => {
  it('hands the resume and the cover letter to the plugin’s code, each as what it is, and answers its answer unchanged', async () => {
    const { send, seen } = setup();
    const res = await send(form({ letter: ['letter.docx', DOCX] }));
    expect(res.status).toBe(200);
    expect(res.headers.get('cache-control')).toBe('no-store');
    expect(await res.json()).toEqual(ANSWER);
    expect(seen).toEqual([
      { resume: { name: 'resume.pdf', base64: Buffer.from(PDF).toString('base64') }, letter: { name: 'letter.docx', base64: Buffer.from(DOCX).toString('base64') } },
    ]);
  });

  it('takes either one alone; an empty file field is no file', async () => {
    const { send, seen } = setup();
    expect((await send(form({ letter: ['', new Uint8Array()] }))).status).toBe(200);
    expect((await send(form({ resume: null, letter: ['l.pdf', PDF] }))).status).toBe(200);
    expect(seen.map((r) => Object.keys(r))).toEqual([['resume'], ['letter']]);
  });

  it.each([
    ['nothing at all', form({ resume: null }), 400, 'Attach a resume, a cover letter, or both.'],
    ['a file that is neither PDF nor Word', form({ resume: ['resume.pdf', new Uint8Array([1, 2, 3, 4, 5])] }), 400, 'The files must be PDF or Word (DOCX).'],
    ['a file too big', form({ resume: ['big.pdf', new Uint8Array(SCREENER_LIMITS.fileBytes + 1).fill(37)] }), 413, 'A file is too big: 3 MB at most.'],
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

  it('lets a visitor check a few a minute, by their address, and says when to come back', async () => {
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

  it('stops for the day when the whole page has had its share', async () => {
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
});

describe('the plugin’s code as a process', () => {
  // A stand-in for check.py, run by node: it answers what it was given, so the test sees exactly what is handed over.
  const scripts = mkdtempSync(join(tmpdir(), 'screener-'));
  const stand = (body: string) => writeFileSync(join(scripts, 'check.py'), body);
  const request: ScreenRequest = { resume: { name: 'cv.pdf', base64: 'JVBERi0=' } };
  const run = (timeoutMs = 5000) => pluginScreen({ ...config, scripts }, timeoutMs, process.execPath)(request);

  it('gives the request on standard input, the demo’s key and model names by argument and environment, and reads the answer', async () => {
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

  it('is one thing in and one thing out: two files, and nothing of email, role or fit', async () => {
    const html = await (await page().request('https://demo.test/screener/')).text();
    expect(html.match(/type="file"/g)).toHaveLength(2);
    expect(html).toContain('name="resume"');
    expect(html).toContain('name="letter"');
    expect(html).not.toMatch(/textarea|name="email"|name="role"|timestamps|Greenhouse/);
  });

  it('says the upload is not stored, what the model is, and that it is no proof', async () => {
    const html = await (await page().request('https://demo.test/screener/')).text();
    expect(html).toContain('Nothing you upload is stored.');
    expect(html).toContain('read in memory');
    expect(html).toContain('generated, fictional applications');
    expect(html).toContain('never a name');
    expect(html).toContain('It is not proof that anyone is real or fake.');
    expect(html).toContain('docs/closeness-model.md');
    expect(html).toContain('https://github.com/glyphh-ai/plugins/tree/main/plugins/resume-screener');
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

  it('holds no key, draws the two numbers, Ada’s confidence and Ada’s fact tree, and builds nothing from markup', async () => {
    const js = await (await page().request('https://demo.test/screener/screener.js')).text();
    expect(js).not.toMatch(/glyphh_ak_|authorization/i);
    expect(js).toContain("fetch('/api/screener/screen', { method: 'POST', body: new FormData($('form')) })");
    expect(js).toContain("side('Closest fake', p.fake), side('Closest real', p.real)");
    expect(js).toContain('node(f.tree, 0)');
    expect(js).toContain('d.confidence');
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
