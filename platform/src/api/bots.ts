import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { Look } from '@/bots/cat/look';
import { api, ApiError } from './client';

/**
 * Glyphh bots (the server's /v1/bots, /v1/bot-runs, /v1/bot-approvals, /v1/bot-key and /v1/connections; the bots
 * to add are the Marketplace's, in botTemplates.ts): each bot is a loop of steps the SDK walks (its spec), gates that learn in Ada, Claude for the
 * steps that need judgment, and the tools of the org's connections it is allowed. A run that needs the person stops
 * (needs_input) until they answer it, in the bot's runs or the org's approvals.
 */
export type Permission = 'allow' | 'ask' | 'deny';
export type Connection = {
  id: string;
  app: string;
  app_name: string;
  app_icon: string | null;
  account_id: string;
  label: string | null;
  permissions: Record<string, Permission>;
  created_at: string;
};
export type ConnectorApp = { slug: string; name: string; description: string | null; icon: string | null };
export type ConnectionTool = { key: string; name: string; description: string | null; permission: Permission };
export type BotConnection = { connection_id: string; app: string; app_name: string; tools: string[] };
export type RunStatus = 'queued' | 'running' | 'needs_input' | 'done' | 'failed' | 'skipped';
export type BotSpec = Record<string, unknown> & { loop?: Array<Record<string, unknown>>; gates?: Record<string, unknown> };
export type Bot = {
  id: string;
  slug: string;
  name: string;
  summary: string | null;
  look: Look;
  /** Its own drawn mascot (safe SVG from the server), shown in place of its cat; empty for the cat. */
  mascot?: string;
  instructions: string;
  model: string;
  permission_mode?: PermissionMode;
  voice?: string;
  spec: BotSpec;
  skills: Record<string, string>;
  gate_models: string[];
  connections: BotConnection[];
  /** When it runs on its own, as chosen in plain words (off when never set). */
  schedule?: Schedule;
  /** The schedule in the server's words: `Every day at 9:00`. */
  schedule_summary?: string;
  next_run_at?: string | null;
  /** Its next run in the schedule's time zone, `Mon 9:00`; empty when it is off. */
  next_run?: string;
  /** The org's rrotor it runs on; none for Glyphh cloud. */
  runs_on?: string | null;
  created_at: string;
  updated_at: string;
  last_run: { id: string; status: RunStatus; created_at: string } | null;
};
/** How often a bot runs on its own: off, every hour, every day, weekdays, one day each week or one day each month. */
export type Every = 'off' | 'hour' | 'day' | 'weekdays' | 'week' | 'month';
/** A bot's schedule as the person chooses it, never cron: `at` is HH:MM in `timezone`; `weekday` 0 is Monday. */
export type Schedule = { every: Every; at: string; weekday: number; day: number; timezone: string; input: string };
/** Where a bot can run: Glyphh cloud (`id` null) or one of the org's rrotors, linked to Glyphh right now or not. */
export type Place = { id: string | null; name: string; mode: 'cloud' | 'local' | 'self'; linked: boolean };
export type BotModel = {
  id: string;
  name: string;
  input_cents_per_mtok: number;
  output_cents_per_mtok: number;
  own_key_input_cents_per_mtok: number;
  own_key_output_cents_per_mtok: number;
  default: boolean;
};
export type BotModels = { models: BotModel[]; markup_pct: number };
export type BatchItem = { n: number; label: string; [k: string]: unknown };
export type Question = { question: string; options: string[]; batch: BatchItem[] | null; answer_with: string | null };
export type BotRun = {
  id: string;
  bot_slug: string;
  status: RunStatus;
  input: string;
  output: string;
  error: string;
  log: string[];
  data: Record<string, unknown>;
  question: Question | null;
  input_tokens: number;
  output_tokens: number;
  cost_micros: number;
  own_key: boolean;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
};
export type GateStats = Record<string, { precedents?: number; asked?: number; right?: number; [k: string]: unknown }>;
export type BotKey = { set: boolean; hint: string; set_at: string | null; glyphh_key: boolean };
/** Which tool steps wait for the person: ask (unless the connection allows the tool), connection (as it says), auto (none). */
export type PermissionMode = 'ask' | 'connection' | 'auto';
export type BotScope = { connection_id: string; tools: string[] };
export type NewBot = {
  name: string;
  summary?: string;
  look: Look;
  mascot?: string;
  instructions: string;
  model?: string;
  permission_mode?: PermissionMode;
  voice?: string;
  spec?: BotSpec;
  skills?: Record<string, string>;
  connections?: BotScope[];
  schedule?: Schedule;
  runs_on?: string | null;
};
export type BotChange = Partial<Omit<NewBot, 'connections'>>;
export type BotVoice = { id: string; name: string; accent: string; gender: string; default: boolean };
export type BotVoices = { voices: BotVoice[]; samples: boolean };
/** One line of the conversation with the bot maker. */
export type Said = { role: 'user' | 'assistant'; content: string };
/** The bot as the bot maker drafted it: ready for POST /v1/bots, but `apps` (what it needs connected). */
export type BotDraft = {
  name: string;
  summary: string;
  look: Look;
  mascot: string;
  instructions: string;
  model: string;
  spec: BotSpec;
  skills: Record<string, string>;
  apps: { app: string; tools: string[] }[];
  connections: BotScope[];
};
export type DraftReply = { reply: string; draft: BotDraft | null; problems: string[]; missing_apps: string[] };
/** An answer to a run's question: one option, or for a batch `1=keep 2=drop` or a map of item to option. */
export type Answer = string | Record<string, string>;
export type Wrong = { outcome: string; gate?: string; item?: string };

