import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, ApiError } from './client';
import type {
  AuditPage,
  Install,
  LogsPage,
  MetricsAnswer,
  Machine,
  MachineSize,
  Invite,
  LicenceKeys,
  Me,
  Member,
  Model,
  NewInvite,
  NewRuntimeKey,
  NewSelfRuntime,
  OfflineLicence,
  Org,
  Plan,
  Provider,
  Rates,
  HostingOff,
  Runtime,
  RuntimeKey,
  RuntimeNodes,
  SelfRuntime,
} from './types';

/** One key per server resource, so a write can refresh exactly what it changed. */
export const keys = {
  me: ['me'] as const,
  installs: ['installs'] as const,
  runtime: ['runtime'] as const,
  runtimeKeys: ['runtime', 'keys'] as const,
  machines: ['machines'] as const,
  selfRuntimes: ['runtimes', 'self'] as const,
  models: ['models'] as const,
  plans: ['plans'] as const,
  rates: ['rates'] as const,
  licenceKeys: ['license', 'keys'] as const,
  nodes: ['license', 'nodes'] as const,
  org: ['org'] as const,
  members: ['org', 'members'] as const,
  invites: ['org', 'invites'] as const,
  logs: ['telemetry', 'logs'] as const,
  audit: ['telemetry', 'audit'] as const,
  metrics: ['telemetry', 'metrics'] as const,
};

// Reads

export const useMe = () => useQuery({ queryKey: keys.me, queryFn: () => api.get<Me>('/me') });
export const useInstalls = () => useQuery({ queryKey: keys.installs, queryFn: () => api.get<Install[]>('/installs') });
export const useRuntime = () => useQuery({ queryKey: keys.runtime, queryFn: () => api.get<Runtime>('/runtime') });
export const useRuntimeKeys = () => useQuery({ queryKey: keys.runtimeKeys, queryFn: () => api.get<RuntimeKey[]>('/runtime/keys') });
export const useMachines = () => useQuery({ queryKey: keys.machines, queryFn: () => api.get<Machine[]>('/runtimes') });
export const useMachine = (id: string) =>
  useQuery({ queryKey: [...keys.machines, id], queryFn: () => api.get<Machine>(`/runtimes/${id}`) });
export const useSelfRuntimes = () => useQuery({ queryKey: keys.selfRuntimes, queryFn: () => api.get<SelfRuntime[]>('/runtimes/self') });
export const useModels = () => useQuery({ queryKey: keys.models, queryFn: () => api.get<Model[]>('/models') });
export const usePlans = () => useQuery({ queryKey: keys.plans, queryFn: () => api.get<Plan[]>('/plans') });
/**
 * The hosted machine rates; null while Glyphh hosts nothing: the server refuses them with `hosting_off`, or answers
 * `{hosting: "off"}` or no plans.
 */
export const useRates = () => useQuery({ queryKey: keys.rates, queryFn: readRates });

/** With hosting off the server refuses the rates (503 E_UNAVAILABLE `hosting_off`): that is no rates, not an error. */
export async function readRates(): Promise<Rates | null> {
  try {
    return hostedRates(await api.get<Rates | HostingOff>('/rates'));
  } catch (error) {
    if (error instanceof ApiError && error.code === 'E_UNAVAILABLE' && error.detail.reason === 'hosting_off') return null;
    throw error;
  }
}

export function hostedRates(answer: Rates | HostingOff): Rates | null {
  if ('hosting' in answer && answer.hosting === 'off') return null;
  const rates = answer as Rates;
  return rates.plans && Object.keys(rates.plans).length > 0 ? rates : null;
}

/**
 * Whether Glyphh hosts machines at all, from the rates alone: off when the server refuses them with `hosting_off`,
 * answers `{hosting: "off"}` or no plans (all read as null). A plan's `limits.machines` is its runtime nodes, hosted or
 * self-hosted, so it says nothing of hosting. On when the rates could not be read, so a page keeps its own refusal.
 */
export const hostingOn = (rates: Rates | null | undefined): boolean => rates !== null;

