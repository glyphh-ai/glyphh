import type { Addon, Install, Invite, Me, Member, Model, Org, Plan, Runtime, RuntimeKey, SelfRuntime } from '@/api/types';

/** One org's data in the server's shapes, shared by the page tests and the local fake server. */

export const plans: Plan[] = [
  { name: 'Free', version: 1, seat_price_cents: 0, limits: { members: 1, installs: 1 }, mods: { ada: { limits: { models: 3, precedents: 10000 } } } },
  { name: 'Pro', version: 1, seat_price_cents: 800, limits: { members: 1, installs: 5 }, mods: { ada: { limits: { models: 3, precedents: 10000 } } } },
  { name: 'Team', version: 1, seat_price_cents: 1600, limits: { members: null, installs: 10 }, mods: { ada: { limits: { models: null, precedents: null } } } },
];

const pro = plans[1]!;

export const me: Me = {
  id: 'u-chris',
  email: 'chris@example.com',
  name: 'Chris Timmerman',
  role: 'admin',
  providers: ['github', 'google'],
  org: { id: 'o-1', name: 'Glyphh', seats: 1, billing_status: 'active', renews_at: '2026-11-16T00:00:00Z' },
  plan: pro,
  used: { members: 1, seats: 1, installs: 2 },
};

export const org: Org = {
  id: 'o-1',
  name: 'Glyphh',
  admin_user_id: 'u-chris',
  plan: pro,
  seats: 1,
  seats_taken: 1,
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
  hours_allowed: 50,
  paused: false,
};

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
    state: 'pending',
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

export const addons: Addon[] = [
  {
    mod: 'ada',
    name: 'Ada',
    description: 'Ada models in your runtime, deployed by commit and called by Claude or any app.',
    version: 1,
    price_cents: 400,
    per_seat: true,
    monthly_cents: 400,
    plans: ['Free', 'Pro', 'Team'],
    free: true,
    allowed: true,
    limits: { models: 3, precedents: 10000 },
    added: true,
    quantity: 1,
  },
];

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