export const botKeys = {
  bots: ['bots'] as const,
  search: (q: string) => ['bots', '~search', q] as const,
  bot: (slug: string) => ['bots', slug] as const,
  models: ['bots', '~models'] as const,
  voices: ['bots', '~voices'] as const,
  places: ['bots', '~places'] as const,
  gates: (slug: string) => ['bots', slug, 'gates'] as const,
  runs: (slug: string) => ['bots', slug, 'runs'] as const,
  run: (id: string) => ['bot-runs', id] as const,
  approvals: ['bot-approvals'] as const,
  key: ['bot-key'] as const,
  connections: ['connections'] as const,
  apps: (q: string) => ['connections', '~apps', q] as const,
  tools: (id: string) => ['connections', id, 'tools'] as const,
};

const one = (slug: string) => `/bots/${encodeURIComponent(slug)}`;
const runPath = (id: string) => `/bot-runs/${encodeURIComponent(id)}`;

// Reads

export const useBots = () => useQuery({ queryKey: botKeys.bots, queryFn: async () => (await api.get<{ bots: Bot[] }>('/bots')).bots });
/** The org's bots the server finds for the words (`GET /v1/bots?q=`), the last answer kept while the next is asked. */
export const useBotSearch = (q: string) =>
  useQuery({
    queryKey: botKeys.search(q),
    queryFn: async () => (await api.get<{ bots: Bot[] }>(`/bots?q=${encodeURIComponent(q)}`)).bots,
    placeholderData: keepPreviousData,
  });
export const useBot = (slug: string) => useQuery({ queryKey: botKeys.bot(slug), queryFn: () => api.get<Bot>(one(slug)) });
export const useBotModels = () => useQuery({ queryKey: botKeys.models, queryFn: () => api.get<BotModels>('/bots/models'), staleTime: 60_000 });
export const useBotVoices = () => useQuery({ queryKey: botKeys.voices, queryFn: () => api.get<BotVoices>('/bots/voices'), staleTime: 60 * 60_000 });
/** Where the org's bots can run: Glyphh cloud first, then its rrotors, each linked right now or not. */
export const useBotPlaces = () =>
  useQuery({ queryKey: botKeys.places, queryFn: async () => (await api.get<{ places: Place[] }>('/bots/places')).places, staleTime: 60_000 });
export const useBotGates = (slug: string) =>
  useQuery({ queryKey: botKeys.gates(slug), queryFn: async () => (await api.get<{ gates: GateStats }>(`${one(slug)}/gates`)).gates });

export const working = (status: RunStatus | undefined) => status === 'queued' || status === 'running';

/** A bot's runs, asked for again every two seconds while one of them is queued or running. */
export const useBotRuns = (slug: string, every = 2000) =>
  useQuery({
    queryKey: botKeys.runs(slug),
    queryFn: async () => (await api.get<{ runs: BotRun[] }>(`${one(slug)}/runs`)).runs,
    refetchInterval: (query) => (query.state.data?.some((r) => working(r.status)) ? every : false),
  });

/** One run, asked for again every two seconds while it is queued or running. */
export const useBotRun = (id: string | null, every = 2000) =>
  useQuery({
    queryKey: botKeys.run(id ?? ''),
    enabled: id !== null,
    queryFn: () => api.get<BotRun>(runPath(id!)),
    refetchInterval: (query) => (working(query.state.data?.status) ? every : false),
  });

/** Every run of the org waiting on the person (its approvals queue), oldest first; asked for again every 15 seconds. */
export const useApprovals = (every = 15_000) =>
  useQuery({ queryKey: botKeys.approvals, queryFn: async () => (await api.get<{ runs: BotRun[] }>('/bot-approvals')).runs, refetchInterval: every });

