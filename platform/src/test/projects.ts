import { http, HttpResponse } from 'msw';
import type { BotRun } from '@/api/bots';
import type { GitHubRepo } from '@/api/github';
import type { CrewSet, Project, ProjectRun, RunStart, Turn } from '@/api/projects';
import type { Recent } from '@/api/recents';
import { apiError } from './server';

/**
 * The crew as the server answers it, held in state: its record per workspace (/v1/projects, got or made with
 * `PUT /v1/projects/crew`), its runs (/v1/project-runs), the person's GitHub App installation, its repos and their
 * branches (/v1/github), and Recents (/v1/recents) over the crew's runs and the bots' own. A run starts with its first
 * turn out (working, or being picked by the orchestrator); the next read of it finds the turn's pull request open,
 * waiting for the person (review each_turn); merged or rejected, the next bot's turn opens one; after the last the run
 * is done. With review `end` a run that waits with no open turn waits on its own pull request of it all.
 */
const v1 = (path: string) => `*/api/v1${path}`;
const at = '2026-11-21T10:00:00Z';
const REPO = 'https://github.com/acme/site';

/** GitHub's install page for the App, as the server's link leads to it; and the installation's own page. */
export const INSTALL_URL = 'https://api.glyphh.test/v1/github/install?link=signed';
export const MANAGE_URL = 'https://github.com/settings/installations/4242';
export const repos: GitHubRepo[] = [
  { full_name: 'acme/site', url: REPO, private: false, default_branch: 'main' },
  { full_name: 'acme/docs', url: 'https://github.com/acme/docs', private: true, default_branch: 'trunk' },
  { full_name: 'acme/api', url: 'https://github.com/acme/api', private: true, default_branch: 'main' },
];
/** The person's installation of the App: the account it is on and the repos it covers. */
export type Installation = { login: string; repos: GitHubRepo[] };
export const acme = (): Installation => ({ login: 'acme', repos: structuredClone(repos) });

export const crew = [
  { id: 'b-inbox', slug: 'inbox-helper', name: 'Inbox helper' },
  { id: 'b-digest', slug: 'digest', name: 'Digest' },
];

export const siteCrew = (given: Partial<Project> = {}): Project => ({
  id: 'p-site',
  slug: 'acme-site-main',
  name: 'acme/site',
  repo_url: REPO,
  github_connected: true,
  base_branch: 'main',
  members: crew,
  instructions: '',
  instructions_path: 'PROJECT.md',
  turn_mode: 'wait',
  review: 'each_turn',
  runs_on: 'rr-studio',
  max_turns: 30,
  max_spend_cents: null,
  narrate: false,
  created_at: at,
  updated_at: at,
  ...given,
});

export const turn = (n: number, given: Partial<Turn> = {}): Turn => {
  const bot = crew[(n - 1) % crew.length]!;
  return {
    n,
    bot_id: bot.id,
    bot_slug: bot.slug,
    bot_name: bot.name,
    branch: `turn-${n}-${bot.slug}-k3x9`,
    status: 'open',
    picked_by: 'wait',
    why: '',
    said: n === 1 ? 'I made the home page with a hero and the three plans. Next: tests for the plan cards.' : 'Added tests for the plan cards; they pass.',
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
    input_tokens: 12_400,
    output_tokens: 1_800,
    cost_micros: 64_000,
    created_at: at,
    finished_at: null,
    ...given,
  };
};

/** A turn still out: nothing said, no pull request yet. */
const out = (n: number, given: Partial<Turn> = {}): Turn =>
  turn(n, { status: 'running', said: '', title: '', pr_url: null, number: null, head_sha: null, files: [], done: false, input_tokens: 0, output_tokens: 0, cost_micros: 0, ...given });

/** The orchestrator choosing who goes next: no bot yet. */
export const picking = (n: number): Turn => out(n, { status: 'picking', bot_id: null, bot_slug: '', bot_name: '', branch: '', picked_by: 'orchestrator' });

/** The orchestrator's own closing turn: it says the work is done, and why. */
export const closing = (n: number, said: string): Turn =>
  out(n, { status: 'unchanged', bot_id: null, bot_slug: '', bot_name: 'Orchestrator', branch: '', picked_by: 'orchestrator', said, done: true, finished_at: at });

