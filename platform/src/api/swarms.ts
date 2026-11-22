import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { botKeys } from './bots';
import { api } from './client';

/**
 * The org's swarms (the server's /v1/swarms, /v1/swarm-runs and /v1/github-key): a crew of its bots, in speaking
 * order, taking turns on one GitHub repo on one of its rrotors. Each turn is a pull request; with review `each_turn`
 * it waits in the approvals queue for a merge or a reject, with `auto` it is merged as it opens. A bot that says DONE
 * twice in a row with the next (or a crew of one) ends the run early.
 */
export type Review = 'each_turn' | 'auto';
export type SwarmMember = { id: string; slug: string; name: string };
export type Swarm = {
  id: string;
  slug: string;
  name: string;
  repo_url: string;
  base_branch: string;
  members: SwarmMember[];
  rounds: number;
  review: Review;
  runs_on: string;
  created_at: string;
  updated_at: string;
};
export type NewSwarm = {
  name: string;
  repo_url: string;
  base_branch?: string;
  /** The org's bot ids, in speaking order. */
  members: string[];
  rounds?: number;
  review?: Review;
  runs_on: string;
};
export type SwarmChange = Partial<NewSwarm>;
/** running, open (its pull request waits), unchanged (no changes), merging, merged, conflict, rejecting, rejected, failed or cancelled. */
export type TurnStatus = 'running' | 'open' | 'unchanged' | 'merging' | 'merged' | 'conflict' | 'rejecting' | 'rejected' | 'failed' | 'cancelled';
export type ChangedFile = { path: string; added?: number; removed?: number };
export type SwarmTurn = {
  n: number;
  round: number;
  bot_id: string | null;
  bot_slug: string;
  bot_name: string;
  branch: string;
  status: TurnStatus;
  said: string;
  title: string;
  pr_url: string | null;
  number: number | null;
  head_sha: string | null;
  files: ChangedFile[];
  done: boolean;
  error: string;
  created_at: string;
  finished_at: string | null;
};
export type SwarmRunStatus = 'running' | 'needs_input' | 'done' | 'failed';
export type SwarmRun = {
  id: string;
  swarm_slug: string;
  task: string;
  status: SwarmRunStatus;
  rounds: number;
  review: Review;
  runs_on: string | null;
  error: string;
  turns: SwarmTurn[];
  created_at: string;
  finished_at: string | null;
};
export type GitHubKey = { set: boolean; hint: string; login: string; set_at: string | null };

export const swarmKeys = {
  swarms: ['swarms'] as const,
  swarm: (slug: string) => ['swarms', slug] as const,
  runs: (slug: string) => ['swarms', slug, 'runs'] as const,
  run: (id: string) => ['swarm-runs', id] as const,
  github: ['github-key'] as const,
};

const one = (slug: string) => `/swarms/${encodeURIComponent(slug)}`;
const runPath = (id: string) => `/swarm-runs/${encodeURIComponent(id)}`;
export const swarmGoing = (status: SwarmRunStatus | undefined) => status === 'running';

// Reads

export const useSwarms = () => useQuery({ queryKey: swarmKeys.swarms, queryFn: async () => (await api.get<{ swarms: Swarm[] }>('/swarms')).swarms });
export const useSwarm = (slug: string) => useQuery({ queryKey: swarmKeys.swarm(slug), queryFn: () => api.get<Swarm>(one(slug)) });
/** A swarm's runs, newest first, asked for again every three seconds while one of them is running. */
export const useSwarmRuns = (slug: string, every = 3000) =>
  useQuery({
    queryKey: swarmKeys.runs(slug),
    queryFn: async () => (await api.get<{ runs: SwarmRun[] }>(`${one(slug)}/runs`)).runs,
    refetchInterval: (query) => (query.state.data?.some((r) => swarmGoing(r.status)) ? every : false),
  });
/** One run, asked for again every three seconds while a turn of it is out on the rrotor. */
export const useSwarmRun = (id: string | null, every = 3000) =>
  useQuery({
    queryKey: swarmKeys.run(id ?? ''),
    enabled: id !== null,
    queryFn: () => api.get<SwarmRun>(runPath(id!)),
    refetchInterval: (query) => (swarmGoing(query.state.data?.status) ? every : false),
  });
export const useGitHubKey = () => useQuery({ queryKey: swarmKeys.github, queryFn: () => api.get<GitHubKey>('/github-key') });

// Writes

function useWrite<A, T>(fn: (args: A) => Promise<T>, refresh: ReadonlyArray<readonly unknown[]>) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: () => Promise.all(refresh.map((queryKey) => client.invalidateQueries({ queryKey }))),
  });
}

export const useCreateSwarm = () => useWrite((swarm: NewSwarm) => api.post<Swarm>('/swarms', swarm), [swarmKeys.swarms]);
export const useUpdateSwarm = (slug: string) => useWrite((change: SwarmChange) => api.patch<Swarm>(one(slug), change), [swarmKeys.swarms]);
export const useDeleteSwarm = () => useWrite((slug: string) => api.delete<void>(one(slug)), [swarmKeys.swarms]);
export const useRunSwarm = (slug: string) => useWrite((task: string) => api.post<SwarmRun>(`${one(slug)}/runs`, { task }), [swarmKeys.runs(slug)]);

/** Merging or rejecting the pull request a run waits on, or cancelling it: the runs and the approvals queue read again. */
const afterRun = [swarmKeys.swarms, ['swarm-runs'], botKeys.approvals] as const;
export const useAnswerSwarmRun = () =>
  useWrite(({ id, answer }: { id: string; answer: 'merge' | 'reject' }) => api.post<SwarmRun>(`${runPath(id)}/answer`, { answer }), afterRun);
export const useCancelSwarmRun = () => useWrite((id: string) => api.post<SwarmRun>(`${runPath(id)}/cancel`), afterRun);

export const useSetGitHubKey = () => useWrite((token: string) => api.put<GitHubKey>('/github-key', { token }), [swarmKeys.github]);
export const useRemoveGitHubKey = () => useWrite(() => api.delete<GitHubKey>('/github-key'), [swarmKeys.github]);
