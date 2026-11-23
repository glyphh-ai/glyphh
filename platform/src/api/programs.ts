import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, ApiError } from './client';
import type { RunsWhere, RunStatus, Schedule } from './bots';

/**
 * Programs (the server's /v1/programs, /v1/program-runs, /v1/tools/search; docs/specs/programs.md there): a
 * deterministic workflow one bot or several follow. A program is one file, `program.py`; its steps are its `FLOW`,
 * which the canvas reads and saves as `flow`, and the file's text is `source`. Saving either one is the program: the
 * server's answer is read back into both views.
 */
export type StepKind = 'tool' | 'bot' | 'ask' | 'branch' | 'code';
/** Where a step goes next: one step's id, or for `ask` and `branch` a map from the result to a step (`else` for any other); none ends. */
export type Next = string | null | Record<string, string | null>;
/** One step of `FLOW`, with only the spec's keys. */
export type Step = {
  id: string;
  kind: StepKind;
  title?: string;
  /** The bot that does it, by slug; none: the program's own bot. */
  bot?: string | null;
  /** A tool key of that bot (a connection's, `fetch`, a built-in). */
  tool?: string;
  input?: Record<string, unknown>;
  task?: string;
  question?: string;
  options?: string[];
  on?: string;
  /** A function of `program.py`, run in a sandbox (on a rrotor). */
  function?: string;
  next?: Next;
  /** Where it sits on the canvas. */
  at?: [number, number];
};
export type ProgramRunStatus = Exclude<RunStatus, 'skipped'> | 'cancelled';
export type LastRun = { id: string; status: ProgramRunStatus; created_at: string } | null;
export type Program = {
  slug: string;
  name: string;
  summary: string | null;
  /** The program's own bot, by slug. */
  bot: string | null;
  /** `program.py`, the whole file. */
  source: string;
  /** Its `FLOW`, parsed. */
  flow: Step[];
  /** The functions of `program.py` a `code` step may call. */
  functions: string[];
  /** What is wrong with it, in plain words; none when it can run. */
  problems: string[];
  /** The org's rrotor it runs on; none for Glyphh cloud. */
  runs_on: string | null;
  can_run_on: RunsWhere[];
  schedule?: Schedule | null;
  schedule_summary?: string;
  next_run_at?: string | null;
  last_run: LastRun;
  template?: string | null;
  created_at: string;
  updated_at: string;
};
export type NewProgram = {
  name: string;
  summary?: string;
  bot?: string | null;
  runs_on?: string | null;
  schedule?: Schedule;
} & ({ source: string; flow?: never } | { flow: Step[]; source?: never } | { source?: never; flow?: never });
/** A change: any of the program's fields, with `flow` (rewrites its `FLOW` in place) or `source` (replaces the file), not both. */
export type ProgramChange = {
  name?: string;
  summary?: string;
  bot?: string | null;
  runs_on?: string | null;
  schedule?: Schedule;
} & ({ flow: Step[]; source?: never } | { source: string; flow?: never } | { flow?: never; source?: never });
/** Who or what started a run. */
export type Trigger = 'person' | 'schedule' | 'connector' | (string & {});
/** What a run waits on the person for: a question, and its options when it has them. */
export type ProgramQuestion = { question: string; options?: string[]; step?: string; approval?: boolean; detail?: string };
export type ProgramRun = {
  id: string;
  program: string;
  status: ProgramRunStatus;
  input: string;
  /** The step it is at (or stopped at). */
  at: string | null;
  /** Each finished step's result, by step id. */
  outputs: Record<string, unknown>;
  question: ProgramQuestion | string | null;
  error: string;
  trigger: Trigger;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
};
export type ProgramEventKind = 'started' | 'step' | 'asked' | 'answered' | 'done' | 'failed' | 'cancelled';
/** One line of a run's audit trail, in order (`n`). */
export type ProgramEvent = {
  n: number;
  at: string;
  kind: ProgramEventKind | (string & {});
  step: string | null;
  title: string | null;
  /** The bot that did the step, by slug. */
  bot: string | null;
  ok: boolean | null;
  detail: string | null;
  /** Who: a person's email, `schedule` or `connector`. */
  by: string | null;
};
/** A tool found for a step: of the org's connected apps, or a built-in; `added` when the bot has it already. */
export type FoundTool = {
  key: string;
  title: string;
  app: string;
  description: string | null;
  read_only: boolean;
  connection_id: string | null;
  added: boolean;
};

export const programKeys = {
  all: ['programs'] as const,
  list: (q: string) => ['programs', '~list', q] as const,
  one: (slug: string) => ['programs', slug] as const,
  runs: (slug: string) => ['programs', slug, 'runs'] as const,
  run: (id: string) => ['program-runs', id] as const,
  events: (id: string) => ['program-runs', id, 'events'] as const,
  tools: (q: string, bot: string) => ['tools', '~search', q, bot] as const,
};

const one = (slug: string) => `/programs/${encodeURIComponent(slug)}`;
const runPath = (id: string) => `/program-runs/${encodeURIComponent(id)}`;

/** A run still going: queued, running or dispatched to a rrotor. */
export const going = (status: ProgramRunStatus | undefined) => status === 'queued' || status === 'running' || status === 'dispatched';
/** A run not over yet: going, or waiting on the person. */
export const live = (status: ProgramRunStatus | undefined) => going(status) || status === 'needs_input';

// Reads

/** The org's programs, the words searched for when given; the last answer kept while the next is asked. */
export const usePrograms = (q = '') =>
  useQuery({
    queryKey: programKeys.list(q),
    queryFn: async () => (await api.get<{ programs: Program[] }>(q ? `/programs?q=${encodeURIComponent(q)}` : '/programs')).programs,
    placeholderData: keepPreviousData,
  });