export const projectRun = (given: Partial<ProjectRun> = {}): ProjectRun => ({
  id: 'pr-1',
  project_slug: 'acme-site-main',
  task: 'Make the home page: a hero and the three plans.',
  status: 'needs_input',
  ended: '',
  turn_mode: 'wait',
  review: 'each_turn',
  runs_on: 'rr-studio',
  model: null,
  effort: null,
  max_turns: 30,
  max_spend_cents: null,
  work_branch: null,
  pr_url: null,
  number: null,
  error: '',
  turns: [turn(1)],
  input_tokens: 12_400,
  output_tokens: 1_800,
  cost_micros: 64_000,
  created_at: at,
  finished_at: null,
  ...given,
});

type Options = {
  projects?: Project[];
  runs?: ProjectRun[];
  /** The person's installation of the Glyphh GitHub App; null: they have not connected GitHub. */
  github?: Installation | null;
  /** The org's rrotors that are offline: a run on one is refused (409 rrotor_offline). */
  offline?: string[];
  /** The bots' own runs, for Recents (the bots' fake holds them). */
  botRuns?: () => BotRun[];
  /** The bots' names by slug, for Recents. */
  botNames?: Record<string, string>;
  /** Runs the person has pinned or archived, by id. */
  pinned?: string[];
  archived?: string[];
};

