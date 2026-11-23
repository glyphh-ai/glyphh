import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { Look } from '@/bots/cat/look';
import { api, ApiError } from './client';

/**
 * Glyphh bots (the server's /v1/bots, /v1/bot-runs, /v1/bot-approvals, /v1/bot-key and /v1/connections; the bots
 * to add are the Marketplace's, in botTemplates.ts): each bot is a Claude agent you talk to, with what it decides
 * learned in Ada and the tools of the org's connections it is allowed. A run is one turn of the conversation; one that
 * needs the person stops (needs_input) until they answer it, in the bot's chat.
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
  /** How the connection stands, once the server says: `ok` (it works), `sign_in` (the person must sign in again) or `failed`. Not sent yet. */
  status?: 'ok' | 'sign_in' | 'failed';
  created_at: string;
};
export type ConnectorApp = { slug: string; name: string; description: string | null; icon: string | null };
/** A tool's MCP hints (readOnlyHint, destructiveHint), when the server sends them; it does not yet. */
export type ToolAnnotations = { readOnlyHint?: boolean; destructiveHint?: boolean; openWorldHint?: boolean };
export type ConnectionTool = {
  key: string;
  name: string;
  description: string | null;
  permission: Permission;
  annotations?: ToolAnnotations | null;
};
export type BotConnection = { connection_id: string; app: string; app_name: string; tools: string[] };
/** `dispatched`: sent to the org's rrotor the bot runs on, running there until its result comes back. */
export type RunStatus = 'queued' | 'running' | 'dispatched' | 'needs_input' | 'done' | 'failed' | 'skipped';
/** A bot's internal definition: kept as loaded and saved back unchanged, never shown. Only what it decides is read. */
export type BotSpec = Record<string, unknown> & { gates?: Record<string, unknown> };
/** `orchestrator`: the org's one bot that leads the crew and can ask the others; always there, never deleted. */
export type BotRole = 'bot' | 'orchestrator';
/** Where a bot may run: Glyphh cloud, one of the org's rrotors, or both. */
export type RunsWhere = 'cloud' | 'rrotor';
export type Bot = {
  id: string;
  slug: string;
  name: string;
  summary: string | null;
  look: Look;
  /** Its own drawn mascot (safe SVG from the server), shown in place of its cat; empty for the cat. */
  mascot?: string;
  instructions: string;
  /** `orchestrator` for the org's orchestrator; a bot otherwise (and on a server that does not say). */
  role?: BotRole;
  /** Its standing task: what it does when it runs on its own (4,000 characters at most). */
  task?: string;
  /** Things to ask it, offered in its empty chat: six at most, 200 characters each. */
  examples?: string[];
  /** Where it may run; a bot that needs a machine of the org's own has only `rrotor`. */
  can_run_on?: RunsWhere[];
  model: string;
  permission_mode?: PermissionMode;
  /** How hard it thinks: low, medium (the default) or high. */
  effort?: Effort;
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
  /** The folders on that rrotor it may read or change; none on Glyphh cloud. */
  folders?: BotFolder[];
  created_at: string;
  updated_at: string;
  last_run: { id: string; status: RunStatus; created_at: string } | null;
};
/** A folder on the bot's rrotor: `read` to read it only, `write` to read and change it. */
export type BotFolder = { path: string; access: 'read' | 'write' };
/** How often a bot runs on its own: off, every hour, every day, weekdays, one day each week or one day each month. */
export type Every = 'off' | 'hour' | 'day' | 'weekdays' | 'week' | 'month';
/** A bot's schedule as the person chooses it, never cron: `at` is HH:MM in `timezone`; `weekday` 0 is Monday. */
export type Schedule = { every: Every; at: string; weekday: number; day: number; timezone: string; input: string };
/** Where a bot can run: Glyphh cloud (`id` null) or one of the org's rrotors, linked to Glyphh right now or not. */
export type Place = {
  id: string | null;
  name: string;
  mode: 'cloud' | 'local' | 'self';
  linked: boolean;
  /** A rrotor's own address, which the browser asks for that machine's folders (api/rrotorFolders.ts). */
  url?: string | null;
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
/** How hard a bot thinks before it answers. */
export type Effort = string;
export type BotModels = { models: BotModel[]; markup_pct: number; /** The effort levels every bot model takes, and the one a new bot starts on. */ efforts?: Effort[]; default_effort?: Effort };
export type BatchItem = { n: number; label: string; [k: string]: unknown };
/**
 * What a run asks the person. An approval (the bot wants to act and must ask first) also says the action in plain
 * words (`detail`); `tool` is the server's own name for it and is never shown.
 */
export type Question = { question: string; options: string[]; batch: BatchItem[] | null; answer_with: string | null; approval?: boolean; tool?: string; detail?: string };
/** One thing the bot used during a turn, in plain words (`title`), with the app it belongs to (its name, or none). */
export type RunStep = { tool: string; title: string; app: string; ok: boolean };
export type RunLink = { url: string; title: string; kind: string };
/** A file of the bot's folders (on its rrotor) the run read or changed: its name alone, never what is in it. */
export type RunFile = { name: string; did: 'read' | 'written' | 'moved' };
/** An MCP App (`ui://…`) a step's tool result carries: its page (`html`, or read from the server by `uri`) and what it shows. */
export type RunApp = { step: string; uri: string; title: string; html: string | null; input: unknown; result: unknown };
/** An MCP App's page as `GET /v1/mcp-apps/resource` answers it (the server's own panels). */
export type McpResource = { uri: string; mimeType: string; text: string; _meta?: { ui?: { prefersBorder?: boolean } } };
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
  /** For a run with no words of its own (failed, cancelled, skipped, waiting): what happened, in a plain sentence. */
  summary?: string;
  /** What the bot used during the turn, in order, in plain words: the turn's "Ran N steps" fold. */
  steps?: RunStep[];
  /** Pages the run made or touched (a pull request, a Slack message, a doc, an app). */
  links?: RunLink[];
  /** MCP App UI resources its steps' tool results carry, shown inline in the turn. */
  apps?: RunApp[];
  /** On a rrotor: the files of its folders it read and changed, what it changed first. */
  files?: RunFile[];
  /** The org's rrotor it ran on; none for Glyphh cloud. */
  runs_on?: string | null;
  /** `project`: in the approvals queue, a project's pull request waiting for merge or reject (`project_slug` its project). */
  kind?: 'bot' | 'project';
  project_slug?: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
};
/** Asked against agreed: how often the person was asked, and how often Ada's own guess matched their answer. */
export type Agreement = { asked: number; agreed: number; rate: number | null };
/**
 * One gate as `GET /v1/bots/{slug}/gates` sends it (the SDK's `gate_stats`): its precedents in Ada, its outcomes,
 * who decided (Ada, the person, the default), how often it asks over the last runs, how often Ada's guess was right
 * when it asked, and how often it was overruled. Any field may be missing on an older runner.
 */