export const useBotKey = () => useQuery({ queryKey: botKeys.key, queryFn: () => api.get<BotKey>('/bot-key') });

export const useConnections = () =>
  useQuery({ queryKey: botKeys.connections, queryFn: async () => (await api.get<{ connections: Connection[] }>('/connections')).connections });
export const useConnectionTools = (id: string) =>
  useQuery({
    queryKey: botKeys.tools(id),
    queryFn: async () => (await api.get<{ tools: ConnectionTool[] }>(`/connections/${encodeURIComponent(id)}/tools`)).tools,
    staleTime: 5 * 60_000,
  });

// Writes

function useWrite<A, T>(fn: (args: A) => Promise<T>, refresh: ReadonlyArray<readonly unknown[]>) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: () => Promise.all(refresh.map((queryKey) => client.invalidateQueries({ queryKey }))),
  });
}

export const useCreateBot = () => useWrite((bot: NewBot) => api.post<Bot>('/bots', bot), [botKeys.bots]);
/** Create with AI: the bot maker's next turn, a question or the bot drafted and checked (it makes nothing). */
export const useDraftBot = () =>
  useMutation({ mutationFn: (body: { messages: Said[]; draft?: BotDraft | null }) => api.post<DraftReply>('/bots/draft', body) });
/** A new mascot drawn from words: safe black-and-white SVG for a bot's `mascot`. */
export const useDrawMascot = () => useMutation({ mutationFn: (prompt: string) => api.post<{ mascot: string }>('/bots/mascot', { prompt }) });
export const useUpdateBot = (slug: string) => useWrite((change: BotChange) => api.patch<Bot>(one(slug), change), [botKeys.bots]);
export const useDeleteBot = () => useWrite((slug: string) => api.delete<void>(one(slug)), [botKeys.bots]);
export const useScopeBot = (slug: string) =>
  useWrite((connections: BotScope[]) => api.put<Bot>(`${one(slug)}/connections`, { connections }), [botKeys.bots]);
export const useRunBot = (slug: string) => useWrite((input: string) => api.post<BotRun>(`${one(slug)}/runs`, { input }), [botKeys.bots]);

/** Answering, correcting or cancelling a run: the bot, its runs and the approvals queue are read again. */
const afterRun = [botKeys.bots, botKeys.approvals, ['bot-runs']] as const;
export const useAnswerRun = () =>
  useWrite(({ id, answer }: { id: string; answer: Answer }) => api.post<BotRun>(`${runPath(id)}/answer`, { answer }), afterRun);
export const useCancelRun = () => useWrite((id: string) => api.post<BotRun>(`${runPath(id)}/cancel`), afterRun);
export const useWrongRun = () =>
  useWrite(({ id, ...body }: Wrong & { id: string }) => api.post<{ gate: string; said: string; now: string }>(`${runPath(id)}/wrong`, body), [botKeys.bots]);

export const useSetBotKey = () => useWrite((key: string) => api.put<BotKey>('/bot-key', { key }), [botKeys.key]);
export const useRemoveBotKey = () => useWrite(() => api.delete<BotKey>('/bot-key'), [botKeys.key]);

export const useLinkConnection = () =>
  useMutation({ mutationFn: (app: string) => api.post<{ url: string; expires_at: string }>('/connections/link', { app }) });
export const useSyncConnections = () => useWrite(() => api.post<{ connections: Connection[] }>('/connections/sync'), [botKeys.connections]);
export const useRemoveConnection = () =>
  useWrite((id: string) => api.delete<void>(`/connections/${encodeURIComponent(id)}`), [botKeys.connections, botKeys.bots]);
export const useSetPermissions = (id: string) =>
  useWrite(
    (permissions: Record<string, Permission>) => api.put<Connection>(`/connections/${encodeURIComponent(id)}/permissions`, { permissions }),
    [botKeys.connections, botKeys.tools(id)],
  );

/** Not set up on the server: no Pipedream project (503 E_UNAVAILABLE, reason pipedream_off). */
export const connectionsOff = (error: unknown): boolean =>
  error instanceof ApiError && error.status === 503 && (error.detail as { reason?: unknown }).reason === 'pipedream_off';

/** A run of a bot set to run on one of the org's machines: not sent to rrotors yet (409, reason runs_on_pending). */
export const runsOnPending = (error: unknown): boolean =>
  error instanceof ApiError && error.status === 409 && (error.detail as { reason?: unknown }).reason === 'runs_on_pending';

/** The SDK's problems with a bot the server would not take (422, `problems`), one a line; else none. */
export const problemsOf = (error: unknown): string[] => {
  if (!(error instanceof ApiError)) return [];
  const problems = error.detail.problems;
  return Array.isArray(problems) ? problems.map(String) : [];
};
