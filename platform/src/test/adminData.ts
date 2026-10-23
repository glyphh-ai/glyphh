import type { AuditPage, Dashboard, Infra, OpsEventPage, OrgDetail, OrgPage, PeoplePage, PlanRow, SourceRow, AdaVersions, Traffic } from '@/api/admin';
import * as fixtures from './fixtures';

/** The staff view's answers, in the server's shapes (its /v1/admin). */

export const staffMe = { ...fixtures.me, email: 'support@glyphh.ai', staff: true };

const hours = (n: number) => Array.from({ length: n }, (_, i) => `20261023${String(i).padStart(2, '0')}`);
const p = (p50: number | null, p95: number | null, n = 0) => ({ n, p50, p95, p99: p95, mean: p50 });

export const dashboard: Dashboard = {
  days: 30,
  since: '2026-09-24',
  totals: { users: 412, orgs: 300, suspended_orgs: 2, active_orgs: 57, reads_month: 1_234_567, models: 88, precedents: 2_500_000 },
  series: [
    { day: '2026-10-22', new_users: 5, new_orgs: 4, active_orgs: 30, reads: 40_000, models_created: 2, conversions: 1 },
    { day: '2026-10-23', new_users: 7, new_orgs: 6, active_orgs: 33, reads: 41_000, models_created: 3, conversions: 0 },
  ],
  money: {
    mrr_cents: 1_234_500,
    paying_orgs: 41,
    contract_orgs: 3,
    trialing_orgs: 1,
    overage_cents_month: 2_300,
    plans: [
      { plan: 'Free', orgs: 250, paying: 0, mrr_cents: 0 },
      { plan: 'Pro', orgs: 40, paying: 38, mrr_cents: 376_200 },
    ],
  },
};

export const infra: Infra = {
  ada_cloud: true,
  alerts: [
    { code: 'tick_late', severity: 'critical', message: 'The minute tick last ran 9 minutes ago.' },
    { code: 'backlog_jobs', severity: 'warning', message: '25 waiting on jobs.' },
  ],
  thresholds: { tick_seconds: 300 },
  queues: [
    { stream: 'sync', length: 12, pending: 1, lag: 0, consumers: 4, alive: 4 },
    { stream: 'jobs', length: 30, pending: 2, lag: 23, consumers: 2, alive: 0 },
  ],
  tick: { last_at: '2026-10-23T10:00:00Z', age_seconds: 540 },
  read: { last_5m: p(12, 48, 300), last_hour: p(11, 52, 4_000), hourly: hours(24).map((hour) => ({ hour, latency: p(10, 40, 100) })) },
  api: { last_5m: p(20, 90, 50), last_hour: p(22, 95, 900), hourly: hours(24).map((hour) => ({ hour, latency: p(20, 80, 30) })) },
  http: {
    total: 4_900,
    c5xx: 49,
    routes: [
      { method: 'POST', route: '/v1/models/{name}/decide', total: 4_000, c4xx: 10, c5xx: 40 },
      { method: 'GET', route: '/v1/me', total: 900, c4xx: 0, c5xx: 0 },
    ],
    hourly: hours(24).map((hour) => ({ hour, total: 200, c5xx: 2 })),
  },
  jobs: [{ kind: 'import', total: 12, failed: 2, unfinished: 1, p50_seconds: 42, p95_seconds: 300 }],
  database: {
    size_bytes: 3_221_225_472,
    ada_bytes: 2_147_483_648,
    connections: { active: 3, idle: 9 },
    max_connections: 100,
    tables: [{ name: 'telemetry_logs', bytes: 524_288_000 }],
  },
  redis: { used_bytes: 52_428_800, peak_bytes: 62_914_560, max_bytes: 0, keys: 12_000 },
};

export const orgs: OrgPage = {
  orgs: [
    {
      id: 'o-acme',
      name: 'Acme',
      plan: 'Pro',
      plan_version: 2,
      billing_status: 'active',
      members: 3,
      models: 2,
      precedents: 41_000,
      reads_month: 120_000,
      source: 'reddit / cpc',
      created_at: '2026-10-01T09:00:00Z',
      first_paid_at: '2026-10-02T09:00:00Z',
      suspended: false,
    },
    {
      id: 'o-spam',
      name: 'Spam Co',
      plan: 'Free',
      plan_version: 3,
      billing_status: 'none',
      members: 1,
      models: 0,
      precedents: 0,
      reads_month: 0,
      source: null,
      created_at: '2026-10-20T09:00:00Z',
      first_paid_at: null,
      suspended: true,
    },
  ],
  total: 120,
  offset: 0,
  limit: 50,
};