export const useProgram = (slug: string | null) =>
  useQuery({ queryKey: programKeys.one(slug ?? ''), enabled: slug !== null, queryFn: () => api.get<Program>(one(slug!)) });

/** A program's runs, newest first; asked for again while the newest is not over. */
/** How often a run being followed is asked for again, in milliseconds (a test makes it quick). */
export const following = { every: 1500 };

export const useProgramRuns = (slug: string | null, every = following.every + 500) =>
  useQuery({
    queryKey: programKeys.runs(slug ?? ''),
    enabled: slug !== null,
    queryFn: async () => (await api.get<{ runs: ProgramRun[] }>(`${one(slug!)}/runs`)).runs,
    refetchInterval: (query) => (live(query.state.data?.[0]?.status) ? every : false),
  });

/** One run, asked for again while it is going (and, slower, while it waits on the person). */
export const useProgramRun = (id: string | null, every = following.every) =>
  useQuery({
    queryKey: programKeys.run(id ?? ''),
    enabled: id !== null,
    queryFn: () => api.get<ProgramRun>(runPath(id!)),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return going(status) ? every : status === 'needs_input' ? every * 3 : false;
    },
  });

/** Events after the last one held, joined to those already held (by `n`, so an `after` read inclusively is harmless). */
export const joinEvents = (held: ProgramEvent[], fresh: ProgramEvent[]): ProgramEvent[] => {
  const seen = new Set(held.map((e) => e.n));
  return [...held, ...fresh.filter((e) => !seen.has(e.n))].sort((a, b) => a.n - b.n);
};

/**
 * A run's events, followed: each read asks only for those after the last one held (`?after=`) and adds them. Asked for
 * again while the run is not over (`following`).
 */
export function useProgramEvents(id: string | null, follow: boolean, every = following.every) {
  const client = useQueryClient();
  return useQuery({
    queryKey: programKeys.events(id ?? ''),
    enabled: id !== null,
    queryFn: async () => {
      const held = client.getQueryData<ProgramEvent[]>(programKeys.events(id!)) ?? [];
      const after = held.at(-1)?.n ?? 0;
      const { events } = await api.get<{ events: ProgramEvent[] }>(`${runPath(id!)}/events?after=${after}`);
      return joinEvents(held, events);
    },
    refetchInterval: follow ? every : false,
  });
}

/** Tools to use in a step, found for the words, as the given bot has them (`added`). */
export const useToolSearch = (q: string, bot: string | null, enabled = true) =>
  useQuery({
    queryKey: programKeys.tools(q, bot ?? ''),
    enabled,
    queryFn: async () => {
      const params = new URLSearchParams({ q });
      if (bot) params.set('bot', bot);
      const found = await api.get<{ tools: FoundTool[] } | FoundTool[]>(`/tools/search?${params}`);
      return Array.isArray(found) ? found : found.tools;
    },
    placeholderData: keepPreviousData,
    staleTime: 30_000,
  });

// Writes

function useWrite<A, T>(fn: (args: A) => Promise<T>, refresh: ReadonlyArray<readonly unknown[]>, after?: (saved: T) => void) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: async (saved) => {
      after?.(saved);
      await Promise.all(refresh.map((queryKey) => client.invalidateQueries({ queryKey })));
    },
  });
}

export const useCreateProgram = () => useWrite((program: NewProgram) => api.post<Program>('/programs', program), [programKeys.all]);

/** Saves a change; the server's answer is the program now (both views are read from it). */
export function useUpdateProgram(slug: string) {
  const client = useQueryClient();
  return useWrite(
    (change: ProgramChange) => api.patch<Program>(one(slug), change),
    [programKeys.all],
    (saved) => client.setQueryData(programKeys.one(saved.slug), saved),
  );
}
export const useDeleteProgram = () => useWrite((slug: string) => api.delete<void>(one(slug)), [programKeys.all]);

export const useRunProgram = (slug: string) =>
  useWrite((input: string) => api.post<ProgramRun>(`${one(slug)}/runs`, { input }), [programKeys.runs(slug), programKeys.all]);

const afterRun = [programKeys.all, ['program-runs'], ['bot-approvals']] as const;
export const useAnswerProgramRun = () =>
  useWrite(({ id, answer }: { id: string; answer: string }) => api.post<ProgramRun>(`${runPath(id)}/answer`, { answer }), afterRun);
export const useCancelProgramRun = () => useWrite((id: string) => api.post<ProgramRun>(`${runPath(id)}/cancel`), afterRun);

/** Gives a found tool to a bot, so a step of that bot can use it. */
export const useAddBotTool = () =>
  useWrite(
    ({ bot, connection_id, tool }: { bot: string; connection_id: string | null; tool: string }) =>
      api.post<unknown>(`/bots/${encodeURIComponent(bot)}/tools`, { connection_id, tool }),
    [['tools'], ['bots']],
  );

/** The problems of a program the server would not take (422, `problems`), one a line; else none. */
export const refusedProblems = (error: unknown): string[] => {
  if (!(error instanceof ApiError)) return [];
  const problems = error.detail.problems;
  return Array.isArray(problems) ? problems.map(String) : [];
};

/** A run's question as words and options, whichever way the server sent it. */
export const questionOf = (run: Pick<ProgramRun, 'question'> | null | undefined): ProgramQuestion | null => {
  const q = run?.question;
  if (!q) return null;
  return typeof q === 'string' ? { question: q } : q;
};
