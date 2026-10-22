import type { Hono } from 'hono';
import type { AdaJob, AdaModel, AdaUsage, AdaVersion, CloudKey, Spec } from '../src/api/ada.js';
import { cloudLimits } from '../src/test/fixtures.js';

/**
 * Ada Cloud's API for the fake server, at /ada/v1 (the platform's GLYPHH_ADA_URL=http://localhost:8080/ada), from a
 * store kept in memory: models and their versions, keys, and jobs that are done when first read. Not the kernel:
 * every decision is the most common outcome recorded, at its share. Each decide counts against the org's plan's month
 * (`plan()`, the fake server's); past it, Free is refused 403 E_LIMIT as the server refuses it, Pro and Team go on,
 * metered. Answers the usage, for /v1/me's and /v1/billing's `cloud`.
 */
export function mountAda(app: Hono, port: number, plan: () => string): () => AdaUsage {
  const models: AdaModel[] = [];
  const versions = new Map<string, AdaVersion[]>();
  const outcomes = new Map<string, string[]>();
  const keys: CloudKey[] = [];
  const jobs = new Map<string, AdaJob>();
  let next = 1;
  const now = () => new Date().toISOString();
  const base = `http://localhost:${port}/ada/v1`;
  const refuse = (status: number, code: string, message: string) => Response.json({ error: { code, message, trace_id: 'dev-trace' } }, { status });
  const found = (name: string) => models.find((m) => m.name === name);
  const job = (model: string, kind: string, result: Record<string, unknown> | null, state: AdaJob['state'] = 'queued'): AdaJob => {
    const made: AdaJob = { id: `job-${next++}`, model, kind, state, percent: 0, args: {}, result, error: null, created_at: now(), started_at: null, finished_at: null, made_by: 'u-chris' };
    jobs.set(made.id, made);
    return made;
  };
  const version = (name: string, note: string): number => {
    const list = versions.get(name)!;
    const v = list.length + 1;
    for (const old of list) old.active = false;
    list.push({ version: v, note, made_by: 'u-chris', made_at: now(), active: true, backtest: null, ready: true, gone: false, retired_at: null, reencoded: false });
    found(name)!.version = v;
    return v;
  };

  let requests = 0;
  const month = () => new Date().toISOString().slice(0, 7);
  const resetsAt = () => {
    const d = new Date();
    return new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth() + 1, 1)).toISOString().slice(0, 10);
  };
  const limits = () => cloudLimits[plan()] ?? cloudLimits.Enterprise!;
  const usage = (): AdaUsage => {
    const { precedents, requests_per_month: max, requests_per_second, overage } = limits();
    return {
      plan: plan(),
      month: month(),
      resets_at: resetsAt(),
      models: models.length,
      precedents: { used: models.reduce((n, m) => n + m.precedents, 0), max: precedents },
      requests: { used: requests, max, over: max !== null && overage ? Math.max(0, requests - max) : 0, overage },
      requests_per_second,
    };
  };

  app.get('/ada/v1/usage', (c) => c.json(usage()));
  app.get('/ada/v1/models', (c) => c.json({ models: models.map(({ spec: _spec, ...row }) => row) }));
  app.post('/ada/v1/models', async (c) => {
    const { name, spec } = (await c.req.json()) as { name: string; spec: Spec };
    if (found(name)) return refuse(409, 'E_CONFLICT', `This org has a model named ${name} already.`);
    const model: AdaModel = { name, id: `m-${next++}`, version: 1, precedents: 0, created_at: now(), spec };
    models.push(model);
    versions.set(name, [{ version: 1, note: 'made', made_by: 'u-chris', made_at: now(), active: true, backtest: null, ready: true, gone: false, retired_at: null, reencoded: false }]);
    outcomes.set(name, []);
    return c.json(model, 201);
  });
  app.get('/ada/v1/models/:name', (c) => {
    const model = found(c.req.param('name'));
    return model ? c.json(model) : refuse(404, 'E_MODEL_MISSING', `No model ${c.req.param('name')} in this org.`);
  });
  app.delete('/ada/v1/models/:name', (c) => {
    models.splice(models.indexOf(found(c.req.param('name'))!), 1);
    return c.json({ name: c.req.param('name'), deleted: true });
  });
  app.get('/ada/v1/models/:name/versions', (c) => c.json({ versions: versions.get(c.req.param('name')) ?? [] }));
  app.post('/ada/v1/models/:name/versions/:version/activate', (c) => {
    const n = Number(c.req.param('version'));
    for (const v of versions.get(c.req.param('name'))!) v.active = v.version === n;
    found(c.req.param('name'))!.version = n;
    return c.json({ version: n, active: true, job: null });
  });
  app.put('/ada/v1/models/:name/spec', async (c) => {
    const { spec, note } = (await c.req.json()) as { spec: Spec; note?: string };
    found(c.req.param('name'))!.spec = spec;
    return c.json({ version: version(c.req.param('name'), note ?? ''), active: true, job: null });
  });
  app.get('/ada/v1/models/:name/settings', (c) => {
    const model = found(c.req.param('name'))!;
    return c.json({ version: model.version, settings: { k: 15, min_sim: 0.1, word_evidence: 2, lexicon: true, calibrate_by: 'loss', refresh_every: null, ...model.spec.settings } });
  });
  app.patch('/ada/v1/models/:name/settings', async (c) => {
    const { changes, note } = (await c.req.json()) as { changes: Record<string, unknown>; note?: string };
    const model = found(c.req.param('name'))!;
    model.spec = { ...model.spec, settings: { ...model.spec.settings, ...changes } };
    return c.json({ version: version(model.name, note ?? ''), active: true, job: null });
  });
  app.post('/ada/v1/decide', async (c) => {
    const { model, outputs: asked } = (await c.req.json()) as { model: string; outputs?: string[] };
    const reads = Math.max(1, asked?.length ?? 0);
    const { requests_per_month: max, overage } = limits();
    if (max !== null && !overage && requests + reads > max) {
      const body = { code: 'E_LIMIT', message: `Your ${plan()} plan's ${max.toLocaleString('en-US')} Ada reads this month are used: they start again on ${resetsAt()}. Upgrade to Pro (the connector's upgrade tool, or Billing on the platform) to read on now.`, trace_id: 'dev-trace', reason: 'requests', used: requests, max, plan: plan(), upgrade: 'Pro', resets_at: resetsAt() };
      return Response.json({ error: body }, { status: 403 });
    }
    requests += reads;
    const seen = outcomes.get(model) ?? [];
    const counts = new Map<string, number>();
    for (const o of seen) counts.set(o, (counts.get(o) ?? 0) + 1);
    const probabilities = Object.fromEntries([...counts].map(([o, n]) => [o, Math.round((n / seen.length) * 1e4) / 1e4]));
    const best = [...counts].sort((a, b) => b[1] - a[1])[0]?.[0] ?? null;
    const receipts = seen.slice(0, 3).map((o, i) => ({ id: `case-${i + 1}`, sim: 0.9 - i * 0.1, outcome: o, hash: `h${i}`, author: 'u-chris' }));
    return c.json({ outcome: best, expected_cost: best ? 1 - (probabilities[best] ?? 0) : null, probabilities, ask: !best, receipts, model, version: found(model)?.version ?? 1 });
  });
  app.post('/ada/v1/models/:name/imports', (c) => {
    const made = job(c.req.param('name'), 'import', null, 'awaiting');
    return c.json({ ...made, upload: { url: `${base}/uploads/${made.id}`, expires_at: Date.now() / 1000 + 3600 } }, 202);
  });
  app.put('/ada/v1/uploads/:link', async (c) => {
    const made = jobs.get(c.req.param('link'))!;
    const lines = (await c.req.text()).trim().split('\n');
    const csv = !lines[0]!.startsWith('{');
    const rows = csv ? lines.slice(1) : lines;
    const at = csv ? lines[0]!.split(',').indexOf('outcome') : -1;
    const seen = outcomes.get(made.model)!;
    for (const row of rows) seen.push(csv ? (row.split(',')[at] ?? '') : String((JSON.parse(row) as { outcome?: string }).outcome ?? ''));
    found(made.model)!.precedents += rows.length;
    Object.assign(made, { state: 'queued', result: { rows: rows.length, recorded: rows.length, added: rows.length, replaced: 0, refused: 0, refusals: [] } });
    return c.json(made, 202);
  });
  app.post('/ada/v1/models/:name/backtest', (c) =>
    c.json(job(c.req.param('name'), 'backtest', { version: 1, trained: 0, held_out: 0, output: 'default', active: { candidate: {}, accuracy: 0 }, candidates: [] }), 202),
  );
  app.post('/ada/v1/models/:name/export', (c) => c.json(job(c.req.param('name'), 'export', { filename: `${c.req.param('name')}.zip` }), 202));
  app.get('/ada/v1/jobs/:id', (c) => {
    const held = jobs.get(c.req.param('id'));
    if (!held) return refuse(404, 'E_JOB_MISSING', 'No such job.');
    if (held.state !== 'awaiting') Object.assign(held, { state: 'done', percent: 100, finished_at: now() });
    if (held.kind === 'export') held.download = { url: `${base}/downloads/${held.id}`, expires_at: Date.now() / 1000 + 3600 };
    return c.json(held);
  });
  app.get('/ada/v1/downloads/:link', (c) => c.body('{}\n', 200, { 'content-disposition': `attachment; filename="export.jsonl"` }));
  app.get('/ada/v1/keys', (c) => c.json(keys));
  app.post('/ada/v1/keys', async (c) => {
    const { name, clearance = 1, expires_in_days: days } = (await c.req.json()) as { name: string; clearance?: number; expires_in_days?: number };
    const key: CloudKey = { id: `key-${next++}`, name, clearance, created_at: now(), expires_at: days ? new Date(Date.now() + days * 86_400_000).toISOString() : null, revoked_at: null };
    keys.push(key);
    return c.json({ ...key, key: `glyphh_ak_${crypto.randomUUID().replaceAll('-', '')}` }, 201);
  });
  app.delete('/ada/v1/keys/:id', (c) => c.json(Object.assign(keys.find((k) => k.id === c.req.param('id'))!, { revoked_at: now() })));
  return usage;
}