export type GateStat = {
  precedents?: number;
  outcomes?: string[];
  policy?: Record<string, unknown>;
  decisions?: { ada: number; person: number; default: number; total: number };
  ask_rate?: number | null;
  ask_rate_by_run?: { run: string; asked: number; of: number; rate: number | null }[];
  agreement?: Agreement;
  audit?: Agreement;
  shadow?: Agreement;
  overrules?: { wrong: number; audit: number; world: number; total: number };
  [k: string]: unknown;
};
export type GateStats = Record<string, GateStat>;
/** A gate's decision in one run (`run.data._gates`): one outcome, or for a gate over many items their summary. */
export type GateDecision = {
  outcome: string;
  by: string;
  p?: number | null;
  each?: boolean;
  asked?: number;
  decided?: number;
  defaulted?: number;
};
/** One item a gate over many items decided (`run.data[step].decisions`). */
export type ItemDecision = { n: number; label: string; outcome: string; by: string; p?: number | null };
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
  task?: string;
  examples?: string[];
  model?: string;
  permission_mode?: PermissionMode;
  effort?: Effort;
  voice?: string;
  spec?: BotSpec;
  skills?: Record<string, string>;
  connections?: BotScope[];
  schedule?: Schedule;
  runs_on?: string | null;
  folders?: BotFolder[];
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

/** The org's orchestrator: always there, changed like any bot, never deleted (the server answers 409, reason `orchestrator`). */
export const isOrchestrator = (bot: Pick<Bot, 'role'> | null | undefined): boolean => bot?.role === 'orchestrator';

export const working = (status: RunStatus | undefined) => status === 'queued' || status === 'running' || status === 'dispatched';

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

/** An MCP App's page, for a `ui://` resource of the server's own; a page never changes at its address, so it is kept. */
export const useMcpResource = (uri: string | null) =>
  useQuery({
    queryKey: ['mcp-apps', uri ?? ''] as const,
    enabled: uri !== null,
    queryFn: () => api.get<McpResource>(`/mcp-apps/resource?uri=${encodeURIComponent(uri!)}`),
    staleTime: Infinity,
  });
/** A connector tool called for an MCP App in the page (its host bridge's `tools/call`), as the person signed in. */
export const callMcpTool = (name: string, args: unknown) => api.post<Record<string, unknown>>('/mcp-apps/tools/call', { name, arguments: args ?? {} });

export const useBotKey = () => useQuery({ queryKey: botKeys.key, queryFn: () => api.get<BotKey>('/bot-key') });

export const useConnections = () =>
  useQuery({ queryKey: botKeys.connections, queryFn: async () => (await api.get<{ connections: Connection[] }>('/connections')).connections });
/** A connection's tools as a query, for a hook or for fetching them on the spot (a connection added to a bot). */
export const connectionToolsQuery = (id: string) => ({
  queryKey: botKeys.tools(id),
  queryFn: async () => (await api.get<{ tools: ConnectionTool[] }>(`/connections/${encodeURIComponent(id)}/tools`)).tools,
  staleTime: 5 * 60_000,
});
export const useConnectionTools = (id: string) => useQuery(connectionToolsQuery(id));

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


/** The SDK's problems with a bot the server would not take (422, `problems`), one a line; else none. */
export const problemsOf = (error: unknown): string[] => {
  if (!(error instanceof ApiError)) return [];
  const problems = error.detail.problems;
  return Array.isArray(problems) ? problems.map(String) : [];
};
