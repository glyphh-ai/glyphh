import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { botKeys } from './bots';
import { api } from './client';
import { recentKeys } from './recents';

/**
 * The crew (the server's /v1/projects and /v1/project-runs; "project" is the server's word and is never shown): the
 * org's bots working together in one GitHub repo and branch, the workspace. There is one per workspace, got or made
 * with `PUT /projects/crew`, which also sets who is in it and how it works. The crew is a set: who goes next is the
 * next free bot with something to do (`wait`), or whoever the orchestrator names. A run goes on until the crew or the
 * orchestrator says it is done; `max_turns` and `max_spend_cents` are its safety caps. Each turn is a pull request:
 * with review `each_turn` it waits for a merge or a reject, with `end` one pull request of it all waits at the end.
 */
export type Review = 'each_turn' | 'end';
export type TurnMode = 'wait' | 'orchestrator';
export type Effort = 'low' | 'medium' | 'high';
export type ProjectMember = { id: string; slug: string; name: string };
export type Project = {
  id: string;
  slug: string;
  name: string;
  repo_url: string;
  /** Glyphh's GitHub App reaches the repo. */
  github_connected: boolean;
  base_branch: string;
  /** A set: it has no order. */
  members: ProjectMember[];
  instructions: string;
  instructions_path: string;
  turn_mode: TurnMode;
  /** The crew bot that picks who goes next; none is Claude. */
  orchestrator: string | null;
  review: Review;
  /** The org's rrotor it runs on; none is Glyphh cloud. */
  runs_on: string | null;
  max_turns: number;
  max_spend_cents: number | null;
  /** Read each turn aloud while its chat is open. */
  narrate: boolean;
  created_at: string;
  updated_at: string;
};
/** How the crew works, whichever workspace it is in. */
export type CrewSettings = {
  runs_on: string | null;
  turn_mode: TurnMode;
  orchestrator: string | null;
  review: Review;
  narrate: boolean;
  max_turns: number;
  max_spend_cents: number | null;
};
/** What `PUT /projects/crew` takes: the workspace, the bots' ids, and any settings to change. */
export type CrewSet = { repo: string; branch?: string; members: string[] } & Partial<CrewSettings>;
/**
 * picking (the orchestrator is choosing who goes next), running, open (its pull request waits), unchanged (no
 * changes), merging, merged, conflict, rejecting, rejected, failed or cancelled.
 */
export type TurnStatus = 'picking' | 'running' | 'open' | 'unchanged' | 'merging' | 'merged' | 'conflict' | 'rejecting' | 'rejected' | 'failed' | 'cancelled';
export type ChangedFile = { path: string; added?: number; removed?: number };
export type Turn = {
  n: number;
  bot_id: string | null;
  /** Empty while the orchestrator is picking, and on the orchestrator's own closing turn. */
  bot_slug: string;
  bot_name: string;
  branch: string;
  status: TurnStatus;
  picked_by: TurnMode;
  /** Why the orchestrator picked this bot, when it said. */
  why: string;
  said: string;
  title: string;
  pr_url: string | null;
  number: number | null;
  head_sha: string | null;
  files: ChangedFile[];
  done: boolean;
  error: string;
  input_tokens: number;
  output_tokens: number;
  cost_micros: number;
  created_at: string;
  finished_at: string | null;
};
export type ProjectRunStatus = 'running' | 'needs_input' | 'done' | 'failed';
/** Why a run ended: the crew said so, the orchestrator said so, or a safety cap stopped it. */
export type Ended = '' | 'done' | 'orchestrator' | 'max_turns' | 'max_spend';
export type ProjectRun = {
  id: string;
  project_slug: string;
  /** May be empty: the crew then works from the repo's own instructions. */
  task: string;
  status: ProjectRunStatus;
  ended: Ended;
  turn_mode: TurnMode;
  review: Review;
  runs_on: string | null;
  /** The model and effort the run was started with; none: each bot's own. */
  model?: string | null;
  effort?: Effort | null;
  max_turns: number;
  max_spend_cents: number | null;
  /** With review `end`: the run's own branch, and the one pull request of it all. */
  work_branch: string | null;
  pr_url: string | null;
  number: number | null;
  error: string;
  turns: Turn[];
  input_tokens: number;
  output_tokens: number;
  cost_micros: number;
  created_at: string;
  finished_at: string | null;
};
/** A run's start: the task (may be empty), and the composer's model and effort (none: each bot's own). */
export type RunStart = { task: string; model: string | null; effort: Effort | null };

export const projectKeys = {
  projects: ['projects'] as const,
  runs: (slug: string) => ['projects', slug, 'runs'] as const,
  run: (id: string) => ['project-runs', id] as const,
};

const one = (slug: string) => `/projects/${encodeURIComponent(slug)}`;
const runPath = (id: string) => `/project-runs/${encodeURIComponent(id)}`;
/** A turn is out working (or being picked): the run is read again until it stops. */
export const runGoing = (status: ProjectRunStatus | undefined) => status === 'running';
/** `owner/name` of a repo's address. */
export const repoName = (url: string) => url.replace(/^https?:\/\/(www\.)?github\.com\//, '').replace(/\.git$/, '');

// Reads

export const useProjects = () => useQuery({ queryKey: projectKeys.projects, queryFn: async () => (await api.get<{ projects: Project[] }>('/projects')).projects });
/** A workspace's runs, newest first, asked for again every three seconds while one of them is running. */
export const useProjectRuns = (slug: string | undefined, every = 3000) =>
  useQuery({
    queryKey: projectKeys.runs(slug ?? ''),
    enabled: slug !== undefined,
    queryFn: async () => (await api.get<{ runs: ProjectRun[] }>(`${one(slug!)}/runs`)).runs,
    refetchInterval: (query) => (query.state.data?.some((r) => runGoing(r.status)) ? every : false),
  });
/** One run, asked for again every three seconds while a turn of it is out. */
export const useProjectRun = (id: string | null, every = 3000) =>
  useQuery({
    queryKey: projectKeys.run(id ?? ''),
    enabled: id !== null,
    queryFn: () => api.get<ProjectRun>(runPath(id!)),
    refetchInterval: (query) => (runGoing(query.state.data?.status) ? every : false),
  });

// Writes

function useWrite<A, T>(fn: (args: A) => Promise<T>, refresh: ReadonlyArray<readonly unknown[]>) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: () => Promise.all(refresh.map((queryKey) => client.invalidateQueries({ queryKey }))),
  });
}

/** Gets or makes the crew's workspace for a repo and branch, and sets its bots and settings in the same call. */
export const useSetCrew = () => useWrite((crew: CrewSet) => api.put<Project>('/projects/crew', crew), [projectKeys.projects]);
export const useRunProject = (slug: string | undefined) =>
  useWrite((start: RunStart) => api.post<ProjectRun>(`${one(slug!)}/runs`, start), [projectKeys.runs(slug ?? ''), recentKeys.all]);

/** Merging or rejecting the pull request a run waits on, or cancelling it: the runs and what waits are read again. */
const afterRun = [projectKeys.projects, ['project-runs'], botKeys.approvals, recentKeys.all] as const;
export const useAnswerProjectRun = () =>
  useWrite(({ id, answer }: { id: string; answer: 'merge' | 'reject' }) => api.post<ProjectRun>(`${runPath(id)}/answer`, { answer }), afterRun);
export const useCancelProjectRun = () => useWrite((id: string) => api.post<ProjectRun>(`${runPath(id)}/cancel`), afterRun);
