import { http, HttpResponse } from 'msw';
import type { FoundTool, Program, ProgramEvent, ProgramRun, Step } from '@/api/programs';
import { apiError } from './server';

/**
 * Programs as the server answers them (docs/specs/programs.md, section 6): /v1/programs, /v1/program-runs and
 * /v1/tools/search, held in state so each write shows on the next read. Saving `flow` rewrites the file's FLOW line;
 * saving `source` reads FLOW back out of it. A run walks its steps one per read of it: a tool or bot step is done, an
 * ask step waits on the person until answered, and the run ends where `next` is none.
 */
const v1 = (path: string) => `*/api/v1${path}`;
const at = '2026-11-23T09:00:00Z';

/** The spec's example, PR review digest, with the inbox helper as its bot. */
export const digestFlow = (): Step[] => [
  { id: 'find', kind: 'tool', tool: 'github-search-issues-and-pull-requests', input: { q: 'is:pr is:open review-requested:@me' }, next: 'pick', at: [0, 0] },
  { id: 'pick', kind: 'bot', bot: 'digest', task: 'Which of these need my review today?\n\n{find}', next: 'ok', at: [0, 160] },
  { id: 'ok', kind: 'ask', question: 'Post the digest?', options: ['yes', 'no'], next: { yes: 'post', no: null }, at: [0, 320] },
  { id: 'post', kind: 'tool', title: 'Post to Slack', tool: 'slack-send-message', input: { channel: '@me', text: '{pick}' }, at: [0, 480] },
];

const DOC = '"""PR review digest: the pull requests waiting on my review, the ones for today posted to Slack."""';
/** `program.py` with its FLOW as a literal (JSON with Python's None). */
export const sourceOf = (flow: Step[], doc = DOC) => `${doc}\n\nFLOW = ${JSON.stringify(flow).replace(/null/g, 'None')}\n\n\ndef tidy(given):\n    return given\n`;
const flowOf = (source: string): Step[] | null => {
  const m = /^FLOW = (.*)$/m.exec(source);
  if (!m) return null;
  try {
    return JSON.parse(m[1]!.replace(/None/g, 'null')) as Step[];
  } catch {
    return null;
  }
};

export const program = (given: Partial<Program> = {}): Program => {
  const flow = given.flow ?? digestFlow();
  return {
    slug: 'pr-digest',
    name: 'PR review digest',
    summary: 'The pull requests waiting on my review, posted to Slack.',
    bot: 'inbox-helper',
    source: sourceOf(flow),
    flow,
    functions: ['tidy'],
    problems: [],
    runs_on: null,
    can_run_on: ['cloud', 'rrotor'],
    schedule: { every: 'off', at: '09:00', weekday: 0, day: 1, timezone: 'UTC', input: '' },
    schedule_summary: 'Off',
    next_run_at: null,
    last_run: null,
    template: null,
    created_at: at,
    updated_at: at,
    ...given,
  };
};

export const tools = (): FoundTool[] => [
  { key: 'github-search-issues-and-pull-requests', title: 'Search issues and pull requests', app: 'GitHub', description: 'Finds issues and pull requests.', read_only: true, connection_id: 'c-github', added: true },
  { key: 'slack-send-message', title: 'Send message', app: 'Slack', description: 'Posts in a channel.', read_only: false, connection_id: 'c-slack', added: true },
  { key: 'gmail-find-email', title: 'Find email', app: 'Gmail', description: 'Finds emails that match a search.', read_only: true, connection_id: 'c-gmail', added: false },
  { key: 'fetch', title: 'Read a web page', app: 'Built in', description: 'Reads a page from the web.', read_only: true, connection_id: null, added: true },
];

/** Plain problems as the server would find them: a step that is not there, code on Glyphh cloud. */
function problemsIn(flow: Step[], runsOn: string | null): string[] {
  const ids = new Set(flow.map((s) => s.id));
  const out: string[] = [];
  for (const s of flow) {
    const targets = typeof s.next === 'string' ? [s.next] : s.next && typeof s.next === 'object' ? Object.values(s.next) : [];
    for (const t of targets) if (t !== null && !ids.has(t)) out.push(`Step ${s.id} goes to ${t}, which is not there.`);
    if (s.kind === 'code' && runsOn === null) out.push(`Step ${s.id} runs code, which needs a rrotor.`);
  }
  return out;
}

type Options = { programs?: Program[]; runs?: ProgramRun[]; events?: Record<string, ProgramEvent[]>; tools?: FoundTool[]; me?: string };

