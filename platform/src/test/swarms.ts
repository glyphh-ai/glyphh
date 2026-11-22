import { http, HttpResponse } from 'msw';
import type { BotRun } from '@/api/bots';
import type { GitHubKey, NewSwarm, Swarm, SwarmRun, SwarmTurn } from '@/api/swarms';
import { apiError } from './server';

/**
 * Swarms as the server answers them (/v1/swarms, /v1/swarm-runs, /v1/github-key, and their pull requests in
 * /v1/bot-approvals beside the bots' runs), held in state. A run starts with its first bot's turn working; the next
 * read of it finds the turn's pull request open, waiting for the person (review each_turn); merged, the next bot's
 * turn opens one; rejected or merged at the last, the run is done.
 */
const v1 = (path: string) => `*/api/v1${path}`;
const at = '2026-11-21T10:00:00Z';
const REPO = 'https://github.com/acme/site';

export const crew = [
  { id: 'b-inbox', slug: 'inbox-helper', name: 'Inbox helper' },
  { id: 'b-digest', slug: 'digest', name: 'Digest' },
];

export const siteCrew = (given: Partial<Swarm> = {}): Swarm => ({
  id: 's-site',
  slug: 'site-crew',
  name: 'Site crew',
  repo_url: REPO,
  base_branch: 'main',
  members: crew,
  rounds: 1,
  review: 'each_turn',
  runs_on: 'rr-studio',
  created_at: at,
  updated_at: at,
  ...given,
});

export const turn = (n: number, given: Partial<SwarmTurn> = {}): SwarmTurn => {
  const bot = crew[(n - 1) % crew.length]!;
  return {
    n,
    round: 1,
    bot_id: bot.id,
    bot_slug: bot.slug,
    bot_name: bot.name,
    branch: `turn-${n}-${bot.slug}-k3x9`,
    status: 'open',
    said: n === 1 ? 'I made the home page with a hero and the three plans. Next: tests for the plan cards.' : 'Added tests for the plan cards; they pass.\nDONE',
    title: n === 1 ? `${bot.name}: I made the home page with a hero and the three plans.` : `${bot.name}: Added tests for the plan cards`,
    pr_url: `${REPO}/pull/${40 + n}`,
    number: 40 + n,
    head_sha: 'a1b2c3d',
    files:
      n === 1
        ? [
            { path: 'src/pages/Home.tsx', added: 84, removed: 3 },
            { path: 'src/styles/home.css', added: 41, removed: 0 },
          ]
        : [{ path: 'src/pages/Home.test.tsx', added: 36, removed: 0 }],
    done: n > 1,
    error: '',
    created_at: at,
    finished_at: null,
    ...given,
  };
};

export const swarmRun = (given: Partial<SwarmRun> = {}): SwarmRun => ({
  id: 'sr-1',
  swarm_slug: 'site-crew',
  task: 'Make the home page: a hero and the three plans.',
  status: 'needs_input',
  rounds: 1,
  review: 'each_turn',
  runs_on: 'rr-studio',
  error: '',
  turns: [turn(1)],
  created_at: at,
  finished_at: null,
  ...given,
});

/** A swarm run's open pull request as the approvals queue lists it. */
export const asked = (run: SwarmRun): BotRun | null => {
  const t = run.turns.find((x) => x.status === 'open');
  if (run.status !== 'needs_input' || !t) return null;
  return {
    id: run.id,
    bot_slug: t.bot_slug,
    status: 'needs_input',
    input: run.task,
    output: '',
    error: '',
    log: [],
    data: { pr_url: t.pr_url, number: t.number, title: t.title, said: t.said, files: t.files, branch: t.branch, n: t.n, round: t.round },
    question: { question: `Merge PR #${t.number} by ${t.bot_name}?`, options: ['merge', 'reject'], batch: null, answer_with: null },
    input_tokens: 0,
    output_tokens: 0,
    cost_micros: 0,
    own_key: true,
    runs_on: run.runs_on,
    kind: 'swarm',
    swarm_slug: run.swarm_slug,
    created_at: t.created_at,
    started_at: run.created_at,
    finished_at: null,
  };
};

type Options = { swarms?: Swarm[]; runs?: SwarmRun[]; key?: GitHubKey; botRuns?: () => BotRun[] };

