import { http, HttpResponse, type HttpHandler } from 'msw';
import type { AdaJob, AdaModel, AdaUsage, AdaVersion, CloudKey, Decision, Spec } from '@/api/ada';
import { examples } from '@/lib/spec';
import { adaPlans, cloudLimits, me } from './fixtures';
import { apiError, sessionHandler, v1 } from './server';

/**
 * Ada Cloud as the server answers it with GLYPHH_ADA_CLOUD on: the account API says so (`ada_cloud`, the plans' and
 * the org's `cloud`), and the Ada API (`/api/ada/v1/*` here) answers from a small store that each write changes,
 * counting each decide against the plan's month as the server does (refused 403 E_LIMIT past it on Free, metered on
 * Basic, Pro and Team). `seen` keeps every request made to it, with its body, for tests to read.
 */

const ada = (path: string) => `*/api/ada/v1${path}`;
const at = '2026-10-20T09:00:00Z';

/** The upgrade the server names past a plan's month: the first self-serve plan that reads more (allowance.py). */
const upgradeFrom = (name: string) => (name === 'Free' ? 'Basic' : null);

export const ticketSpec: Spec = examples.find((e) => e.id === 'tickets')!.spec;

export const levers = {
  k: 15,
  min_sim: 0.1,
  word_weights: true,
  word_floor: 0.35,
  interactions: true,
  max_interactions: 5,
  rare: 5,
  calibrate_by: 'loss',
  calibrate_sample: 200,
  refresh_every: null,
  lexicon: true,
  word_pairs: false,
  max_word_pairs: 20,
  word_evidence: 2,
  shortlist: 1000,
  exact_below: 1000,
};

export const decision: Decision = {
  outcome: 'billing',
  expected_cost: 0.18,
  probabilities: { billing: 0.82, auth: 0.12, search: 0.06 },
  ask: false,
  receipts: [
    { id: 'c1a2b3', sim: 0.91, outcome: 'billing', hash: 'h1', author: 'u-chris' },
    { id: 'd4e5f6', sim: 0.77, outcome: 'auth', hash: 'h2', author: 'u-chris' },
  ],
  model: 'tickets',
  version: 1,
};

export const backtestResult = {
  version: 2,
  trained: 800,
  held_out: 200,
  output: 'default',
  active: { candidate: { name: 'active', settings: {} }, n: 200, accuracy: 0.81, top_accuracy: 0.8, log_loss: 0.52, ask_rate: 0.1, accuracy_answered: 0.85, coverage: 0.97, calibration_error: 0.04 },
  candidates: [
    {
      candidate: { settings: { word_evidence: 1 } },
      n: 200,
      accuracy: 0.84,
      top_accuracy: 0.82,
      log_loss: 0.49,
      ask_rate: 0.08,
      accuracy_answered: 0.87,
      coverage: 0.97,
      calibration_error: 0.03,
      change: { accuracy: 0.03, top_accuracy: 0.02, log_loss: -0.03, ask_rate: -0.02, calibration_error: -0.01 },
    },
    { candidate: { spec_version: 1 }, error: { code: 'E_SPEC_READING', message: 'Version 1 reads subject differently.' } },
  ],
};

type Seen = { method: string; path: string; body: unknown };

