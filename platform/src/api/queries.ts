import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from './client';
import type {
  App,
  AppPage,
  AppState,
  AppType,
  Billing,
  Install,
  LedgerEntry,
  LlmModel,
  LlmModelsAnswer,
  Payment,
  PlansAnswer,
  SeriesDay,
  TokenDay,
  Invite,
  LicenceKeys,
  Me,
  Member,
  NewInvite,
  NewRuntimeKey,
  NewSelfRuntime,
  OfflineLicence,
  Org,
  Plan,
  Provider,
  RuntimeKey,
  RuntimeNodes,
  SelfRuntime,
  Sso,
  SsoIn,
} from './types';

/**
 * One key per server resource, so a write can refresh exactly what it changed. Glyphh hosts no runtime: the server
 * grants licences to the rrotors a person runs, and keeps the ones registered to run at their own address.
 */
export const keys = {
  me: ['me'] as const,
  installs: ['installs'] as const,
  runtimeKeys: ['runtime', 'keys'] as const,
  selfRuntimes: ['runtimes', 'self'] as const,
  plans: ['plans'] as const,
  licenceKeys: ['license', 'keys'] as const,
  nodes: ['license', 'nodes'] as const,
  org: ['org'] as const,
  members: ['org', 'members'] as const,
  invites: ['org', 'invites'] as const,
  sso: ['org', 'sso'] as const,
  apps: ['apps'] as const,
  billing: ['billing'] as const,
  ledger: ['billing', 'ledger'] as const,
  series: ['billing', 'series'] as const,
  payment: ['billing', 'payment'] as const,
  tokenDays: ['llm', 'usage'] as const,
  llmModels: ['llm', 'models'] as const,
};

// Reads

export const useMe = () => useQuery({ queryKey: keys.me, queryFn: () => api.get<Me>('/me') });
export const useInstalls = () => useQuery({ queryKey: keys.installs, queryFn: () => api.get<Install[]>('/installs') });
export const useRuntimeKeys = () => useQuery({ queryKey: keys.runtimeKeys, queryFn: () => api.get<RuntimeKey[]>('/runtime/keys') });
export const useSelfRuntimes = () => useQuery({ queryKey: keys.selfRuntimes, queryFn: () => api.get<SelfRuntime[]>('/runtimes/self') });
/** `GET /v1/plans` read alike as a list of plans or `{plans, models}`: the plans, and the hosted models' rates if any. */
export const readPlans = (answer: PlansAnswer): { plans: Plan[]; models: LlmModel[] | null } =>
  Array.isArray(answer) ? { plans: answer, models: null } : { plans: answer.plans, models: answer.models ?? null };
const plansQuery = { queryKey: keys.plans, queryFn: async () => readPlans(await api.get<PlansAnswer>('/plans')) };
export const usePlans = () => useQuery({ ...plansQuery, select: (answer) => answer.plans });

/**
 * The hosted models and their rates: from `GET /v1/plans` when it carries them, else `GET /v1/llm/models`. None (an
 * empty list) while hosted models are off: the registry refused or missing is no error to show.
 */
export function useLlmModels() {
  const plans = useQuery({ ...plansQuery, select: (answer) => answer.models });
  const registry = useQuery({
    queryKey: keys.llmModels,
    enabled: plans.isSuccess && plans.data === null,
    queryFn: async () => {
      try {
        const answer = await api.get<LlmModelsAnswer>('/llm/models');
        return Array.isArray(answer) ? answer : answer.models;
      } catch {
        return [];
      }
    },
  });
  return plans.data ?? registry.data ?? [];
}

/** The org's billing and use; with hosted models on, its tokens this month and its overage balance. */
export const useBilling = () => useQuery({ queryKey: keys.billing, queryFn: () => api.get<Billing>('/billing') });
/** Each model's tokens by day, the last `days` days, UTC; only asked for while hosted models are on. */
export const useTokenDays = (days: number, enabled: boolean) =>
  useQuery({
    queryKey: [...keys.tokenDays, days],
    enabled,
    queryFn: async () => (await api.get<{ days: TokenDay[] }>(`/llm/usage?days=${days}`)).days,
  });
/** The org's use by UTC day, the last `days` days, one a day: Ada reads, bot runs, charges and connections. */
export const useUsageSeries = (days: number) =>
  useQuery({
    queryKey: [...keys.series, days],
    queryFn: async () => (await api.get<{ days: SeriesDay[] }>(`/billing/series?days=${days}`)).days,
  });
/** The card on file and the invoices, from Stripe through the server; the admin's, so asked only for them. */
export const usePayment = (enabled: boolean) => useQuery({ queryKey: keys.payment, enabled, queryFn: () => api.get<Payment>('/billing/payment') });
/** The balance's movements, newest first: top-ups, charges, grants and refunds. */
export const useLedger = (enabled: boolean, limit = 50) =>
  useQuery({
    queryKey: [...keys.ledger, limit],
    enabled,
    queryFn: async () => (await api.get<{ entries: LedgerEntry[] }>(`/billing/ledger?limit=${limit}`)).entries,
  });
