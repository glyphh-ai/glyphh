import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { Look } from '@/bots/cat/look';
import { api, ApiError } from './client';

/**
 * Glyphh bots (the server's /v1/bots and /v1/connections): Claude agents the org runs on Glyphh, billed by their
 * tokens, that use the org's connections (Pipedream accounts) with only the tools each bot is allowed, and the org's
 * Ada models to decide the way it was decided before.
 */
export type Connection = { id: string; app: string; app_name: string; app_icon: string | null; account_id: string; label: string | null; created_at: string };
export type ConnectorApp = { slug: string; name: string; description: string | null; icon: string | null };
export type ConnectionTool = { key: string; name: string; description: string | null };
export type BotConnection = { connection_id: string; app: string; app_name: string; tools: string[] };
export type BotLimits = { max_turns: number; usd_per_run: number };
export type RunStatus = 'queued' | 'running' | 'done' | 'failed';
export type Bot = {
  id: string;
  slug: string;
  name: string;
  summary: string | null;
  look: Look;
  instructions: string;
  model: string;
  models: string[];
  connections: BotConnection[];
  limits: BotLimits;
  created_at: string;
  updated_at: string;
  last_run: { id: string; status: RunStatus; created_at: string } | null;
};
export type BotModel = { id: string; name: string; input_cents_per_mtok: number; output_cents_per_mtok: number; default: boolean };
export type RunStep = { kind: 'text' | 'tool' | 'ada'; name: string | null; input: unknown; output: unknown; is_error: boolean; at: string };
export type BotRun = {
  id: string;
  bot_slug: string;
  status: RunStatus;
  input: string;
  output: string | null;
  error: string | null;
  steps: RunStep[];
  input_tokens: number;
  output_tokens: number;
  cost_micros: number;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
};
export type NewBot = { name: string; summary?: string; look: Look; instructions: string; model?: string; models?: string[]; limits?: BotLimits };
export type BotChange = Partial<Omit<NewBot, 'limits'>> & { limits?: BotLimits };
export type BotScope = { connection_id: string; tools: string[] };

export const botKeys = {
  bots: ['bots'] as const,
  bot: (slug: string) => ['bots', slug] as const,
  models: ['bots', '~models'] as const,
  runs: (slug: string) => ['bots', slug, 'runs'] as const,
  run: (id: string) => ['bot-runs', id] as const,
  connections: ['connections'] as const,
  apps: (q: string) => ['connections', '~apps', q] as const,
  tools: (id: string) => ['connections', id, 'tools'] as const,
};

const one = (slug: string) => `/bots/${encodeURIComponent(slug)}`;

// Reads

export const useBots = () => useQuery({ queryKey: botKeys.bots, queryFn: async () => (await api.get<{ bots: Bot[] }>('/bots')).bots });
export const useBot = (slug: string) => useQuery({ queryKey: botKeys.bot(slug), queryFn: () => api.get<Bot>(one(slug)) });
export const useBotModels = () =>
  useQuery({ queryKey: botKeys.models, queryFn: async () => (await api.get<{ models: BotModel[] }>('/bots/models')).models, staleTime: 60_000 });
export const useBotRuns = (slug: string) =>
  useQuery({ queryKey: botKeys.runs(slug), queryFn: async () => (await api.get<{ runs: BotRun[] }>(`${one(slug)}/runs`)).runs });

const working = (status: RunStatus | undefined) => status === 'queued' || status === 'running';

/** One run, asked for again every two seconds while it is queued or running. */
export const useBotRun = (id: string | null, every = 2000) =>
  useQuery({
    queryKey: botKeys.run(id ?? ''),
    enabled: id !== null,
    queryFn: () => api.get<BotRun>(`/bot-runs/${encodeURIComponent(id!)}`),
    refetchInterval: (query) => (working(query.state.data?.status) ? every : false),
  });

export const useConnections = () =>
  useQuery({ queryKey: botKeys.connections, queryFn: async () => (await api.get<{ connections: Connection[] }>('/connections')).connections });
export const useConnectorApps = (q: string, enabled = true) =>
  useQuery({
    queryKey: botKeys.apps(q),
    enabled,
    queryFn: () => api.get<{ apps: ConnectorApp[]; next_cursor: string | null }>(`/connections/apps?q=${encodeURIComponent(q)}`),
  });
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

export const useLinkConnection = () => useMutation({ mutationFn: (app: string) => api.post<{ url: string; expires_at: string }>('/connections/link', { app }) });
export const useSyncConnections = () =>
  useWrite(() => api.post<{ connections: Connection[] }>('/connections/sync'), [botKeys.connections]);
export const useRemoveConnection = () => useWrite((id: string) => api.delete<void>(`/connections/${encodeURIComponent(id)}`), [botKeys.connections, botKeys.bots]);

/** Not set up on the server: no Pipedream project (503 E_UNAVAILABLE, reason pipedream_off). */
export const connectionsOff = (error: unknown): boolean =>
  error instanceof ApiError && error.status === 503 && (error.detail as { reason?: unknown }).reason === 'pipedream_off';