export function adaFake({ models = [] as AdaModel[], jobSteps = 2, plan = 'Pro', requests = 0 } = {}) {
  const state = {
    models: structuredClone(models),
    versions: new Map<string, AdaVersion[]>(),
    keys: [] as CloudKey[],
    jobs: new Map<string, { job: AdaJob; reads: number; result: Record<string, unknown> | null; download?: AdaJob['download'] }>(),
    seen: [] as Seen[],
    precedents: 0,
    /** Requests this month (decides; a decide of several outputs counts once per output). */
    requests,
  };
  const limits = cloudLimits[plan]!;
  const planView = { ...adaPlans.find((p) => p.name === plan)! };

  /** `GET /v1/usage`, and `cloud` on /v1/me, as the server answers them. */
  const usage = (): AdaUsage => {
    const max = limits.requests_per_month;
    return {
      plan,
      month: '2026-10',
      resets_at: '2026-11-01',
      models: state.models.length,
      precedents: { used: state.models.reduce((n, m) => n + m.precedents, 0), max: limits.precedents },
      requests: { used: state.requests, max, over: max !== null && limits.overage ? Math.max(0, state.requests - max) : 0, overage: limits.overage },
      requests_per_second: limits.requests_per_second,
    };
  };
  for (const model of state.models) {
    state.versions.set(model.name, [{ version: model.version, note: 'made', made_by: 'u-chris', made_at: at, active: true, backtest: null, ready: true, gone: false, retired_at: null, reencoded: false }]);
  }
  let next = 1;

  const record = async (request: Request, path: string) => {
    const text = request.method === 'GET' || request.method === 'DELETE' ? '' : await request.clone().text();
    let body: unknown = text;
    try {
      body = text ? JSON.parse(text) : undefined;
    } catch {
      // a file, kept as text
    }
    state.seen.push({ method: request.method, path, body });
  };

  /** A job that runs for `jobSteps` reads, then is done with `result`. */
  const addJob = (model: string, kind: string, result: Record<string, unknown> | null, download?: AdaJob['download'], awaiting = false): AdaJob => {
    const id = `job-${next++}`;
    const job: AdaJob = { id, model, kind, state: awaiting ? 'awaiting' : 'queued', percent: 0, args: {}, result: null, error: null, created_at: at, started_at: null, finished_at: null, made_by: 'u-chris' };
    state.jobs.set(id, { job, reads: 0, result, download });
    return job;
  };

  const found = (name: string) => state.models.find((m) => m.name === name);
  const missing = (name: string) => apiError(404, 'E_MODEL_MISSING', `No model ${name} in this org.`);

  const newVersion = (name: string, active: boolean, note: string) => {
    const list = state.versions.get(name)!;
    const version = Math.max(...list.map((v) => v.version)) + 1;
    if (active) for (const v of list) v.active = false;
    list.push({ version, note, made_by: 'u-chris', made_at: at, active, backtest: null, ready: active, gone: false, retired_at: null, reencoded: !active });
    if (active) found(name)!.version = version;
    return version;
  };

  const handlers: HttpHandler[] = [
    sessionHandler(),
    http.get(v1('/me'), () => HttpResponse.json({ ...me, plan: planView, ada_cloud: true, cloud: usage() })),
    http.get(v1('/plans'), () => HttpResponse.json(adaPlans)),
    // Glyphh hosts no machines with Ada Cloud on.
    http.get(v1('/rates'), () => apiError(503, 'E_UNAVAILABLE', 'Hosting is off.', { reason: 'hosting_off' })),
    http.all(ada('/*'), async ({ request }) => {
      await record(request, new URL(request.url).pathname.replace('/api/ada/v1', ''));
      return undefined;
    }),
    http.get(ada('/usage'), () => HttpResponse.json(usage())),
    http.get(ada('/models'), () => HttpResponse.json({ models: state.models.map(({ spec: _spec, ...row }) => row) })),
    http.post(ada('/models'), async ({ request }) => {
      const { name, spec } = (await request.json()) as { name: string; spec: Spec };
      if (found(name)) return apiError(409, 'E_CONFLICT', `This org has a model named ${name} already.`);
      const model: AdaModel = { name, id: `m-${next++}`, version: 1, precedents: 0, created_at: at, spec };
      state.models.push(model);
      state.versions.set(name, [{ version: 1, note: 'made', made_by: 'u-chris', made_at: at, active: true, backtest: null, ready: true, gone: false, retired_at: null, reencoded: false }]);
      return HttpResponse.json(model, { status: 201 });
    }),
    http.get(ada('/models/:name'), ({ params }) => {
      const model = found(String(params.name));
      return model ? HttpResponse.json(model) : missing(String(params.name));
    }),
    http.delete(ada('/models/:name'), ({ params }) => {
      state.models = state.models.filter((m) => m.name !== params.name);
      return HttpResponse.json({ name: params.name, deleted: true });
    }),
    http.get(ada('/models/:name/versions'), ({ params }) => HttpResponse.json({ versions: state.versions.get(String(params.name)) ?? [] })),
    http.post(ada('/models/:name/versions/:version/activate'), ({ params }) => {
      const name = String(params.name);
      const list = state.versions.get(name)!;
      for (const v of list) v.active = v.version === Number(params.version);
      found(name)!.version = Number(params.version);
      return HttpResponse.json({ version: Number(params.version), active: true, job: null });
    }),
    http.put(ada('/models/:name/spec'), async ({ params, request }) => {
      const name = String(params.name);
      const { spec, note } = (await request.json()) as { spec: Spec; note?: string };
      // A role added rewrites the cases: a re-encode job, then live.
      const reencode = JSON.stringify(spec.layers) !== JSON.stringify(found(name)!.spec.layers);
      const version = newVersion(name, !reencode, note ?? '');
      if (!reencode) found(name)!.spec = spec;
      const job = reencode ? addJob(name, 'reencode', { version }) : null;
      if (job) state.jobs.get(job.id)!.result = { version, spec } as Record<string, unknown>;
      return HttpResponse.json({ version, active: !reencode, job });
    }),
    http.get(ada('/models/:name/settings'), ({ params }) => HttpResponse.json({ version: found(String(params.name))!.version, settings: { ...levers, ...found(String(params.name))!.spec.settings } })),
    http.patch(ada('/models/:name/settings'), async ({ params, request }) => {
      const name = String(params.name);
      const { changes, note } = (await request.json()) as { changes: Record<string, unknown>; note?: string };
      const model = found(name)!;
      model.spec = { ...model.spec, settings: { ...model.spec.settings, ...changes } };
      return HttpResponse.json({ version: newVersion(name, true, note ?? ''), active: true, job: null });
    }),
    http.post(ada('/decide'), async ({ request }) => {
      const body = (await request.json()) as { model: string; outputs?: string[] };
      const n = Math.max(1, body.outputs?.length ?? 0);
      const max = limits.requests_per_month;
      if (max !== null && !limits.overage && state.requests + n > max) {
        // As api/meter.py refuses past an unmetered month: not counted, with when it turns and the plan to move to.
        const message = `Your ${plan} plan's ${max.toLocaleString('en-US')} Ada reads this month are used: they start again on 2026-11-01. Upgrade to ${upgradeFrom(plan)} (the connector's upgrade tool, or Billing on the platform) to read on now.`;
        return apiError(403, 'E_LIMIT', message, { reason: 'requests', used: state.requests, max, plan, upgrade: upgradeFrom(plan), resets_at: '2026-11-01' });
      }
      state.requests += n;
      return HttpResponse.json({ ...decision, model: body.model, version: found(body.model)?.version ?? 1 });
    }),
    http.post(ada('/models/:name/imports'), ({ params }) => {
      const job = addJob(String(params.name), 'import', null, undefined, true);
      return HttpResponse.json({ ...job, upload: { url: `https://ada.test/v1/uploads/${job.id}.signed`, expires_at: 1_800_000_000 } }, { status: 202 });
    }),
    http.put(ada('/uploads/:link'), async ({ params, request }) => {
      const id = String(params.link).replace('.signed', '');
      const held = state.jobs.get(id)!;
      const rows = (await request.text()).trim().split('\n').length - 1;
      held.job.state = 'queued';
      held.result = { rows, recorded: rows - 1, added: rows - 1, replaced: 0, refused: 1, refusals: [{ row: 3, path: 'ticket.about.plan', message: 'not a value the spec takes' }] };
      const model = found(held.job.model)!;
      model.precedents += rows - 1;
      return HttpResponse.json(held.job, { status: 202 });
    }),
    http.post(ada('/models/:name/backtest'), ({ params }) => HttpResponse.json(addJob(String(params.name), 'backtest', backtestResult), { status: 202 })),
    http.post(ada('/models/:name/export'), ({ params }) =>
      HttpResponse.json(addJob(String(params.name), 'export', { filename: 'tickets.zip' }, { url: 'https://ada.test/v1/downloads/tickets.signed', expires_at: 1_800_000_000 }), { status: 202 }),
    ),
    http.get(ada('/jobs/:id'), ({ params }) => {
      const held = state.jobs.get(String(params.id));
      if (!held) return apiError(404, 'E_JOB_MISSING', 'No such job.');
      held.reads += 1;
      if (held.job.state !== 'awaiting' && held.reads >= jobSteps) {
        held.job = { ...held.job, state: 'done', percent: 100, result: held.result, finished_at: at, ...(held.download ? { download: held.download } : {}) };
        if (held.job.kind === 'reencode') {
          const { version, spec } = held.result as { version: number; spec: Spec };
          const list = state.versions.get(held.job.model)!;
          for (const v of list) v.active = v.version === version;
          list.find((v) => v.version === version)!.ready = true;
          Object.assign(found(held.job.model)!, { version, spec });
        }
      } else if (held.job.state !== 'awaiting') {
        held.job = { ...held.job, state: 'running', percent: 40 };
      }
      return HttpResponse.json(held.job);
    }),
    http.get(ada('/keys'), () => HttpResponse.json(state.keys)),
    http.post(ada('/keys'), async ({ request }) => {
      const body = (await request.json()) as { name: string; clearance: number; expires_in_days?: number };
      const key: CloudKey = { id: `key-${next++}`, name: body.name, clearance: body.clearance, created_at: at, expires_at: body.expires_in_days ? '2026-11-19T09:00:00Z' : null, revoked_at: null };
      state.keys.push(key);
      return HttpResponse.json({ ...key, key: 'glyphh_ak_secret123' }, { status: 201 });
    }),
    http.delete(ada('/keys/:id'), ({ params }) => {
      const key = state.keys.find((k) => k.id === params.id)!;
      key.revoked_at = at;
      return HttpResponse.json(key);
    }),
  ];

  return { state, handlers };
}

/** A model with some history, as most page tests start from. */
export const tickets = (): AdaModel => ({ name: 'tickets', id: 'm-tickets', version: 2, precedents: 1_240, created_at: '2026-10-01T09:00:00Z', spec: ticketSpec });
