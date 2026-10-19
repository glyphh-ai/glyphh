import type {
  AuditEvent,
  HostingOff,
  Install,
  Invite,
  LogLine,
  LicenceKey,
  LicenceKeys,
  Machine,
  MachineSize,
  Me,
  Member,
  Model,
  Org,
  Plan,
  Rates,
  Runtime,
  RuntimeMetrics,
  RuntimeKey,
  RuntimeNodes,
  SelfRuntime,
} from '@/api/types';

/**
 * One org's data in the server's shapes, shared by the page tests and the local fake server: with hosting on and Pro
 * and Team for sale (`GLYPHH_HOSTING=on`, sync shipped), and below, `hostingOff`, as the server answers today.
 */

// The server's four flags; roles and audit logs ride on sso. With hosting on, as if every feature were built.
const none = { sync: false, ha: false, offline: false, sso: false };
const built = { sync: true, ha: true, offline: true, sso: true };

export const plans: Plan[] = [
  { name: 'Free', version: 1, price_cents: 0, interval: null, self_serve: true, limits: { machines: 1, precedents: 5_000 }, features: none, built, markup_hidden: true },
  { name: 'Pro', version: 1, price_cents: 9900, interval: 'month', self_serve: true, limits: { machines: 3, precedents: 50_000 }, features: { ...none, sync: true }, built, markup_hidden: true },
  { name: 'Team', version: 1, price_cents: 29900, interval: 'month', self_serve: true, limits: { machines: 10, precedents: 500_000 }, features: { ...none, sync: true }, built, markup_hidden: true },
  {
    name: 'Enterprise',
    version: 1,
    price_cents: null,
    interval: null,
    self_serve: false,
    limits: { machines: null, precedents: null },
    features: { sync: true, ha: true, offline: true, sso: true },
    built,
    markup_hidden: true,
  },
];

const pro = plans[1]!;

export const me: Me = {
  id: 'u-chris',
  email: 'chris@example.com',
  name: 'Chris Timmerman',
  role: 'admin',
  providers: ['github', 'google'],
  org: { id: 'o-1', name: 'Glyphh', billing_status: 'active', renews_at: '2026-11-16T00:00:00Z', plan_until: null },
  plan: pro,
  precedents: { used: 18_240, limit: 50_000 },
  hosting: {
    month: '2026-10',
    month_to_date_cents: 1217,
    machines: [
      { id: 'rt-7f3a9c', name: 'Main', size: 'small', cents: 412 },
      { id: 'rt-2b8e41', name: 'Experiments', size: 'large', cents: 805 },
    ],
  },
};

/** Per second is the month's rate over a 30-day month. */
const rate = (size: MachineSize, usd_per_month: number) => ({ size, usd_per_month, usd_per_second: usd_per_month / 2_592_000 });

export const rates: Rates = {
  effective_from: '2026-10-18',
  source: 'https://docs.fly.io/about/pricing',
  sizes: [
    { ...rate('small', 6.7), cpu_kind: 'shared', cpus: 1, memory_mb: 1024, volume_gb: 3 },
    { ...rate('medium', 25.39), cpu_kind: 'shared', cpus: 2, memory_mb: 4096, volume_gb: 10 },
    { ...rate('large', 90), cpu_kind: 'performance', cpus: 2, memory_mb: 8192, volume_gb: 20 },
  ],
  volume_usd_per_gb_month: 0.15,
  // Enterprise's rates are set in each customer's contract, so it has none here.
  plans: {
    Pro: { sizes: [rate('small', 8.71), rate('medium', 33.01), rate('large', 117)], volume_usd_per_gb_month: 0.2 },
    Team: { sizes: [rate('small', 8.71), rate('medium', 33.01), rate('large', 117)], volume_usd_per_gb_month: 0.2 },
  },
};

export const org: Org = {
  id: 'o-1',
  name: 'Glyphh',
  admin_user_id: 'u-chris',
  plan: pro,
  members: 1,
  billing_status: 'active',
};

export const runtime: Runtime = {
  runtime_id: 'rt-7f3a9c',
  address: 'https://chris-7f3a.glyphh.app',
  state: 'online',
  region: 'lhr',
  image_version: '1.4.2',
  last_seen_at: '2026-10-16T13:58:00Z',
  seconds_used: 12 * 3600 + 1200,
};

export const machines: Machine[] = [
  {
    id: 'rt-7f3a9c',
    name: 'Main',
    size: 'small',
    state: 'online',
    address: 'https://chris-7f3a.glyphh.app',
    month_seconds: 12 * 3600 + 1200,
    created_at: '2026-08-01T09:00:00Z',
  },
  {
    id: 'rt-2b8e41',
    name: 'Experiments',
    size: 'large',
    state: 'stopped',
    address: 'https://chris-2b8e.glyphh.app',
    month_seconds: 3 * 3600,
    created_at: '2026-10-10T15:00:00Z',
  },
];

