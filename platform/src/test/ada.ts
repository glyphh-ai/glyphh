import { http, HttpResponse, type HttpHandler } from 'msw';
import type { AdaJob, AdaModel, AdaNotice, AdaRelease, AdaReleases, AdaUsage, AdaVersion, CloudKey, Decision, ModelMap, ModelStats, Spec } from '@/api/ada';
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

/** An Ada version as the registry lists it, with what is not given as a stable's would have it. */
export const releaseOf = (given: Partial<AdaRelease> & { name: string; kernel: string }): AdaRelease => ({
  status: 'stable',
  beta: false,
  open: true,
  released: '2026-10-01',
  deprecated: null,
  ends: null,
  changes_answers: true,
  aliases: [],
  summary: `${given.name}.`,
  notes: '',
  models: 0,
  ...given,
});

/**
 * Ada's versions a little after a release, newest first: a beta to try, the latest stable (`ada-1-1`), the stable
 * before it deprecated until April, and the first one retired. `models` is counted by the fake from its models.
 */
export const adaReleases = (): AdaReleases => ({
  latest_stable: 'ada-1-1',
  contract: 5,
  versions: [
    releaseOf({
      name: 'ada-1-2-beta',
      kernel: '3.14.0',
      status: 'beta',
      beta: true,
      released: '2026-10-23',
      summary: 'Pairs it never learned weigh nothing.',
      notes: 'Once a model has learned pairs, a pair value it never saw no longer pulls the answer.\n\n- Within noise on German Credit\n- Try it on your own backtest first',
    }),
    releaseOf({
      name: 'ada-1-1',
      kernel: '3.13.0',
      released: '2026-10-20',
      summary: 'Better calibrated answers.',
      notes: 'Ada now calibrates each output on its own, so **how sure** it says it is matches how often it is right.\n\nThe setting `calibrate_by` takes `loss` as before.',
    }),
    releaseOf({
      name: 'ada-1-0',
      kernel: '3.12.2',
      status: 'deprecated',
      released: '2026-09-01',
      deprecated: '2026-10-20',
      ends: '2027-04-18',
      changes_answers: true,
      aliases: ['ada-1-0-beta'],
      summary: 'The cloud’s launch.',
      notes: 'The version Ada Cloud launched with.',
    }),
    releaseOf({ name: 'ada-0-9', kernel: '3.11.0', status: 'retired', released: '2026-06-01', deprecated: '2026-09-01', ends: '2026-10-01', summary: 'The preview.', notes: 'The preview.' }),
  ],
});

/** A backtest of the live spec on another Ada: the live version, then the candidate, a little better. */
export const adaBacktest = {
  version: 2,
  trained: 800,
  held_out: 200,
  output: 'default',
  active: { candidate: { name: 'active', settings: {} }, n: 200, accuracy: 0.81, top_accuracy: 0.8, log_loss: 0.52, ask_rate: 0.1, accuracy_answered: 0.85, coverage: 0.97, calibration_error: 0.04 },
  candidates: [
    {
      candidate: { ada: 'ada-1-1' },
      n: 200,
      accuracy: 0.83,
      top_accuracy: 0.81,
      log_loss: 0.5,
      ask_rate: 0.09,
      accuracy_answered: 0.86,
      coverage: 0.97,
      calibration_error: 0.02,
      change: { accuracy: 0.02, top_accuracy: 0.01, log_loss: -0.02, ask_rate: -0.01, calibration_error: -0.02 },
    },
  ],
};

type Seen = { method: string; path: string; body: unknown };

const day = (n: number) => `2026-10-${String(n).padStart(2, '0')}`;

/** A model's dashboard with a week of reads and decides, as `GET /v1/models/{name}/stats` answers it. */
export const modelStats = (model: AdaModel): ModelStats => ({
  name: model.name,
  version: model.version,
  precedents: model.precedents,
  created_at: model.created_at,
  active: { version: model.version, note: 'Ask more', made_by: 'u-chris', made_at: at },
  plan: { plan: 'Pro', precedents: { used: model.precedents, max: 100_000 } },
  outcomes: [
    { output: null, value: 'billing', n: 700 },
    { output: null, value: 'auth', n: 400 },
    { output: null, value: null, n: 140 },
  ],
  growth: [
    { day: day(1), n: 1_000 },
    { day: day(15), n: 240 },
  ],
  jobs: [{ id: 'job-9', model: model.name, kind: 'import', state: 'done', percent: 100, args: {}, result: null, error: null, created_at: at, started_at: at, finished_at: at, made_by: 'u-chris' }],
  days: Array.from({ length: 7 }, (_, i) => ({ day: day(16 + i), reads: { decide: 10 * i, query: i, probabilities: 0, facts: 1 }, decided: 10 * i, asked: i })),
  sure: [0, 0, 0, 0, 1, 2, 5, 20, 80, 102],
  others: [],
  estimated: false,
  answers: [
    {
      output: null,
      decided: 210,
      asked: 21,
      sure: [0, 0, 0, 0, 1, 2, 5, 20, 80, 102],
      days: Array.from({ length: 7 }, (_, i) => ({ decided: 10 * i, asked: i })),
    },
  ],
});