/** The org's licence keys, newest first, and the newest live one: none on Free. */
export const useLicenceKeys = () => useQuery({ queryKey: keys.licenceKeys, queryFn: () => api.get<LicenceKeys>('/license/keys') });
/** The org's runtime nodes against the plan's. */
export const useRuntimeNodes = () => useQuery({ queryKey: keys.nodes, queryFn: () => api.get<RuntimeNodes>('/license/nodes') });
export const useOrg = () => useQuery({ queryKey: keys.org, queryFn: () => api.get<Org>('/org') });
export const useMembers = () => useQuery({ queryKey: keys.members, queryFn: () => api.get<Member[]>('/org/members') });
export const useInvites = () => useQuery({ queryKey: keys.invites, queryFn: () => api.get<Invite[]>('/org/invites') });
/** The org's single sign-on, or null when it has none. */
export const useSso = () => useQuery({ queryKey: keys.sso, queryFn: () => api.get<Sso | null>('/org/sso') });

export type AppsQuery = { q?: string; page?: number; state?: AppState; type?: AppType };

/** A page of the org's apps: the approved ones the person's roles allow, or for a reviewer any state; one type, or every type. */
export const useApps = ({ q = '', page = 1, state = 'approved', type }: AppsQuery) =>
  useQuery({
    queryKey: [...keys.apps, { q, page, state, type: type ?? null }],
    queryFn: () => {
      const params = new URLSearchParams({ page: String(page), per_page: '24', state });
      if (q) params.set('q', q);
      if (type) params.set('type', type);
      return api.get<AppPage>(`/apps?${params}`);
    },
    placeholderData: (previous) => previous,
  });

// Writes

function useWrite<TArgs, TResult>(fn: (args: TArgs) => Promise<TResult>, refresh: ReadonlyArray<readonly string[]>) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: () => Promise.all(refresh.map((queryKey) => client.invalidateQueries({ queryKey }))),
  });
}

/** A key calls one of the person's self-hosted runtimes (`runtime_id`); with no expiry it never expires. */
export const useCreateRuntimeKey = () =>
  useWrite(
    ({ expires_in_days, ...body }: { name: string; runtime_id: string; expires_in_days: number | null }) =>
      api.post<NewRuntimeKey>('/runtime/keys', expires_in_days === null ? body : { ...body, expires_in_days }),
    [keys.runtimeKeys],
  );
export const useRevokeRuntimeKey = () =>
  useWrite((id: string) => api.delete<RuntimeKey>(`/runtime/keys/${id}`), [keys.runtimeKeys]);

export const useDeleteRuntimeKey = () => useWrite((id: string) => api.delete(`/runtime/keys/${id}/record`), [keys.runtimeKeys]);

// A runtime registered or deleted changes the nodes counted against the plan, and its keys go with it.
export const useRegisterSelfRuntime = () =>
  useWrite((body: { name: string; public_url: string }) => api.post<NewSelfRuntime>('/runtimes/self', body), [keys.selfRuntimes, keys.nodes]);
export const useRotateSelfRuntimeToken = () =>
  useWrite((id: string) => api.post<{ token: string }>(`/runtimes/self/${id}/token`), [keys.selfRuntimes]);
export const useDeleteSelfRuntime = () =>
  useWrite((id: string) => api.delete(`/runtimes/self/${id}`), [keys.selfRuntimes, keys.nodes, keys.runtimeKeys]);
export const useIssueOfflineLicence = () =>
  useWrite(({ id, days }: { id: string; days: number }) => api.post<OfflineLicence>(`/runtimes/${id}/offline-licence`, { days }), []);

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
export const useSetSso = () => useWrite((body: SsoIn) => api.put<Sso>('/org/sso', body), [keys.sso]);
export const useRemoveSso = () => useWrite(() => api.delete('/org/sso'), [keys.sso]);

// A review changes which list an app is in: every page is read again.
export const useApproveApp = () => useWrite((id: string) => api.post<App>(`/apps/${id}/approve`), [keys.apps]);
export const useRejectApp = () => useWrite(({ id, reason }: { id: string; reason: string }) => api.post<App>(`/apps/${id}/reject`, { reason }), [keys.apps]);
export const useRetireApp = () => useWrite((id: string) => api.post<App>(`/apps/${id}/retire`), [keys.apps]);

export const useCheckout = () => useWrite((plan: string) => api.post<{ url: string }>('/billing/checkout', { plan }), []);
/** Stripe Checkout's page to add `amount_cents` ($10 to $1,000) to the overage balance; it is credited once Stripe says paid. */
export const useTopUp = () => useWrite((amount_cents: number) => api.post<{ url: string }>('/billing/topup', { amount_cents }), []);
export const usePortal = () => useWrite(() => api.post<{ url: string }>('/billing/portal'), []);
/** Stripe's page to add or replace the card on file. */
export const useChangeCard = () => useWrite(() => api.post<{ url: string }>('/billing/card'), []);
// A new plan is a new licence key and a new count of runtime nodes.
export const useChangePlan = () =>
  useWrite((plan: string) => api.post<Org>('/billing/plan', { plan }), [keys.org, keys.me, keys.licenceKeys, keys.nodes]);