export const runtimeKeys: RuntimeKey[] = [
  { id: 'k-1', name: 'Billing worker', created_at: '2026-10-02T09:00:00Z', expires_at: '2027-10-02T09:00:00Z', revoked_at: null, calls: 1284, last_used_at: '2026-10-16T13:55:00Z' },
  { id: 'k-2', name: 'Support bot', created_at: '2026-10-09T15:30:00Z', expires_at: '2026-10-12T15:30:00Z', revoked_at: null, calls: 1, last_used_at: '2026-10-10T08:00:00Z' },
  { id: 'k-3', name: 'Old script', created_at: '2026-09-12T11:00:00Z', expires_at: '2026-12-11T11:00:00Z', revoked_at: '2026-10-01T08:00:00Z', calls: 0, last_used_at: null },
];

export const selfRuntimes: SelfRuntime[] = [
  {
    id: 'rt-self-1',
    name: 'Acme production',
    public_url: 'https://rrotor.acme.com',
    state: 'online',
    version: '1.4.2',
    last_seen_at: '2026-10-16T13:50:00Z',
    last_heartbeat_at: '2026-10-16T06:00:00Z',
  },
  {
    id: 'rt-self-2',
    name: 'Lab',
    public_url: 'https://rrotor.lab.acme.com',
    state: 'stopped',
    version: null,
    last_seen_at: null,
    last_heartbeat_at: null,
  },
];

export const models: Model[] = [
  {
    id: 'm-1',
    name: 'invoice-triage',
    repo: 'glyphh-ai/invoice-triage',
    created_at: '2026-09-20T10:00:00Z',
    versions: [
      { id: 'v-1', version: 1, commit_sha: '3f9c2ab71d', created_at: '2026-09-20T10:00:00Z', active_on: [] },
      { id: 'v-2', version: 2, commit_sha: '8be41c0f2a', created_at: '2026-10-11T16:20:00Z', active_on: ['rt-7f3a9c'] },
    ],
  },
];

/** As the server signs one: the payload's JSON and a signature, each base64url without padding. */
const base64url = (text: string) => btoa(text).replaceAll('+', '-').replaceAll('/', '_').replace(/=+$/, '');
function licenceKey(terms: Omit<LicenceKey, 'state' | 'key' | 'revoked_at'>, state: LicenceKey['state'], revoked_at: string | null = null): LicenceKey {
  const payload = { ...terms, customer_id: 'o-1' };
  return { ...terms, revoked_at, state, key: `${base64url(JSON.stringify(payload))}.${base64url(`signature-${terms.license_id}`)}` };
}

const proTerms = { tier: 'pro', max_nodes: 3, max_precedents: 50_000, cluster_sync_enabled: true };

/** One key per paid month, newest first: this month's live, last month's expired, and one from a subscription that ended. */
export const licenceKeys: LicenceKeys = (() => {
  const keys = [
    licenceKey({ license_id: 'lk-3', ...proTerms, issued_at: '2026-10-16T00:00:04Z', expires_at: '2026-11-16T00:00:00Z' }, 'live'),
    licenceKey({ license_id: 'lk-2', ...proTerms, issued_at: '2026-09-16T00:00:03Z', expires_at: '2026-10-16T00:00:00Z' }, 'expired'),
    licenceKey(
      { license_id: 'lk-1', tier: 'team', max_nodes: 10, max_precedents: 500_000, cluster_sync_enabled: true, issued_at: '2026-08-02T09:00:00Z', expires_at: '2026-09-02T09:00:00Z' },
      'revoked',
      '2026-08-20T12:00:00Z',
    ),
  ];
  return { license_key: keys[0]!.key, keys };
})();

/** Pro's three nodes: the hosted machine (it names no node, so counts as one) and a self-hosted cluster of two. */
export const nodes: RuntimeNodes = {
  count: 3,
  max_nodes: 3,
  over: false,
  nodes: [
    { runtime_id: 'rt-self-1', runtime: 'Acme production', mode: 'self', node_id: 'rrotor-1', cluster_id: 'c-1', role: 'head', precedents: 12_050, version: '1.4.2', seen_at: '2026-10-16T13:50:00Z' },
    { runtime_id: 'rt-self-1', runtime: 'Acme production', mode: 'self', node_id: 'rrotor-2', cluster_id: 'c-1', role: 'follower', precedents: 12_050, version: '1.4.2', seen_at: '2026-10-16T13:49:00Z' },
    { runtime_id: 'rt-7f3a9c', runtime: 'Main', mode: 'hosted', node_id: null, cluster_id: null, role: null, precedents: 18_240, version: '1.4.2', seen_at: '2026-10-16T13:58:00Z' },
  ],
};

export const members: Member[] = [{ id: 'u-chris', email: 'chris@example.com', name: 'Chris Timmerman', role: 'admin', joined_at: '2026-07-05T12:00:00Z' }];