export function swarmsFake({ swarms = [siteCrew()], runs = [], key = { set: true, hint: 'x9Qz', login: 'acme-bot', set_at: at }, botRuns = () => [] }: Options = {}) {
  const state = { swarms: structuredClone(swarms), runs: structuredClone(runs), key: { ...key }, seen: [] as string[], bodies: [] as unknown[], reads: new Map<string, number>() };
  let next = 1;
  const find = (slug: unknown) => state.swarms.find((s) => s.slug === slug);
  const run = (id: unknown) => state.runs.find((r) => r.id === id);
  const missing = () => apiError(404, 'E_NOT_FOUND', 'There is no such swarm.');
  const noRun = () => apiError(404, 'E_NOT_FOUND', 'There is no such swarm run.');
  const members = (ids: string[]) => ids.map((id) => crew.find((c) => c.id === id) ?? { id, slug: id, name: id });
  const live = (s: Swarm) => state.runs.some((r) => r.swarm_slug === s.slug && (r.status === 'running' || r.status === 'needs_input'));

  const handlers = [
    http.get(v1('/swarms'), () => HttpResponse.json({ swarms: state.swarms })),
    http.post(v1('/swarms'), async ({ request }) => {
      const body = (await request.json()) as NewSwarm;
      state.bodies.push(body);
      const slug = body.name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
      if (find(slug)) return apiError(409, 'E_CONFLICT', `The org already has a swarm '${slug}': name it another way.`);
      const made = siteCrew({ ...body, id: `s-${next++}`, slug, members: members(body.members) });
      state.swarms.push(made);
      state.seen.push(`create ${slug}`);
      return HttpResponse.json(made, { status: 201 });
    }),
    http.get(v1('/swarms/:slug'), ({ params }) => (find(params.slug) ? HttpResponse.json(find(params.slug)) : missing())),
    http.patch(v1('/swarms/:slug'), async ({ params, request }) => {
      const s = find(params.slug);
      if (!s) return missing();
      const change = (await request.json()) as Partial<NewSwarm>;
      state.bodies.push(change);
      Object.assign(s, change, change.members ? { members: members(change.members) } : {}, { updated_at: new Date(Date.parse(at) + next++ * 1000).toISOString() });
      state.seen.push(`update ${params.slug}`);
      return HttpResponse.json(s);
    }),
    http.delete(v1('/swarms/:slug'), ({ params }) => {
      state.swarms = state.swarms.filter((s) => s.slug !== params.slug);
      state.seen.push(`delete ${params.slug}`);
      return new HttpResponse(null, { status: 204 });
    }),
    http.get(v1('/swarms/:slug/runs'), ({ params }) => HttpResponse.json({ runs: state.runs.filter((r) => r.swarm_slug === params.slug) })),
    http.post(v1('/swarms/:slug/runs'), async ({ params, request }) => {
      const s = find(params.slug);
      if (!s) return missing();
      if (!state.key.set) return apiError(404, 'E_NOT_FOUND', 'Save the org’s GitHub token first.', { reason: 'github_key' });
      if (live(s)) return apiError(409, 'E_CONFLICT', 'The swarm has a run going: answer its pull request, or cancel it, first.');
      const { task } = (await request.json()) as { task: string };
      const made = swarmRun({ id: `sr-${next++}`, swarm_slug: s.slug, task, status: 'running', review: s.review, turns: [turn(1, { status: 'running', said: '', pr_url: null, number: null, files: [] })] });
      state.runs.unshift(made);
      state.seen.push(`run ${s.slug}`);
      return HttpResponse.json(made, { status: 202 });
    }),
    http.get(v1('/swarm-runs/:id'), ({ params }) => {
      const r = run(params.id);
      if (!r) return noRun();
      const reads = (state.reads.get(r.id) ?? 0) + 1;
      state.reads.set(r.id, reads);
      const out = r.turns.at(-1);
      if (reads >= 2 && r.status === 'running' && out?.status === 'running') {
        Object.assign(out, turn(out.n));
        r.status = 'needs_input';
      }
      return HttpResponse.json(r);
    }),
    http.post(v1('/swarm-runs/:id/answer'), async ({ params, request }) => {
      const r = run(params.id);
      if (!r) return noRun();
      const open = r.turns.find((t) => t.status === 'open');
      if (r.status !== 'needs_input' || !open) return apiError(409, 'E_CONFLICT', 'That swarm run is not waiting on a pull request.');
      const { answer } = (await request.json()) as { answer: 'merge' | 'reject' };
      state.bodies.push(answer);
      open.status = answer === 'merge' ? 'merged' : 'rejected';
      open.finished_at = at;
      if (r.turns.length < crew.length) {
        r.turns.push(turn(r.turns.length + 1));
      } else {
        Object.assign(r, { status: 'done', finished_at: at });
      }
      state.seen.push(`${answer} ${r.id}`);
      return HttpResponse.json(r, { status: 202 });
    }),
    http.post(v1('/swarm-runs/:id/cancel'), ({ params }) => {
      const r = run(params.id);
      if (!r) return noRun();
      for (const t of r.turns) if (t.status === 'running') t.status = 'cancelled';
      Object.assign(r, { status: 'failed', error: 'cancelled', finished_at: at });
      state.seen.push(`cancel ${r.id}`);
      return HttpResponse.json(r);
    }),
    http.get(v1('/bot-approvals'), () =>
      HttpResponse.json({ runs: [...botRuns().filter((r) => r.status === 'needs_input'), ...state.runs.map(asked).filter((r): r is BotRun => r !== null)] }),
    ),
    http.get(v1('/github-key'), () => HttpResponse.json(state.key)),
    http.put(v1('/github-key'), async ({ request }) => {
      const { token } = (await request.json()) as { token: string };
      if (token.endsWith('bad')) return apiError(422, 'E_INVALID', 'GitHub does not take that token.', { reason: 'token' });
      state.key = { set: true, hint: token.slice(-4), login: 'acme-bot', set_at: at };
      state.seen.push('github key');
      return HttpResponse.json(state.key);
    }),
    http.delete(v1('/github-key'), () => {
      state.key = { set: false, hint: '', login: '', set_at: null };
      state.seen.push('github key removed');
      return HttpResponse.json(state.key);
    }),
  ];
  return { state, handlers };
}