/** Thirty days with nothing read, as the server answers a model made today. */
const quietDays = Array.from({ length: 30 }, (_, i) => ({
  day: new Date(Date.UTC(2026, 8, 23 + i)).toISOString().slice(0, 10),
  reads: { decide: 0, query: 0, probabilities: 0, facts: 0 },
  decided: 0,
  asked: 0,
}));

/** A model's dashboard before anything was read or recorded. */
export const emptyStats = (model: AdaModel): ModelStats => ({
  ...modelStats({ ...model, precedents: 0 }),
  plan: { plan: 'Pro', precedents: { used: 0, max: 100_000 } },
  outcomes: [],
  growth: [],
  jobs: [],
  days: quietDays,
  sure: Array(10).fill(0),
  answers: [],
});

/** Four precedents at dimension 16, two joined by an edge of the same outcome and one of different outcomes. */
export const modelMap = (layer: string | null): ModelMap => ({
  version: 2,
  dim: 16,
  layers: ['ticket'],
  layer,
  total: 1_240,
  points: [
    { id: 'c1a2b3', outcome: 'billing', outcomes: {}, bits: btoa('\xff\x00') },
    { id: 'd4e5f6', outcome: 'billing', outcomes: {}, bits: btoa('\xf0\x0f') },
    { id: 'a9b8c7', outcome: 'auth', outcomes: {}, bits: btoa('\x0f\xf0') },
    { id: 'e1e2e3', outcome: null, outcomes: {}, bits: layer ? null : btoa('\x00\xff') },
  ],
  edges: [
    [0, 1, 0.33],
    [1, 2, 0.14],
  ],
});

/** A version as the server lists it, with what is not given as a version on the live store would have it. */
export const versionOf = (given: Partial<AdaVersion> & { version: number }): AdaVersion => ({
  note: '',
  made_by: 'u-chris',
  made_at: at,
  active: false,
  backtest: null,
  ready: true,
  gone: false,
  retired_at: null,
  reencoded: false,
  new_store: false,
  changes: null,
  precedents_at: null,
  learned: null,
  scores: null,
  store: { status: 'active', drop_after: null },
  ada: 'ada-1-0',
  kernel: '3.12.2',
  ...given,
});

/**
 * Three versions of tickets: the first, its stored cases dropped; the second, re-encoded for another seed, kept apart,
 * learned and backtested; the third live, k raised, with notes.
 */
export const ticketHistory = (): AdaVersion[] => [
  versionOf({ version: 1, note: 'made', made_at: '2026-10-01T09:00:00Z', precedents_at: 0, gone: true, reencoded: false, store: { status: 'dropped', drop_after: null } }),
  versionOf({
    version: 2,
    made_at: '2026-10-10T09:00:00Z',
    reencoded: true,
    new_store: true,
    changes: [{ path: 'seed', from: 5, to: 11, restates: true }],
    precedents_at: 900,
    retired_at: '2026-10-20T09:00:00Z',
    learned: { default: { roles: { 'ticket.about.subject': 0.9, 'ticket.about.product': 0.4 }, words: { 'ticket.about.subject': 120 }, pairs: [['a', 'b']], tau: 0.81 } },
    scores: { job: 'job-0', at: '2026-10-19T09:00:00Z', output: 'default', n: 200, accuracy: 0.81, log_loss: 0.52, ask_rate: 0.1 },
    store: { status: 'kept', drop_after: '2026-10-27T09:00:00Z' },
  }),
  versionOf({
    version: 3,
    note: 'More voters',
    made_at: '2026-10-20T09:00:00Z',
    active: true,
    reencoded: true,
    changes: [{ path: 'settings.k', from: 15, to: 20, restates: false }],
    precedents_at: 1_200,
  }),
];

