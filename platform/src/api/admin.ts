import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from './client';
import type { IsoDate, Uuid } from './types';

/**
 * What is left of Glyphh's staff view on the server (its /v1/admin, staff only, every call audited there): Glyphh's
 * own sites' traffic, the server's errors, and the audit log. The retired products' screens and their calls are gone;
 * the games' admin is the platform's own (/api/games, src/games).
 */

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

/** One part of a zone's pull: what its Cloudflare plan (and the token) allowed, and why not when it didn't. */
export type TrafficPart = { ok: boolean; days?: number; note?: string };
export type TrafficPoint = { day: string; requests: number; page_views: number; uniques: number; bytes: number; threats: number; cached_share: number | null };
export type TrafficTop = { host: string; key: string; n: number };
export type TrafficZone = {
  name: string;
  plan: string | null;
  pulled_at: IsoDate;
  available: Record<string, TrafficPart>;
  series: TrafficPoint[];
  hosts: Array<{ host: string; series: Array<{ day: string; requests: number; visits: number }> }>;
  countries: TrafficTop[];
  pages: TrafficTop[];
  referrers: TrafficTop[];
  rum_pages: TrafficTop[];
  rum_referrers: TrafficTop[];
};
export type TrafficPeriod = {
  days: number;
  visitors: number;
  page_views: number;
  previous_visitors: number;
  previous_page_views: number;
  visitors_change: number | null;
  page_views_change: number | null;
  sign_ups: number;
  conversion: number | null;
};
export type GitHubCounts = { views: number; view_uniques: number; clones: number; clone_uniques: number };
export type GitHubTop = { key: string; count: number; uniques: number };
/** A public repository's traffic from GitHub: its last 14 days as GitHub counts them, and each day kept since tracking began. */
export type GitHubRepo = {
  name: string;
  pulled_at: IsoDate;
  last_14: GitHubCounts;
  total: GitHubCounts;
  since: string | null;
  series: Array<GitHubCounts & { day: string }>;
  referrers: GitHubTop[];
  paths: GitHubTop[];
};
export type GitHubTraffic = { connected: boolean; repos: GitHubRepo[] };
/** Glyphh's own sites' traffic, from Cloudflare as the server's hourly pull kept it, and its public repositories' from GitHub. */
export type Traffic = {
  connected: boolean;
  pulled_at: IsoDate | null;
  days: number;
  since: string;
  last_7: TrafficPeriod;
  last_30: TrafficPeriod;
  zones: TrafficZone[];
  github: GitHubTraffic;
};

/** A query string from the values that are set. */
export function query(params: Record<string, string | number | boolean | null | undefined>): string {
  const found = Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== '' && v !== false);
  return found.length ? `?${new URLSearchParams(found.map(([k, v]) => [k, String(v)]))}` : '';
}

const admin = ['admin'] as const;
export const adminKeys = {
  all: admin,
  traffic: (days: number) => [...admin, 'traffic', days] as const,
  audit: (params: object) => [...admin, 'audit', params] as const,
  events: (params: object) => [...admin, 'events', params] as const,
};

export const useAdminTraffic = (days: number) =>
  useQuery({ queryKey: adminKeys.traffic(days), queryFn: () => api.get<Traffic>(`/admin/traffic?days=${days}`) });

export type AuditFilter = { by?: string; org_id?: string; action?: string; before?: string };
export const useAdminAudit = (params: AuditFilter) =>
  useQuery({ queryKey: adminKeys.audit(params), queryFn: () => api.get<AuditPage>(`/admin/audit${query(params)}`) });

export type EventFilter = { severity?: string; kind?: string; open_only?: boolean; before?: string };
export const useAdminEvents = (params: EventFilter) =>
  useQuery({ queryKey: adminKeys.events(params), queryFn: () => api.get<OpsEventPage>(`/admin/events${query(params)}`) });

/** After any staff action, everything shown is read again. */
function useAdminMutation<A, R = unknown>(fn: (args: A) => Promise<R>) {
  const client = useQueryClient();
  return useMutation({ mutationFn: fn, onSuccess: () => client.invalidateQueries({ queryKey: admin }) });
}

export const useAckEvent = () => useAdminMutation((id: string) => api.post(`/admin/events/${id}/ack`));
export const useAckEvents = () => useAdminMutation((body: { severity?: string; kind?: string }) => api.post<{ acknowledged: number }>('/admin/events/ack', body));