/** Undefined until the rates are read. */
export function useHosting(): boolean | undefined {
  const rates = useRates();
  if (rates.isPending) return undefined;
  return hostingOn(rates.data);
}
/** The org's licence keys, newest first, and the newest live one: none on Free. */
export const useLicenceKeys = () => useQuery({ queryKey: keys.licenceKeys, queryFn: () => api.get<LicenceKeys>('/license/keys') });
/** The org's runtime nodes against the plan's. */
export const useRuntimeNodes = () => useQuery({ queryKey: keys.nodes, queryFn: () => api.get<RuntimeNodes>('/license/nodes') });
export const useOrg = () => useQuery({ queryKey: keys.org, queryFn: () => api.get<Org>('/org') });
export const useMembers = () => useQuery({ queryKey: keys.members, queryFn: () => api.get<Member[]>('/org/members') });
export const useInvites = () => useQuery({ queryKey: keys.invites, queryFn: () => api.get<Invite[]>('/org/invites') });

// rrotor's opt-in telemetry: read live while its page is open.

/** How often the telemetry is read again while its page is open. */
export const liveEvery = 10_000;
/** Lines or events in a page. */
export const pageSize = 50;

/** How far back to look; '' is any time. */
export type Since = '' | '1h' | '24h' | '7d';
const sinceMs: Record<Exclude<Since, ''>, number> = { '1h': 3_600_000, '24h': 86_400_000, '7d': 7 * 86_400_000 };

/** The moment a window starts, counted back from `now`; undefined for any time. */
export function sinceAt(since: Since, now: Date = new Date()): string | undefined {
  return since ? new Date(now.getTime() - sinceMs[since]).toISOString() : undefined;
}

export type LogFilters = { runtime?: string; node?: string; level?: string; since?: Since; q?: string };
export type AuditFilters = { runtime?: string; node?: string; since?: Since; actor?: string; action?: string };

/** A telemetry path with its filters, leaving out the empty ones. The window starts when the page is read. */
export function telemetryPath(
  path: string,
  filters: Record<string, string | undefined>,
  cursor: string | null,
  now: Date = new Date(),
): string {
  const params = new URLSearchParams();
  for (const [name, value] of Object.entries(filters)) {
    const text = name === 'since' ? sinceAt((value ?? '') as Since, now) : value?.trim();
    if (text) params.set(name, text);
  }
  params.set('limit', String(pageSize));
  if (cursor) params.set('cursor', cursor);
  return `${path}?${params.toString()}`;
}

const pages = { initialPageParam: null as string | null, refetchInterval: liveEvery, staleTime: 0 } as const;
const nextOf = (page: { next?: string | null }) => page.next || null;

/** Log lines, newest first, a page at a time; older pages follow the server's cursor. */
export const useLogs = (filters: LogFilters) =>
  useInfiniteQuery({
    ...pages,
    queryKey: [...keys.logs, filters],
    queryFn: ({ pageParam }) => api.get<LogsPage>(telemetryPath('/telemetry/logs', filters, pageParam)),
    getNextPageParam: nextOf,
  });

/** Audit events, newest first, a page at a time. */
export const useAudit = (filters: AuditFilters) =>
  useInfiniteQuery({
    ...pages,
    queryKey: [...keys.audit, filters],
    queryFn: ({ pageParam }) => api.get<AuditPage>(telemetryPath('/telemetry/audit', filters, pageParam)),
    getNextPageParam: nextOf,
  });

/** Each node's latest metrics. */
export const useMetrics = () =>
  useQuery({ queryKey: keys.metrics, queryFn: () => api.get<MetricsAnswer>('/telemetry/metrics'), refetchInterval: liveEvery, staleTime: 0 });

// Writes

function useWrite<TArgs, TResult>(fn: (args: TArgs) => Promise<TResult>, refresh: ReadonlyArray<readonly string[]>) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: () => Promise.all(refresh.map((queryKey) => client.invalidateQueries({ queryKey }))),
  });
}