const person = {
  id: 'u-ada',
  email: 'ada@acme.test',
  name: 'Ada Lovelace',
  role: 'admin' as const,
  org_id: 'o-acme',
  org_name: 'Acme',
  providers: ['google'],
  created_at: '2026-10-01T09:00:00Z',
  last_seen_at: null,
  source: { utm_source: 'reddit' },
};

export const people: PeoplePage = { people: [person], total: 1, offset: 0, limit: 50 };

export const org: OrgDetail = {
  account: {
    id: 'o-acme',
    name: 'Acme',
    created_at: '2026-10-01T09:00:00Z',
    plan: 'Pro',
    plan_version: 2,
    plan_version_id: 'pv-pro-2',
    billing_status: 'active',
    stripe_customer_id: 'cus_acme',
    stripe_subscription_id: 'sub_acme',
    renews_at: '2026-11-01T00:00:00Z',
    plan_until: null,
    first_paid_at: '2026-10-02T09:00:00Z',
    suspended_at: null,
    suspended_reason: null,
    source: { utm_source: 'reddit', utm_medium: 'cpc' },
  },
  members: [person],
  reads_month: 120_000,
  months: [{ period: '2026-10', reads: 120_000 }],
  days: [{ day: '2026-10-23', reads: 5_000 }],
  models: [
    { name: 'loans', created_at: '2026-10-03T09:00:00Z', deleted: false, active_version: 4, precedents: 40_000, ada: 'ada-1-0', kernel: '3.12.2' },
    { name: 'old', created_at: '2026-10-02T09:00:00Z', deleted: true, active_version: 1, precedents: 1_000, ada: null, kernel: null },
  ],
  jobs: [{ kind: 'import', state: 'failed', seconds: 3, created_at: '2026-10-22T09:00:00Z' }],
  api_keys: 2,
  licences: 0,
  audit: [
    { id: 'a1', at: '2026-10-23T10:00:00Z', staff_email: 'support@glyphh.ai', action: 'adminOrg', org_id: 'o-acme', target: '/v1/admin/orgs/o-acme', detail: {}, outcome: 'ok' },
  ],
};

const version = (id: string, n: number, newest: boolean, orgs: number) => ({
  id,
  version: n,
  price_cents: 9900,
  billing_interval: 'month' as const,
  stripe_price_id: `price_pro_${n}`,
  self_serve: true,
  max_machines: 3,
  precedents: 50_000,
  sync: true,
  ha: false,
  offline: false,
  sso: false,
  hosting_markup_pct: 20,
  cloud_precedents: 100_000,
  cloud_requests: 1_000_000,
  cloud_rps: 50,
  cloud_overage: true,
  created_at: '2026-10-01T00:00:00Z',
  orgs,
  newest,
});

export const plans: PlanRow[] = [
  { name: 'Pro', active: true, orgs: 40, versions: [version('pv-pro-2', 2, true, 30), version('pv-pro-1', 1, false, 10)] },
  { name: 'Enterprise', active: true, orgs: 3, versions: [{ ...version('pv-ent-1', 1, true, 3), price_cents: null, self_serve: false }] },
];

export const sources: SourceRow[] = [
  { source: 'reddit', medium: 'cpc', campaign: 'launch', people: 20, orgs: 18, paid: 3, paying: 2 },
  { source: '(none)', medium: '(none)', campaign: '(none)', people: 5, orgs: 0, paid: 0, paying: 0 },
];

export const adaVersions: AdaVersions = {
  versioned: false,
  versions: [{ ada: null, kernels: [], models: 88, orgs: 50, precedents: 2_500_000 }],
};

export const audit: AuditPage = { entries: org.audit, next_before: '2026-10-23T09:00:00Z' };

export const events: OpsEventPage = {
  events: [
    {
      id: 'e1',
      first_at: '2026-10-23T09:00:00Z',
      last_at: '2026-10-23T09:05:00Z',
      severity: 'error',
      kind: 'stripe',
      source: 'glyphh.billing',
      message: 'stripe call failed',
      detail: { path: '/subscriptions/sub_x' },
      org_id: 'o-acme',
      trace_id: 'trace-9',
      count: 3,
      acknowledged_at: null,
      acknowledged_by: null,
    },
    {
      id: 'e2',
      first_at: '2026-10-23T08:00:00Z',
      last_at: '2026-10-23T08:00:00Z',
      severity: 'warning',
      kind: 'worker',
      source: 'glyphh.ada',
      message: 'a worker stopped; starting another',
      detail: {},
      org_id: null,
      trace_id: null,
      count: 1,
      acknowledged_at: '2026-10-23T08:10:00Z',
      acknowledged_by: 'support@glyphh.ai',
    },
  ],
  next_before: null,
};