export function crewFake({ projects = [siteCrew()], runs = [], github = acme(), offline = ['rr-acme'], botRuns = () => [], botNames = {}, pinned = [], archived = [] }: Options = {}) {
  const state = {
    projects: structuredClone(projects),
    runs: structuredClone(runs),
    github: github as Installation | null,
    pinned: new Set(pinned),
    archived: new Set(archived),
    deleted: new Set<string>(),
    seen: [] as string[],
    bodies: [] as unknown[],
    reads: new Map<string, number>(),
  };
  let next = 1;
  const appMissing = (repo: string) =>
    apiError(404, 'E_NOT_FOUND', `Glyphh’s GitHub App is not installed on ${repo}.`, { reason: 'github_app_missing', install_url: INSTALL_URL });
  const find = (slug: unknown) => state.projects.find((p) => p.slug === slug);
  const run = (id: unknown) => state.runs.find((r) => r.id === id);
  const missing = () => apiError(404, 'E_NOT_FOUND', 'There is no such workspace.');
  const noRun = () => apiError(404, 'E_NOT_FOUND', 'There is no such run.');
  const members = (ids: string[]) => ids.map((id) => crew.find((c) => c.id === id) ?? { id, slug: id.replace(/^b-/, ''), name: botNames[id.replace(/^b-/, '')] ?? id });
  const live = (p: Project) => state.runs.some((r) => r.project_slug === p.slug && (r.status === 'running' || r.status === 'needs_input'));
  const short = (repo: string) => repo.replace(/^https:\/\/github\.com\//, '');

  const recents = (): Recent[] => {
    const flags = (id: string) => ({ pinned: state.pinned.has(id), archived: state.archived.has(id) });
    const fromBots = botRuns().map(
      (r): Recent => ({
        id: r.id,
        kind: 'bot',
        title: r.input.split('\n')[0] ?? '',
        bot_slug: r.bot_slug,
        bot_name: botNames[r.bot_slug] ?? 'Inbox helper',
        project_slug: null,
        workspace: null,
        branch: null,
        runs_on: r.runs_on ?? null,
        status: r.status,
        waiting: r.status === 'needs_input',
        created_at: r.created_at,
        ...flags(r.id),
      }),
    );
    const fromCrew = state.runs.map((r): Recent => {
      const p = find(r.project_slug);
      return {
        id: r.id,
        kind: 'crew',
        title: r.task.split('\n')[0] ?? '',
        bot_slug: null,
        bot_name: 'Crew',
        project_slug: r.project_slug,
        workspace: p ? short(p.repo_url) : null,
        branch: p?.base_branch ?? null,
        runs_on: r.runs_on,
        status: r.status,
        waiting: r.status === 'needs_input',
        created_at: r.created_at,
        ...flags(r.id),
      };
    });
    return [...fromBots, ...fromCrew].filter((r) => !state.deleted.has(r.id)).sort((a, b) => b.created_at.localeCompare(a.created_at));
  };
  const flag = (set: Set<string>, on: boolean, word: string) =>
    http.post(v1(`/recents/:id/${word}`), ({ params }) => {
      const id = String(params.id);
      const found = recents().find((r) => r.id === id);
      if (!found) return noRun();
      on ? set.add(id) : set.delete(id);
      state.seen.push(`${word} ${id}`);
      return HttpResponse.json(recents().find((r) => r.id === id));
    });

  const handlers = [
    http.get(v1('/projects'), () => HttpResponse.json({ projects: state.projects })),
    // One per (repo, branch): got or made, and set to what is given.
    http.put(v1('/projects/crew'), async ({ request }) => {
      const body = (await request.json()) as CrewSet;
      state.bodies.push(body);
      const repo = short(body.repo);
      const branch = body.branch ?? 'main';
      if (!state.github) return appMissing(repo);
      if (!state.github.repos.some((r) => r.full_name === repo) && !repo.startsWith('acme-org/')) return appMissing(repo);
      const { repo: _repo, branch: _branch, members: ids, ...settings } = body;
      const found = state.projects.find((p) => short(p.repo_url) === repo && p.base_branch === branch);
      const stamp = new Date(Date.parse(at) + next++ * 1000).toISOString();
      if (found) {
        Object.assign(found, settings, { members: members(ids), updated_at: stamp });
        state.seen.push(`crew ${found.slug}`);
        return HttpResponse.json(found);
      }
      const made = siteCrew({
        runs_on: null,
        ...settings,
        id: `p-${next++}`,
        slug: `${repo}-${branch}`.toLowerCase().replace(/[^a-z0-9]+/g, '-'),
        name: repo,
        repo_url: `https://github.com/${repo}`,
        base_branch: branch,
        members: members(ids),
        updated_at: stamp,
      });
      state.projects.push(made);
      state.seen.push(`crew ${made.slug}`);
      return HttpResponse.json(made);
    }),
    http.get(v1('/projects/:slug/runs'), ({ params }) => HttpResponse.json({ runs: state.runs.filter((r) => r.project_slug === params.slug && !state.deleted.has(r.id)) })),
    http.post(v1('/projects/:slug/runs'), async ({ params, request }) => {
      const p = find(params.slug);
      if (!p) return missing();
      if (live(p)) return apiError(409, 'E_CONFLICT', 'The crew has a run going here: answer its pull request, or cancel it, first.');
      if (p.runs_on && offline.includes(p.runs_on)) return apiError(409, 'E_CONFLICT', 'Its rrotor is offline: start it, or choose another place.', { reason: 'rrotor_offline' });
      const body = (await request.json()) as RunStart;
      state.bodies.push(body);
      const made = projectRun({
        id: `pr-${next++}`,
        project_slug: p.slug,
        task: body.task,
        model: body.model,
        effort: body.effort,
        status: 'running',
        turn_mode: p.turn_mode,
        review: p.review,
        runs_on: p.runs_on,
        max_turns: p.max_turns,
        max_spend_cents: p.max_spend_cents,
        turns: [p.turn_mode === 'orchestrator' ? picking(1) : out(1)],
        input_tokens: 0,
        output_tokens: 0,
        cost_micros: 0,
      });
      state.runs.unshift(made);
      state.seen.push(`run ${p.slug}`);
      return HttpResponse.json(made, { status: 202 });
    }),
    http.get(v1('/project-runs/:id'), ({ params }) => {
      const r = run(params.id);
      if (!r) return noRun();
      const reads = (state.reads.get(r.id) ?? 0) + 1;
      state.reads.set(r.id, reads);
      const last = r.turns.at(-1);
      if (reads >= 2 && r.status === 'running' && (last?.status === 'running' || last?.status === 'picking')) {
        Object.assign(last, turn(last.n, last.status === 'picking' ? { picked_by: 'orchestrator', why: 'The home page comes first.' } : {}));
        r.status = 'needs_input';
      }
      return HttpResponse.json(r);
    }),
    http.post(v1('/project-runs/:id/answer'), async ({ params, request }) => {
      const r = run(params.id);
      if (!r) return noRun();
      const open = r.turns.find((t) => t.status === 'open');
      const whole = !open && r.review === 'end' && r.pr_url !== null;
      if (r.status !== 'needs_input' || (!open && !whole)) return apiError(409, 'E_CONFLICT', 'That run is not waiting on a pull request.');
      const { answer } = (await request.json()) as { answer: 'merge' | 'reject' };
      state.bodies.push(answer);
      if (open) {
        open.status = answer === 'merge' ? 'merged' : 'rejected';
        open.finished_at = at;
      }
      if (open && r.turns.length < crew.length) {
        r.turns.push(turn(r.turns.length + 1));
      } else {
        Object.assign(r, { status: 'done', ended: 'done', finished_at: at });
      }
      state.seen.push(`${answer} ${r.id}`);
      return HttpResponse.json(r, { status: 202 });
    }),
    http.post(v1('/project-runs/:id/cancel'), ({ params }) => {
      const r = run(params.id);
      if (!r) return noRun();
      for (const t of r.turns) if (t.status === 'running' || t.status === 'picking') t.status = 'cancelled';
      Object.assign(r, { status: 'failed', error: 'cancelled', finished_at: at });
      state.seen.push(`cancel ${r.id}`);
      return HttpResponse.json(r);
    }),

    http.post(v1('/github/install'), () => {
      state.seen.push('install link');
      return HttpResponse.json({ url: INSTALL_URL });
    }),
    http.get(v1('/github/repos'), () =>
      HttpResponse.json(state.github ? { account_login: state.github.login, manage_url: MANAGE_URL, repos: state.github.repos } : { account_login: '', manage_url: '', repos: [] }),
    ),
    http.get(v1('/github/repos/:owner/:repo/branches'), ({ params }) => {
      const name = `${String(params.owner)}/${String(params.repo)}`;
      const found = state.github?.repos.find((r) => r.full_name === name);
      if (!found) return appMissing(name);
      return HttpResponse.json({ default_branch: found.default_branch, branches: [...new Set([found.default_branch, 'dev', 'release'])] });
    }),

    http.get(v1('/recents'), ({ request }) => {
      const q = new URL(request.url).searchParams;
      const words = (q.get('q') ?? '').toLowerCase();
      const all = recents();
      const found = all
        .filter((r) => (q.get('archived') ? r.archived : !r.archived))
        .filter((r) => !q.get('waiting') || r.waiting)
        .filter((r) => !q.get('pinned') || r.pinned)
        .filter((r) => !words || `${r.title} ${r.bot_name} ${r.workspace ?? ''}`.toLowerCase().includes(words));
      // A page by its cursor: here, how many rows came before it.
      const from = Number(q.get('cursor') ?? 0);
      const limit = Number(q.get('limit') ?? 30);
      const shown = found.slice(from, from + limit);
      state.seen.push(`recents ${q.toString()}`);
      return HttpResponse.json({
        recents: shown,
        next_cursor: from + limit < found.length ? String(from + limit) : null,
        needs_you: all.filter((r) => r.waiting).length,
        archived_count: all.filter((r) => r.archived).length,
      });
    }),
    flag(state.pinned, true, 'pin'),
    flag(state.pinned, false, 'unpin'),
    flag(state.archived, true, 'archive'),
    flag(state.archived, false, 'unarchive'),
    http.delete(v1('/recents/:id'), ({ params }) => {
      const found = recents().find((r) => r.id === params.id);
      if (!found) return noRun();
      if (found.status === 'running' || found.waiting) return apiError(409, 'E_CONFLICT', 'That run is still going: cancel it first.', { reason: 'run_live' });
      state.deleted.add(found.id);
      state.seen.push(`delete ${found.id}`);
      return new HttpResponse(null, { status: 204 });
    }),
  ];
  return { state, handlers };
}
