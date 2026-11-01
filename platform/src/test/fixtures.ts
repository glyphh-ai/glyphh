import type { CloudLimits, Install, Invite, LicenceKey, LicenceKeys, Me, Member, Org, Plan, RuntimeKey, RuntimeNodes, SelfRuntime } from '@/api/types';

/**
 * One org's data in the server's shapes, shared by the page tests and the local fake server: on Pro, as if every
 * feature were built, and below, `onFree`, as the server answers a Free org today (only offline licences built).
 * Glyphh hosts no runtime: the org's runtimes are a local rrotor and the ones it runs at its own address.
 */

// The server's four flags; roles and audit logs ride on sso. As if every feature were built.
const none = { sync: false, ha: false, offline: false, sso: false };
const built = { sync: true, ha: true, offline: true, sso: true };

// In the server's order: Free, Basic, Pro, Team, Enterprise. Basic ($20, an Ada Cloud plan) has no licence key, so a
// self-hosted node on it runs as Free's.
export const plans: Plan[] = [
  { name: 'Free', version: 1, price_cents: 0, interval: null, self_serve: true, limits: { machines: 1, precedents: 5_000 }, features: none, built },
  { name: 'Basic', version: 1, price_cents: 2000, interval: 'month', self_serve: true, limits: { machines: 1, precedents: 5_000 }, features: none, built },
  { name: 'Pro', version: 1, price_cents: 9900, interval: 'month', self_serve: true, limits: { machines: 3, precedents: 50_000 }, features: { ...none, sync: true }, built },
  { name: 'Team', version: 1, price_cents: 29900, interval: 'month', self_serve: true, limits: { machines: 10, precedents: 500_000 }, features: { ...none, sync: true }, built },
  {
    name: 'Enterprise',
    version: 1,
    price_cents: null,
    interval: null,
    self_serve: false,
    limits: { machines: null, precedents: null },
    features: { sync: true, ha: true, offline: true, sso: true },
    built,
  },
];

/** Each plan's Ada Cloud limits, as the server seeds them (glyphh_server/db/seed.py): a version's cloud_*. */
export const cloudLimits: Record<string, CloudLimits> = {
  Free: { precedents: 1_000, requests_per_month: 5_000, requests_per_second: 5, overage: false, overage_cents_per_10k: null },
  Basic: { precedents: 10_000, requests_per_month: 50_000, requests_per_second: 10, overage: true, overage_cents_per_10k: 100 },
  Pro: { precedents: 100_000, requests_per_month: 1_000_000, requests_per_second: 50, overage: true, overage_cents_per_10k: 100 },
  Team: { precedents: 1_000_000, requests_per_month: 5_000_000, requests_per_second: 200, overage: true, overage_cents_per_10k: 100 },
  Enterprise: { precedents: null, requests_per_month: null, requests_per_second: null, overage: false, overage_cents_per_10k: null },
};

/** The plans as `GET /v1/plans` lists them with Ada Cloud on: each with its cloud limits. */
export const adaPlans: Plan[] = plans.map((plan) => ({ ...plan, cloud: cloudLimits[plan.name]! }));

const pro = plans[2]!;

export const me: Me = {
  id: 'u-chris',
  email: 'chris@example.com',
  name: 'Chris Timmerman',
  role: 'admin',
  providers: ['github', 'google'],
  org: { id: 'o-1', name: 'Glyphh', billing_status: 'active', renews_at: '2026-11-16T00:00:00Z', plan_until: null },
  plan: pro,
  precedents: { used: 18_240, limit: 50_000 },
};

export const org: Org = {
  id: 'o-1',
  name: 'Glyphh',
  admin_user_id: 'u-chris',
  plan: pro,
  members: 1,
  billing_status: 'active',
};

export const runtimeKeys: RuntimeKey[] = [
  { id: 'k-1', runtime_id: 'rt-self-1', name: 'Billing worker', created_at: '2026-10-02T09:00:00Z', expires_at: '2027-10-02T09:00:00Z', revoked_at: null, calls: 1284, last_used_at: '2026-10-16T13:55:00Z' },
  { id: 'k-2', runtime_id: 'rt-self-1', name: 'Support bot', created_at: '2026-10-09T15:30:00Z', expires_at: '2026-10-12T15:30:00Z', revoked_at: null, calls: 1, last_used_at: '2026-10-10T08:00:00Z' },
  { id: 'k-3', runtime_id: 'rt-self-2', name: 'Old script', created_at: '2026-09-12T11:00:00Z', expires_at: '2026-12-11T11:00:00Z', revoked_at: '2026-10-01T08:00:00Z', calls: 0, last_used_at: null },
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

/** Pro's three nodes: a local rrotor (it names no node, so counts as one) and a self-hosted cluster of two. */
export const nodes: RuntimeNodes = {
  count: 3,
  max_nodes: 3,
  over: false,
  nodes: [
    { runtime_id: 'rt-self-1', runtime: 'Acme production', mode: 'self', node_id: 'rrotor-1', cluster_id: 'c-1', role: 'head', precedents: 12_050, version: '1.4.2', seen_at: '2026-10-16T13:50:00Z' },
    { runtime_id: 'rt-self-1', runtime: 'Acme production', mode: 'self', node_id: 'rrotor-2', cluster_id: 'c-1', role: 'follower', precedents: 12_050, version: '1.4.2', seen_at: '2026-10-16T13:49:00Z' },
    { runtime_id: 'rt-local-1', runtime: 'studio-mac', mode: 'local', node_id: null, cluster_id: null, role: null, precedents: 18_240, version: '1.4.2', seen_at: '2026-10-16T13:58:00Z' },
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
 * As the server answers a Free org today: each feature saying whether it is built (as the server's BUILT, only offline
 * licences work), no subscription and no licence key.
 */
const unbuilt = { sync: false, ha: false, offline: true, sso: false };
// The runtime nodes stay as they are: they count local and self-hosted runtimes alike.
const freePlans: Plan[] = plans.map((plan) => ({ ...plan, built: unbuilt }));
const freeMe: Me = {
  ...me,
  org: { ...me.org, billing_status: 'none', renews_at: null },
  plan: freePlans[0]!,
  precedents: { used: 3_200, limit: 5_000 },
};

export const onFree = {
  plans: freePlans,
  me: freeMe,
  org: { ...org, plan: freePlans[0]!, billing_status: 'none' } as Org,
  // Free has no key: rrotor runs as Community. Its one node is the self-hosted runtime.
  licenceKeys: { license_key: null, keys: [] } as LicenceKeys,
  nodes: {
    count: 1,
    max_nodes: 1,
    over: false,
    nodes: [{ runtime_id: 'rt-self-1', runtime: 'Acme production', mode: 'self', node_id: null, cluster_id: null, role: null, precedents: 3_200, version: '1.4.2', seen_at: '2026-10-16T13:50:00Z' }],
  } as RuntimeNodes,
};