export function adaFake({
  models = [] as AdaModel[],
  jobSteps = 2,
  plan = 'Pro',
  requests = 0,
  stats = modelStats,
  map = modelMap,
  history = {} as Record<string, AdaVersion[]>,
  releases = adaReleases(),
  notices = {} as Record<string, AdaNotice | null>,
} = {}) {
  const state = {
    models: structuredClone(models),
    releases: structuredClone(releases),
    versions: new Map<string, AdaVersion[]>(),
    /** Each version's spec, by `<model>:<version>`; the model's own when not kept. */
    specs: new Map<string, Spec>(),
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
  /** An Ada name as the registry resolves it, aliases included. */
  const release = (name: string) => state.releases.versions.find((r) => r.name === name || r.aliases.includes(name));
  for (const model of state.models) {
    const made = { version: model.version, note: 'made', active: true, precedents_at: 0, ada: model.ada, kernel: release(model.ada)?.kernel ?? '3.12.2' };
    state.versions.set(model.name, structuredClone(history[model.name]) ?? [versionOf(made)]);
  }
  const specOf = (name: string, version: number): Spec => state.specs.get(`${name}:${version}`) ?? found(name)!.spec;
  /** What the server's diff says from one spec to another, for the parts the platform's tests change. */
  const diffOf = (from: Spec, to: Spec) => {
    const changes: Array<{ path: string; from: unknown; to: unknown; restates: boolean }> = [];
    for (const key of ['seed', 'dimension'] as const) if (from[key] !== to[key]) changes.push({ path: key, from: from[key] ?? null, to: to[key] ?? null, restates: true });
    const before = { ...levers, ...from.settings } as Record<string, unknown>;
    const after = { ...levers, ...to.settings } as Record<string, unknown>;
    for (const key of Object.keys(after)) if (before[key] !== after[key]) changes.push({ path: `settings.${key}`, from: before[key], to: after[key], restates: false });
    return changes;
  };
  let next = 1;
  /** The server's refusal of an Ada that can't be chosen (for a new model, or an upgrade's target), naming the latest stable. */
  const refuseAda = (name: string) => {
    const found = release(name);
    const fix = { ada: name, latest: state.releases.latest_stable };
    if (!found) return apiError(422, 'E_ADA_UNKNOWN', `There is no Ada version ${name}. The latest stable is ${fix.latest}.`, fix);
    if (found.status === 'retired') return apiError(410, 'E_ADA_RETIRED', `${name} is retired. The latest stable is ${fix.latest}.`, fix);
    if (found.status === 'deprecated') return apiError(422, 'E_ADA_DEPRECATED', `${name} is deprecated: choose ${fix.latest}.`, fix);
    if (found.beta && !found.open) return apiError(422, 'E_ADA_BETA', `${name} is closed to new models.`, fix);
    return null;
  };

  const record =async (request: Request, path: string) => {
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

  const newVersion = (name: string, active: boolean, note: string, spec: Spec) => {
    const list = state.versions.get(name)!;
    const version = Math.max(...list.map((v) => v.version)) + 1;
    const live = found(name)!;
    state.specs.set(`${name}:${live.version}`, live.spec);
    state.specs.set(`${name}:${version}`, spec);
    if (active) for (const v of list) v.active = false;
    const store: AdaVersion['store'] = { status: active ? 'active' : 'making', drop_after: null };
    const changes = diffOf(live.spec, spec);
    const ada = { ada: live.ada, kernel: release(live.ada)?.kernel ?? '3.12.2' };
    list.push(versionOf({ version, note, active, ready: active, reencoded: !active, new_store: !active, changes, precedents_at: live.precedents, store, ...ada }));
    if (active) live.version = version;
    return version;
  };

  const handlers: HttpHandler[] = [
    sessionHandler(),
    http.get(v1('/me'), () => HttpResponse.json({ ...me, plan: planView, ada_cloud: true, cloud: usage() })),
    http.get(v1('/plans'), () => HttpResponse.json(adaPlans)),
    http.all(ada('/*'), async ({ request }) => {
      await record(request, new URL(request.url).pathname.replace('/api/ada/v1', ''));
      return undefined;
    }),
    http.get(ada('/usage'), () => HttpResponse.json(usage())),
    http.get(ada('/models'), () => HttpResponse.json({ models: state.models.map(({ spec: _spec, ...row }) => row) })),
    http.get(ada('/ada'), () =>
      HttpResponse.json({
        ...state.releases,
        versions: state.releases.versions.map((r) => ({ ...r, models: state.models.filter((m) => release(m.ada)?.name === r.name).length })),
      }),
    ),
    http.post(ada('/models'), async ({ request }) => {
      const { name, spec, ada: asked } = (await request.json()) as { name: string; spec: Spec; ada?: string };
      if (found(name)) return apiError(409, 'E_CONFLICT', `This org has a model named ${name} already.`);
      const on = asked ?? state.releases.latest_stable;
      const refused = refuseAda(on);
      if (refused) return refused;
      const model: AdaModel = { name, id: `m-${next++}`, version: 1, precedents: 0, created_at: at, spec, ada: on };
      state.models.push(model);
      state.versions.set(name, [versionOf({ version: 1, note: 'made', active: true, precedents_at: 0, ada: on, kernel: release(on)!.kernel })]);
      return HttpResponse.json(model, { status: 201 });
    }),
    http.get(ada('/models/:name'), ({ params }) => {
      const model = found(String(params.name));
      if (!model) return missing(String(params.name));
      return HttpResponse.json({ ...model, ada_status: release(model.ada)?.status ?? 'stable', ada_notice: notices[model.name] ?? null });
    }),
    // An upgrade: a new version of the live spec on the target Ada, made by a re-encode job, live once it is done.
    http.post(ada('/models/:name/upgrade'), async ({ params, request }) => {
      const name = String(params.name);
      const model = found(name);
      if (!model) return missing(name);
      const { ada: asked, note } = (await request.json()) as { ada?: string; note?: string };
      const to = asked ?? state.releases.latest_stable;
      const refused = refuseAda(to);
      if (refused) return refused;
      if (release(to)!.name === release(model.ada)?.name) return apiError(409, 'E_NO_CHANGE', `${name} runs on ${to} already.`, { ada: to });
      const from = model.ada;
      const list = state.versions.get(name)!;
      const version = Math.max(...list.map((v) => v.version)) + 1;
      state.specs.set(`${name}:${model.version}`, model.spec);
      state.specs.set(`${name}:${version}`, model.spec);
      list.push(
        versionOf({ version, note: note ?? `Upgraded from ${from} to ${to}`, ready: false, reencoded: true, new_store: true, changes: [], precedents_at: model.precedents, store: { status: 'making', drop_after: null }, ada: to, kernel: release(to)!.kernel }),
      );
      const job = addJob(name, 'reencode', { version, spec: model.spec, ada: to });
      return HttpResponse.json({ version, active: false, job, ada: to, from });
    }),
    http.delete(ada('/models/:name'), ({ params }) => {
      state.models = state.models.filter((m) => m.name !== params.name);
      return HttpResponse.json({ name: params.name, deleted: true });
    }),
    http.get(ada('/models/:name/stats'), ({ params }) => {
      const model = found(String(params.name));
      return model ? HttpResponse.json(stats(model)) : missing(String(params.name));
    }),
    http.get(ada('/models/:name/map'), ({ request }) => HttpResponse.json(map(new URL(request.url).searchParams.get('layer')))),
    http.get(ada('/models/:name/precedents/:id'), ({ params }) =>
      HttpResponse.json({
        id: params.id,
        situation: { ticket: { about: { subject: [['refund', 1], ['twice', 0.4]], product: 'web' } } },
        outcome: 'billing',
        outcomes: {},
        author: 'u-chris',
        ts: 1_792_400_000,
      }),
    ),
    http.get(ada('/models/:name/versions'), ({ params }) => HttpResponse.json({ versions: state.versions.get(String(params.name)) ?? [] })),
    http.get(ada('/models/:name/versions/:version'), ({ params }) => {
      const name = String(params.name);
      const entry = state.versions.get(name)?.find((v) => v.version === Number(params.version));
      if (!entry) return apiError(404, 'E_VERSION_MISSING', `This model has no version ${String(params.version)}.`);
      const spec = specOf(name, entry.version);
      return HttpResponse.json({ ...entry, spec, settings: { ...levers, ...spec.settings } });
    }),
    http.get(ada('/models/:name/versions/:version/diff'), ({ params }) => {
      const name = String(params.name);
      const live = found(name)!.version;
      return HttpResponse.json({ version: Number(params.version), against: live, changes: diffOf(specOf(name, live), specOf(name, Number(params.version))) });
    }),
    http.patch(ada('/models/:name/versions/:version'), async ({ params, request }) => {
      const { note } = (await request.json()) as { note: string };
      state.versions.get(String(params.name))!.find((v) => v.version === Number(params.version))!.note = note;
      return HttpResponse.json({ version: Number(params.version), note });
    }),
    http.post(ada('/models/:name/versions/:version/activate'), ({ params }) => {
      const name = String(params.name);
      const version = Number(params.version);
      const list = state.versions.get(name)!;
      const entry = list.find((v) => v.version === version)!;
      if (entry.gone) return apiError(410, 'E_VERSION_GONE', `Version ${version}'s store was dropped after 7 days.`);
      const spec = specOf(name, version);
      // A version whose cases are stored apart is brought up to date by a job, then live.
      if (entry.store.status === 'kept') return HttpResponse.json({ version, active: false, job: addJob(name, 'reencode', { version, spec }) });
      state.specs.set(`${name}:${found(name)!.version}`, found(name)!.spec);
      for (const v of list) v.active = v.version === version;
      Object.assign(found(name)!, { version, spec, ada: entry.ada });
      return HttpResponse.json({ version, active: true, job: null });
    }),
    http.put(ada('/models/:name/spec'), async ({ params, request }) => {
      const name = String(params.name);
      const { spec, note } = (await request.json()) as { spec: Spec; note?: string };
      // A role added rewrites the cases: a re-encode job, then live.
      const reencode = JSON.stringify(spec.layers) !== JSON.stringify(found(name)!.spec.layers);
      const version = newVersion(name, !reencode, note ?? '', spec);
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
      const spec = { ...model.spec, settings: { ...model.spec.settings, ...changes } };
      const version = newVersion(name, true, note ?? '', spec);
      model.spec = spec;
      return HttpResponse.json({ version, active: true, job: null });
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
    http.post(ada('/models/:name/backtest'), async ({ params, request }) => {
      const name = String(params.name);
      const { ada: on } = (await request.json()) as { ada?: string };
      if (!on) return HttpResponse.json(addJob(name, 'backtest', backtestResult), { status: 202 });
      // The live spec on another Ada, against the live version on its own.
      const refused = release(on) ? null : refuseAda(on);
      if (refused) return refused;
      const result = { ...adaBacktest, active: { ...adaBacktest.active, ada: found(name)!.ada }, candidates: [{ ...adaBacktest.candidates[0]!, candidate: { ada: on }, ada: on }] };
      return HttpResponse.json(addJob(name, 'backtest', result), { status: 202 });
    }),
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
          const made = list.find((v) => v.version === version)!;
          Object.assign(made, { ready: true, store: { status: 'active', drop_after: null } });
          Object.assign(found(held.job.model)!, { version, spec, ada: made.ada });
        }
      } else if (held.job.state !== 'awaiting') {
        held.job = { ...held.job, state: 'running', percent: 40 };
      }
      return HttpResponse.json(held.job);
    }),
    http.get(ada('/keys'), () => HttpResponse.json(state.keys)),
    http.post(ada('/keys'), async ({ request }) => {
      const body = (await request.json()) as { name: string; clearance: number; expires_in_days?: number };
      const key: CloudKey = { id: `key-${next++}`, name: body.name, clearance: body.clearance, created_at: at, expires_at: body.expires_in_days ? new Date(Date.now() + body.expires_in_days * 86_400_000).toISOString() : null, revoked_at: null };
      state.keys.push(key);
      return HttpResponse.json({ ...key, key: 'glyphh_ak_secret123' }, { status: 201 });
    }),
    http.delete(ada('/keys/:id/forever'), ({ params }) => {
      const key = state.keys.find((k) => k.id === params.id);
      if (!key) return HttpResponse.json({ error: { code: 'E_NOT_FOUND', message: 'You have no such API key.' } }, { status: 404 });
      if (!key.revoked_at && (key.expires_at === null || new Date(key.expires_at) > new Date()))
        return HttpResponse.json({ error: { code: 'E_CONFLICT', message: 'This API key still works. Revoke it before you delete it.' } }, { status: 409 });
      state.keys = state.keys.filter((k) => k.id !== params.id);
      return new HttpResponse(null, { status: 204 });
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
export const tickets = (): AdaModel => ({ name: 'tickets', id: 'm-tickets', version: 2, precedents: 1_240, created_at: '2026-10-01T09:00:00Z', spec: ticketSpec, ada: 'ada-1-0' });