export const useStartRuntime = () => useWrite(() => api.post<Runtime>('/runtime/start'), [keys.runtime]);
export const useStopRuntime = () => useWrite(() => api.post<Runtime>('/runtime/stop'), [keys.runtime]);

// A person's first machine is also the old /v1/runtime, which Home reads; a change to any machine refreshes both.
const machineReads = [keys.machines, keys.runtime];
export const useCreateMachine = () =>
  useWrite((body: { name: string; size: MachineSize }) => api.post<Machine>('/runtimes', body), machineReads);
export const useStartMachine = () => useWrite((id: string) => api.post<Machine>(`/runtimes/${id}/start`), machineReads);
export const useStopMachine = () => useWrite((id: string) => api.post<Machine>(`/runtimes/${id}/stop`), machineReads);
export const useRestartMachine = () => useWrite((id: string) => api.post<Machine>(`/runtimes/${id}/restart`), machineReads);
export const useDeleteMachine = () =>
  useWrite(({ id, confirm }: { id: string; confirm: string }) => api.delete(`/runtimes/${id}?confirm=${encodeURIComponent(confirm)}`), machineReads);

export const useCreateRuntimeKey = () =>
  useWrite(
    (body: { name: string; expires_in_days: number | null }) =>
      api.post<NewRuntimeKey>('/runtime/keys', body.expires_in_days === null ? { name: body.name } : body),
    [keys.runtimeKeys],
  );
export const useRevokeRuntimeKey = () =>
  useWrite((id: string) => api.delete<RuntimeKey>(`/runtime/keys/${id}`), [keys.runtimeKeys]);

export const useDeleteRuntimeKey = () => useWrite((id: string) => api.delete(`/runtime/keys/${id}/record`), [keys.runtimeKeys]);

export const useRegisterSelfRuntime = () =>
  useWrite((body: { name: string; public_url: string }) => api.post<NewSelfRuntime>('/runtimes/self', body), [keys.selfRuntimes]);
export const useRotateSelfRuntimeToken = () =>
  useWrite((id: string) => api.post<{ token: string }>(`/runtimes/self/${id}/token`), [keys.selfRuntimes]);
export const useDeleteSelfRuntime = () => useWrite((id: string) => api.delete(`/runtimes/self/${id}`), [keys.selfRuntimes]);
export const useIssueOfflineLicence = () =>
  useWrite(({ id, days }: { id: string; days: number }) => api.post<OfflineLicence>(`/runtimes/${id}/offline-licence`, { days }), []);

export const useDeleteModel = () => useWrite((id: string) => api.delete(`/models/${id}`), [keys.models]);

export const useRenameMe = () => useWrite((name: string) => api.patch<Me>('/me', { name }), [keys.me]);
export const useLinkProvider = () =>
  useWrite((provider: Provider) => api.post<{ url: string }>('/me/identities', { provider }), []);
export const useUnlinkProvider = () =>
  useWrite((provider: Provider) => api.delete(`/me/identities/${provider}`), [keys.me]);
export const useSignOutInstall = () => useWrite((id: string) => api.delete(`/installs/${id}`), [keys.installs, keys.me]);

export const useRenameOrg = () => useWrite((name: string) => api.patch<Org>('/org', { name }), [keys.org, keys.me]);
export const useInvite = () => useWrite((email: string) => api.post<NewInvite>('/org/invites', { email }), [keys.invites, keys.org]);
export const useCancelInvite = () => useWrite((id: string) => api.delete(`/org/invites/${id}`), [keys.invites, keys.org]);
export const useRemoveMember = () => useWrite((id: string) => api.delete(`/org/members/${id}`), [keys.members, keys.org]);

export const useCheckout = () => useWrite((plan: string) => api.post<{ url: string }>('/billing/checkout', { plan }), []);
export const usePortal = () => useWrite(() => api.post<{ url: string }>('/billing/portal'), []);
// A new plan is a new licence key and a new count of runtime nodes.
export const useChangePlan = () =>
  useWrite((plan: string) => api.post<Org>('/billing/plan', { plan }), [keys.org, keys.me, keys.licenceKeys, keys.nodes]);