export function programsFake({ programs = [program()], runs = [], events = {}, tools: found = tools(), me = 'chris@example.com' }: Options = {}) {
  const state = {
    programs: structuredClone(programs),
    runs: structuredClone(runs),
    events: structuredClone(events) as Record<string, ProgramEvent[]>,
    tools: structuredClone(found),
    bodies: [] as { method: string; path: string; body: unknown }[],
    /** The `after` of each events read, in order. */
    afters: [] as number[],
    added: [] as unknown[],
  };
  let next = 1;
  const find = (slug: unknown) => state.programs.find((p) => p.slug === slug);
  const run = (id: unknown) => state.runs.find((r) => r.id === id);
  const missing = () => apiError(404, 'E_NOT_FOUND', 'There is no such program.');
  const noRun = () => apiError(404, 'E_NOT_FOUND', 'There is no such run.');
  const stamp = () => new Date(Date.parse(at) + next++ * 1000).toISOString();
  const log = (id: string, e: Omit<ProgramEvent, 'n' | 'at'>) => {
    const list = (state.events[id] ??= []);
    list.push({ n: list.length + 1, at: stamp(), ...e });
  };
  const blank = { step: null, title: null, bot: null, ok: null, detail: null, by: null };
  const saved = (p: Program) => {
    p.problems = problemsIn(p.flow, p.runs_on);
    p.updated_at = stamp();
    return p;
  };

  /** One step further: what a read of a going run sees. */
  const walk = (r: ProgramRun) => {
    const p = find(r.program);
    if (!p || (r.status !== 'queued' && r.status !== 'running')) return;
    if (r.status === 'queued') {
      r.status = 'running';
      r.started_at = stamp();
      r.at = p.flow[0]?.id ?? null;
      return;
    }
    const step = p.flow.find((s) => s.id === r.at);
    if (!step) {
      r.status = 'done';
      r.finished_at = stamp();
      log(r.id, { ...blank, kind: 'done' });
      return;
    }
    if (step.kind === 'ask') {
      r.status = 'needs_input';
      r.question = { question: step.question ?? '', options: step.options ?? [], step: step.id };
      log(r.id, { ...blank, kind: 'asked', step: step.id, title: step.title ?? step.question ?? step.id, detail: step.question ?? null });
      return;
    }
    r.outputs[step.id] = `${step.id} done`;
    log(r.id, { ...blank, kind: 'step', step: step.id, title: step.title ?? step.id, bot: step.bot ?? p.bot, ok: true, detail: step.kind === 'tool' ? 'Found 3' : 'Answered' });
    const to = typeof step.next === 'string' ? step.next : null;
    if (to) r.at = to;
    else {
      r.status = 'done';
      r.finished_at = stamp();
      log(r.id, { ...blank, kind: 'done' });
    }
  };

  const handlers = [
    http.get(v1('/programs'), ({ request }) => {
      const q = (new URL(request.url).searchParams.get('q') ?? '').toLowerCase();
      return HttpResponse.json({ programs: state.programs.filter((p) => !q || `${p.name} ${p.summary ?? ''}`.toLowerCase().includes(q)) });
    }),
    http.post(v1('/programs'), async ({ request }) => {
      const body = (await request.json()) as Partial<Program> & { name: string };
      state.bodies.push({ method: 'POST', path: '/programs', body });
      const slug = body.name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
      if (find(slug)) return apiError(409, 'E_CONFLICT', 'A program has that name.');
      const flow = body.flow ?? (body.source ? (flowOf(body.source) ?? []) : []);
      const made = saved(program({ slug, name: body.name, summary: body.summary ?? null, bot: body.bot ?? null, flow, source: body.source ?? sourceOf(flow, `"""${body.name}."""`), runs_on: body.runs_on ?? null }));
      state.programs.push(made);
      return HttpResponse.json(made, { status: 201 });
    }),
    http.get(v1('/programs/:slug'), ({ params }) => {
      const p = find(params.slug);
      return p ? HttpResponse.json(p) : missing();
    }),
    http.patch(v1('/programs/:slug'), async ({ params, request }) => {
      const p = find(params.slug);
      if (!p) return missing();
      const body = (await request.json()) as Partial<Program>;
      state.bodies.push({ method: 'PATCH', path: `/programs/${p.slug}`, body });
      if (body.flow && body.source) return apiError(422, 'E_INVALID', 'Send the steps or the file, not both.');
      if (body.source !== undefined) {
        const flow = flowOf(body.source);
        if (!flow) return apiError(422, 'E_INVALID', 'The program could not be read.', { problems: ['FLOW is not a list of steps.'] });
        p.source = body.source;
        p.flow = flow;
      }
      if (body.flow) {
        p.flow = body.flow;
        p.source = p.source.replace(/^FLOW = .*$/m, `FLOW = ${JSON.stringify(body.flow).replace(/null/g, 'None')}`);
      }
      for (const k of ['name', 'summary', 'bot', 'runs_on'] as const) if (k in body) (p as Record<string, unknown>)[k] = body[k];
      if (body.schedule) {
        p.schedule = body.schedule;
        p.schedule_summary = body.schedule.every === 'off' ? 'Off' : body.schedule.every === 'weekdays' ? `Weekdays at ${body.schedule.at.replace(/^0/, '')}` : 'On a schedule';
      }
      return HttpResponse.json(saved(p));
    }),
    http.delete(v1('/programs/:slug'), ({ params }) => {
      if (!find(params.slug)) return missing();
      state.programs = state.programs.filter((p) => p.slug !== params.slug);
      return new HttpResponse(null, { status: 204 });
    }),
    http.post(v1('/programs/:slug/runs'), async ({ params, request }) => {
      const p = find(params.slug);
      if (!p) return missing();
      const body = (await request.json()) as { input?: string };
      state.bodies.push({ method: 'POST', path: `/programs/${p.slug}/runs`, body });
      if (state.runs.some((r) => r.program === p.slug && ['queued', 'running', 'dispatched', 'needs_input'].includes(r.status)))
        return apiError(409, 'E_CONFLICT', 'It is running already.');
      const r: ProgramRun = { id: `pr-${next++}`, program: p.slug, status: 'queued', input: body.input ?? '', at: null, outputs: {}, question: null, error: '', trigger: 'person', created_at: stamp(), started_at: null, finished_at: null };
      state.runs.unshift(r);
      log(r.id, { ...blank, kind: 'started', by: me });
      p.last_run = { id: r.id, status: r.status, created_at: r.created_at };
      return HttpResponse.json(r, { status: 202 });
    }),
    http.get(v1('/programs/:slug/runs'), ({ params }) => HttpResponse.json({ runs: state.runs.filter((r) => r.program === params.slug) })),
    http.get(v1('/program-runs/:id'), ({ params }) => {
      const r = run(params.id);
      if (!r) return noRun();
      walk(r);
      return HttpResponse.json(r);
    }),
    http.get(v1('/program-runs/:id/events'), ({ params, request }) => {
      const after = Number(new URL(request.url).searchParams.get('after') ?? '0');
      state.afters.push(after);
      return HttpResponse.json({ events: (state.events[String(params.id)] ?? []).filter((e) => e.n > after) });
    }),
    http.post(v1('/program-runs/:id/answer'), async ({ params, request }) => {
      const r = run(params.id);
      if (!r) return noRun();
      const { answer } = (await request.json()) as { answer: string };
      state.bodies.push({ method: 'POST', path: `/program-runs/${r.id}/answer`, body: { answer } });
      const p = find(r.program);
      const step = p?.flow.find((s) => s.id === r.at);
      log(r.id, { ...blank, kind: 'answered', step: r.at, title: step?.title ?? null, detail: answer, by: me });
      r.outputs[r.at ?? ''] = answer;
      r.question = null;
      const map = step?.next && typeof step.next === 'object' ? step.next : {};
      const to = map[answer] ?? map.else ?? null;
      if (to) {
        r.status = 'running';
        r.at = to;
      } else {
        r.status = 'done';
        r.finished_at = stamp();
        log(r.id, { ...blank, kind: 'done' });
      }
      return HttpResponse.json(r);
    }),
    http.post(v1('/program-runs/:id/cancel'), ({ params }) => {
      const r = run(params.id);
      if (!r) return noRun();
      r.status = 'cancelled';
      r.question = null;
      r.finished_at = stamp();
      log(r.id, { ...blank, kind: 'cancelled', by: me });
      return HttpResponse.json(r);
    }),
    http.get(v1('/tools/search'), ({ request }) => {
      const q = (new URL(request.url).searchParams.get('q') ?? '').toLowerCase();
      return HttpResponse.json({ tools: state.tools.filter((t) => !q || `${t.key} ${t.title} ${t.app}`.toLowerCase().includes(q)) });
    }),
    http.post(v1('/bots/:slug/tools'), async ({ params, request }) => {
      const body = (await request.json()) as { connection_id: string; tool: string };
      state.added.push({ bot: params.slug, ...body });
      state.tools = state.tools.map((t) => (t.key === body.tool ? { ...t, added: true } : t));
      return HttpResponse.json({ ok: true });
    }),
  ];
  return { state, handlers };
}