export const invites: Invite[] = [];

export const installs: Install[] = [
  {
    id: 'i-1',
    machine_id: 'mac-1',
    name: 'studio-mac',
    surface: 'Claude Code',
    mod_version: '0.9.3',
    last_seen_at: '2026-10-16T13:40:00Z',
    created_at: '2026-08-01T09:00:00Z',
    current: false,
  },
  {
    id: 'i-2',
    machine_id: 'mac-2',
    name: 'laptop',
    surface: 'Claude Desktop',
    mod_version: '0.9.3',
    last_seen_at: '2026-10-14T18:05:00Z',
    created_at: '2026-09-03T09:00:00Z',
    current: false,
  },
];

/**
 * rrotor's opt-in telemetry, as the server passes it on with `RROTOR_SERVER_LOGS=on` on the self-hosted cluster. By
 * default a runtime sends none and each list is empty. Newest first.
 */
const acme = { runtime_id: 'rt-self-1', runtime: 'Acme production' };
export const logs: LogLine[] = [
  { at: '2026-10-16T13:58:12Z', ...acme, node_id: 'rrotor-1', level: 'error', message: 'Sync to rrotor-2 failed: connection reset', attributes: { peer: 'rrotor-2', attempt: 3 } },
  { at: '2026-10-16T13:57:40Z', ...acme, node_id: 'rrotor-2', level: 'warn', message: 'Precedents at 90% of the cap', attributes: { precedents: 45_000, cap: 50_000 } },
  { at: '2026-10-16T13:55:03Z', ...acme, node_id: 'rrotor-1', level: 'info', message: 'Model credit-risk v4 active', attributes: {} },
  { at: '2026-10-16T13:50:00Z', ...acme, node_id: 'rrotor-1', level: 'debug', message: 'Heartbeat sent' },
];

export const auditEvents: AuditEvent[] = [
  { at: '2026-10-16T13:58:00Z', runtime_id: 'rt-self-1', node_id: 'rrotor-1', actor: { kind: 'key', id: 'Production app' }, action: 'model.query', target: 'credit-risk', outcome: 'allowed', via: 'api' },
  { at: '2026-10-16T13:41:00Z', runtime_id: 'rt-self-1', node_id: 'rrotor-1', actor: { kind: 'user', id: 'chris@example.com' }, action: 'model.delete', target: 'old-model', outcome: 'denied', via: 'mcp' },
];

export const metrics: RuntimeMetrics[] = [
  { ...acme, node_id: 'rrotor-1', at: '2026-10-16T13:58:00Z', runs: 1_284, run_seconds: 5_400, precedents: 12_050, cap: 50_000, link: 'up', drops: 0 },
  { ...acme, node_id: 'rrotor-2', at: '2026-10-16T13:57:00Z', runs: 310, run_seconds: 90, precedents: 12_050, cap: 50_000, link: 'down', drops: 12 },
];

/**
 * As the server answers with `GLYPHH_HOSTING=off` and sync not yet built: the rates off
 * (refused with hosting_off), and each feature saying whether it is built. The org is on Free.
 */
// As the server's BUILT: only offline licences work today.
const unbuilt = { sync: false, ha: false, offline: true, sso: false };
// The runtime nodes stay as they are: they count self-hosted runtimes too.
const off = (plan: Plan, change: Partial<Plan>): Plan => ({ ...plan, ...change, built: unbuilt });
const offPlans: Plan[] = [
  off(plans[0]!, {}),
  off(plans[1]!, {}),
  off(plans[2]!, {}),
  off(plans[3]!, {}),
];
const offMe: Me = {
  ...me,
  org: { ...me.org, billing_status: 'none', renews_at: null },
  plan: offPlans[0]!,
  precedents: { used: 3_200, limit: 5_000 },
  hosting: { month: '2026-10', month_to_date_cents: 0, machines: [] },
};

export const hostingOff = {
  plans: offPlans,
  rates: { hosting: 'off' } as HostingOff,
  me: offMe,
  org: { ...org, plan: offPlans[0]!, billing_status: 'none' } as Org,
  machines: [] as Machine[],
  // Free has no key: rrotor runs as Community. Its one node is the self-hosted runtime.
  licenceKeys: { license_key: null, keys: [] } as LicenceKeys,
  nodes: {
    count: 1,
    max_nodes: 1,
    over: false,
    nodes: [{ runtime_id: 'rt-self-1', runtime: 'Acme production', mode: 'self', node_id: null, cluster_id: null, role: null, precedents: 3_200, version: '1.4.2', seen_at: '2026-10-16T13:50:00Z' }],
  } as RuntimeNodes,
  runtime: { ...runtime, runtime_id: null, address: null, state: 'none', region: null, image_version: null, last_seen_at: null, seconds_used: 0 } as Runtime,
};
