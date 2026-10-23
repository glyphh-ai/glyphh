import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from './client';
import type { IsoDate, Uuid } from './types';

/**
 * Glyphh's staff view (the server's /v1/admin, staff only, every call audited there): account and usage metadata
 * across every org, the server's health and its errors. Never a customer's precedents, cases, specs or files.
 */

export type Percentiles = { n: number; p50: number | null; p95: number | null; p99: number | null; mean: number | null };
export type Alert = { code: string; severity: 'warning' | 'critical'; message: string };

export type DashboardDay = {
  day: string;
  new_users: number;
  new_orgs: number;
  active_orgs: number;
  reads: number;
  models_created: number;
  conversions: number;
};

export type PlanMix = { plan: string; orgs: number; paying: number; mrr_cents: number };

export type Dashboard = {
  days: number;
  since: string;
  totals: { users: number; orgs: number; suspended_orgs: number; active_orgs: number; reads_month: number; models: number; precedents: number };
  series: DashboardDay[];
  money: {
    mrr_cents: number;
    paying_orgs: number;
    contract_orgs: number;
    trialing_orgs: number;
    overage_cents_month: number;
    plans: PlanMix[];
  };
};

export type Queue = { stream: string; length: number; pending: number; lag: number; consumers: number; alive: number };
export type Latency = { last_5m: Percentiles; last_hour: Percentiles; hourly: Array<{ hour: string; latency: Percentiles }> };
export type Endpoint = { method: string; route: string; total: number; c4xx: number; c5xx: number };

export type Infra = {
  ada_cloud: boolean;
  alerts: Alert[];
  thresholds: Record<string, number>;
  queues: Queue[];
  tick: { last_at: IsoDate | null; age_seconds: number | null };
  read: Latency;
  api: Latency;
  http: { total: number; c5xx: number; routes: Endpoint[]; hourly: Array<{ hour: string; total: number; c5xx: number }> };
  jobs: Array<{ kind: string; total: number; failed: number; unfinished: number; p50_seconds: number | null; p95_seconds: number | null }>;
  database: {
    size_bytes: number;
    ada_bytes: number;
    connections: Record<string, number>;
    max_connections: number;
    tables: Array<{ name: string; bytes: number }>;
  };
  redis: { used_bytes: number; peak_bytes: number; max_bytes: number; keys: number };
};

export type OrgRow = {
  id: Uuid;
  name: string;
  plan: string;
  plan_version: number;
  billing_status: string;
  members: number;
  models: number;
  precedents: number;
  reads_month: number;
  source: string | null;
  created_at: IsoDate;
  first_paid_at: IsoDate | null;
  suspended: boolean;
};

export type Page<K extends string, T> = { [key in K]: T[] } & { total: number; offset: number; limit: number };
export type OrgPage = Page<'orgs', OrgRow>;

export type Source = Partial<Record<'utm_source' | 'utm_medium' | 'utm_campaign' | 'utm_content' | 'utm_term' | 'gclid' | 'fbclid' | 'rdt_cid' | 'landing', string>>;

export type Person = {
  id: Uuid;
  email: string;
  name: string | null;
  role: 'admin' | 'member';
  org_id: Uuid;
  org_name: string;
  providers: string[];
  created_at: IsoDate;
  last_seen_at: IsoDate | null;
  source: Source | null;
};
export type PeoplePage = Page<'people', Person>;

export type AdaModelMeta = { name: string; created_at: IsoDate; deleted: boolean; active_version: number; precedents: number; ada: string | null; kernel: string | null };
export type AdaJobMeta = { kind: string; state: string; seconds: number | null; created_at: IsoDate };

export type AuditEntry = {
  id: Uuid;
  at: IsoDate;
  staff_email: string;
  action: string;
  org_id: Uuid | null;
  target: string | null;
  detail: Record<string, unknown>;
  outcome: string;
};
export type AuditPage = { entries: AuditEntry[]; next_before: IsoDate | null };

export type OrgDetail = {
  account: {
    id: Uuid;
    name: string;
    created_at: IsoDate;
    plan: string;
    plan_version: number;
    plan_version_id: Uuid;
    billing_status: string;
    stripe_customer_id: string | null;
    stripe_subscription_id: string | null;
    renews_at: IsoDate | null;
    plan_until: IsoDate | null;
    first_paid_at: IsoDate | null;
    suspended_at: IsoDate | null;
    suspended_reason: string | null;
    source: Source | null;
  };
  members: Person[];
  reads_month: number;
  months: Array<{ period: string; reads: number }>;
  days: Array<{ day: string; reads: number }>;
  models: AdaModelMeta[];
  jobs: AdaJobMeta[];
  api_keys: number;
  licences: number;
  audit: AuditEntry[];
};

export type PlanVersionRow = {
  id: Uuid;
  version: number;
  price_cents: number | null;
  billing_interval: 'month' | 'year' | null;
  stripe_price_id: string | null;
  self_serve: boolean;
  max_machines: number | null;
  precedents: number | null;
  sync: boolean;
  ha: boolean;
  offline: boolean;
  sso: boolean;
  hosting_markup_pct: number | null;
  cloud_precedents: number | null;
  cloud_requests: number | null;
  cloud_rps: number | null;
  cloud_overage: boolean;
  created_at: IsoDate;
  orgs: number;
  newest: boolean;
};
export type PlanRow = { name: string; active: boolean; orgs: number; versions: PlanVersionRow[] };