const point = (day: string, uniques: number) => ({ day, requests: uniques * 9, page_views: uniques * 3, uniques, bytes: 1000, threats: 0, cached_share: 0.4 });
const none = { pages: [], referrers: [], rum_pages: [], rum_referrers: [] };

/** glyphh.ai on a Free plan whose adaptive dataset gives hosts, pages and referrers; glyphh.app with Web Analytics only. */
export const traffic: Traffic = {
  connected: true,
  pulled_at: '2026-10-23T11:05:00Z',
  days: 30,
  since: '2026-09-24',
  last_7: { days: 7, visitors: 4_200, page_views: 9_000, previous_visitors: 3_500, previous_page_views: 9_500, visitors_change: 0.2, page_views_change: -0.0526, sign_ups: 42, conversion: 0.01 },
  last_30: { days: 30, visitors: 18_000, page_views: 40_000, previous_visitors: 0, previous_page_views: 0, visitors_change: null, page_views_change: null, sign_ups: 150, conversion: 0.0083 },
  zones: [
    {
      name: 'glyphh.ai',
      plan: 'Free Website',
      pulled_at: '2026-10-23T11:05:00Z',
      available: { daily: { ok: true, days: 60 }, hosts: { ok: true, days: 3 }, pages: { ok: true, days: 3 }, referrers: { ok: true, days: 3 }, rum: { ok: false, note: 'not authorized for that account' } },
      series: [point('2026-10-22', 600), point('2026-10-23', 700)],
      hosts: [
        { host: 'docs.glyphh.ai', series: [{ day: '2026-10-22', requests: 300, visits: 90 }, { day: '2026-10-23', requests: 320, visits: 95 }] },
        { host: 'glyphh.ai', series: [{ day: '2026-10-22', requests: 5_000, visits: 800 }, { day: '2026-10-23', requests: 5_200, visits: 850 }] },
      ],
      countries: [{ host: '', key: 'GB', n: 3_000 }, { host: '', key: 'US', n: 2_000 }],
      ...none,
      pages: [{ host: 'glyphh.ai', key: '/pricing', n: 700 }, { host: 'docs.glyphh.ai', key: '/quickstart', n: 120 }],
      referrers: [{ host: 'glyphh.ai', key: 'www.google.com', n: 400 }, { host: 'docs.glyphh.ai', key: 'github.com', n: 60 }],
    },
    {
      name: 'glyphh.app',
      plan: 'Free Website',
      pulled_at: '2026-10-23T10:05:00Z',
      available: { daily: { ok: true, days: 60 }, hosts: { ok: false, note: 'Not on this zone’s plan' }, pages: { ok: false }, referrers: { ok: false, note: 'unknown field' }, rum: { ok: true, days: 7 } },
      series: [point('2026-10-22', 50), point('2026-10-23', 60)],
      hosts: [],
      countries: [],
      ...none,
      rum_pages: [{ host: 'glyphh.app', key: '/sign-in', n: 30 }],
      rum_referrers: [{ host: 'glyphh.app', key: 'www.google.com', n: 10 }],
    },
  ],
  github: {
    connected: true,
    repos: [
      {
        name: 'glyphh-ai/glyphh',
        pulled_at: '2026-10-23T11:05:00Z',
        last_14: { views: 900, view_uniques: 310, clones: 120, clone_uniques: 45 },
        total: { views: 1_400, view_uniques: 520, clones: 200, clone_uniques: 77 },
        since: '2026-10-09',
        series: [
          { day: '2026-10-22', views: 60, view_uniques: 20, clones: 8, clone_uniques: 3 },
          { day: '2026-10-23', views: 70, view_uniques: 25, clones: 9, clone_uniques: 4 },
        ],
        referrers: [{ key: 'Google', count: 200, uniques: 80 }],
        paths: [{ key: '/glyphh-ai/glyphh', count: 600, uniques: 250 }],
      },
    ],
  },
};

/** Each GET of the staff view and its answer, for the page tests' fake server and the local one (dev/fake-server.ts). */
export const staffAnswers: Record<string, object> = {
  '/admin/dashboard': dashboard,
  '/admin/infra': infra,
  '/admin/orgs': orgs,
  '/admin/orgs/:id': org,
  '/admin/users': people,
  '/admin/plans': plans,
  '/admin/marketing': sources,
  '/admin/traffic': traffic,
  '/admin/ada-versions': adaVersions,
  '/admin/audit': audit,
  '/admin/events': events,
};
