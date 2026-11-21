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
  instructions: string;
  model: string;
  spec: BotSpec;
  skills: Record<string, string>;
  gate_models: string[];
  connections: BotConnection[];
  created_at: string;
  updated_at: string;
  last_run: { id: string; status: RunStatus; created_at: string } | null;
};
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
export type NewBot = { name: string; summary?: string; look: Look; instructions: string; model?: string; spec?: BotSpec; skills?: Record<string, string> };
export type BotChange = Partial<NewBot>;
export type BotScope = { connection_id: string; tools: string[] };
/** An answer to a run's question: one option, or for a batch `1=keep 2=drop` or a map of item to option. */
export type Answer = string | Record<string, string>;
export type Wrong = { outcome: string; gate?: string; item?: string };

export const botKeys = {
  bots: ['bots'] as const,
  search: (q: string) => ['bots', '~search', q] as const,
  bot: (slug: string) => ['bots', slug] as const,
  models: ['bots', '~models'] as const,
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

/** The SDK's problems with a bot the server would not take (422, `problems`), one a line; else none. */
export const problemsOf = (error: unknown): string[] => {
  if (!(error instanceof ApiError)) return [];
  const problems = error.detail.problems;
  return Array.isArray(problems) ? problems.map(String) : [];
};