export type SourceRow = { source: string; medium: string; campaign: string; people: number; orgs: number; paid: number; paying: number };
export type AdaVersions = { versioned: boolean; versions: Array<{ ada: string | null; kernels: string[]; models: number; orgs: number; precedents: number }> };

export type OpsEvent = {
  id: Uuid;
  first_at: IsoDate;
  last_at: IsoDate;
  severity: 'warning' | 'error' | 'critical';
  kind: string;
  source: string;
  message: string;
  detail: Record<string, unknown>;
  org_id: Uuid | null;
  trace_id: string | null;
  count: number;
  acknowledged_at: IsoDate | null;
  acknowledged_by: string | null;
};
export type OpsEventPage = { events: OpsEvent[]; next_before: IsoDate | null };

/** A query string from the values that are set. */
export function query(params: Record<string, string | number | boolean | null | undefined>): string {
  const found = Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== '' && v !== false);
  return found.length ? `?${new URLSearchParams(found.map(([k, v]) => [k, String(v)]))}` : '';
}

const admin = ['admin'] as const;
export const adminKeys = {
  all: admin,
  dashboard: (days: number) => [...admin, 'dashboard', days] as const,
  infra: [...admin, 'infra'] as const,
  orgs: (params: object) => [...admin, 'orgs', params] as const,
  org: (id: string) => [...admin, 'org', id] as const,
  users: (params: object) => [...admin, 'users', params] as const,
  plans: [...admin, 'plans'] as const,
  marketing: (days: number) => [...admin, 'marketing', days] as const,
  adaVersions: [...admin, 'ada-versions'] as const,
  audit: (params: object) => [...admin, 'audit', params] as const,
  events: (params: object) => [...admin, 'events', params] as const,
};

export const useAdminDashboard = (days: number) =>
  useQuery({ queryKey: adminKeys.dashboard(days), queryFn: () => api.get<Dashboard>(`/admin/dashboard?days=${days}`) });
export const useAdminInfra = () => useQuery({ queryKey: adminKeys.infra, queryFn: () => api.get<Infra>('/admin/infra') });

export type OrgFilter = { q?: string; plan?: string; offset?: number };
export const useAdminOrgs = (params: OrgFilter) =>
  useQuery({ queryKey: adminKeys.orgs(params), queryFn: () => api.get<OrgPage>(`/admin/orgs${query({ ...params, limit: 50 })}`), placeholderData: keepPreviousData });
export const useAdminOrg = (id: string) => useQuery({ queryKey: adminKeys.org(id), queryFn: () => api.get<OrgDetail>(`/admin/orgs/${id}`) });

export type PeopleFilter = { q?: string; provider?: string; offset?: number };
export const useAdminUsers = (params: PeopleFilter) =>
  useQuery({ queryKey: adminKeys.users(params), queryFn: () => api.get<PeoplePage>(`/admin/users${query({ ...params, limit: 50 })}`), placeholderData: keepPreviousData });
export const useAdminPlans = () => useQuery({ queryKey: adminKeys.plans, queryFn: () => api.get<PlanRow[]>('/admin/plans') });
export const useAdminMarketing = (days: number) =>
  useQuery({ queryKey: adminKeys.marketing(days), queryFn: () => api.get<SourceRow[]>(`/admin/marketing?days=${days}`) });
export const useAdminAdaVersions = () => useQuery({ queryKey: adminKeys.adaVersions, queryFn: () => api.get<AdaVersions>('/admin/ada-versions') });

export type AuditFilter = { by?: string; org_id?: string; action?: string; before?: string };
export const useAdminAudit = (params: AuditFilter) =>
  useQuery({ queryKey: adminKeys.audit(params), queryFn: () => api.get<AuditPage>(`/admin/audit${query(params)}`) });

export type EventFilter = { severity?: string; kind?: string; open_only?: boolean; before?: string };
export const useAdminEvents = (params: EventFilter) =>
  useQuery({ queryKey: adminKeys.events(params), queryFn: () => api.get<OpsEventPage>(`/admin/events${query(params)}`) });

/** After any staff action, everything shown is read again: the audit log, the org, the lists. */
function useAdminMutation<A, R = unknown>(fn: (args: A) => Promise<R>) {
  const client = useQueryClient();
  return useMutation({ mutationFn: fn, onSuccess: () => client.invalidateQueries({ queryKey: admin }) });
}

export const useAckEvent = () => useAdminMutation((id: string) => api.post(`/admin/events/${id}/ack`));
export const useAckEvents = () => useAdminMutation((body: { severity?: string; kind?: string }) => api.post<{ acknowledged: number }>('/admin/events/ack', body));
export const useChangePlan = (org: string) => useAdminMutation((plan_version_id: string) => api.post<{ message: string }>(`/admin/orgs/${org}/plan`, { plan_version_id }));
export const useSuspend = (org: string) => useAdminMutation((reason: string) => api.post(`/admin/orgs/${org}/suspend`, { reason }));
export const useUnsuspend = (org: string) => useAdminMutation(() => api.delete(`/admin/orgs/${org}/suspend`));
export const useGrantEnterprise = (org: string) =>
  useAdminMutation((body: { until: string; subscription: string; markup: number | null }) => api.post<{ message: string }>(`/admin/orgs/${org}/enterprise`, body));
export const useRevokeEnterprise = (org: string) => useAdminMutation(() => api.delete<{ message: string }>(`/admin/orgs/${org}/enterprise`));
