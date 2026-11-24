import type {
  Balance,
  Billing,
  CloudLimits,
  Install,
  Invite,
  LedgerEntry,
  LlmModel,
  Me,
  Member,
  Org,
  Payment,
  Plan,
  SeriesDay,
  Sso,
  TokenDay,
  TokenUsage,
} from '@/api/types';

/**
 * One org's data in the server's shapes, shared by the page tests and the local fake server: on Pro, as if every
 * feature were built, and below, `onFree`, as the server answers a Free org today (single sign-on built; roles and
 * audit logs not).
 */

// The server's flag; roles and audit logs are included where sso is. As if every feature were built.
const none = { sso: false };
const built = { sso: true, rbac: true, audit: true };

// In the server's order: Free, Basic, Pro, Team, Enterprise.
export const plans: Plan[] = [
  { name: 'Free', version: 1, price_cents: 0, interval: null, self_serve: true, features: none, built },
  { name: 'Basic', version: 1, price_cents: 2000, interval: 'month', self_serve: true, features: none, built },
  { name: 'Pro', version: 1, price_cents: 9900, interval: 'month', self_serve: true, features: none, built },
  { name: 'Team', version: 1, price_cents: 29900, interval: 'month', self_serve: true, features: none, built },
  { name: 'Enterprise', version: 1, price_cents: null, interval: null, self_serve: false, features: { sso: true }, built },
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
};

export const org: Org = {
  id: 'o-1',
  name: 'Glyphh',
  admin_user_id: 'u-chris',
  plan: pro,
  members: 1,
  billing_status: 'active',
};

export const members: Member[] = [{ id: 'u-chris', email: 'chris@example.com', name: 'Chris Timmerman', role: 'admin', joined_at: '2026-07-05T12:00:00Z' }];

export const invites: Invite[] = [];

/** The org's single sign-on, once set: Okta, with one domain, not required. */
export const sso: Sso = {
  issuer: 'https://acme.okta.com',
  client_id: '0oa1example',
  domains: ['acme.com'],
  enforced: false,
  callback_url: 'http://api.test/auth/sso/callback',
  updated_at: '2026-10-30T09:00:00Z',
};

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

/** As the server answers a Free org today: single sign-on built, roles and audit logs not, and no subscription. */
const unbuilt = { sso: true };
const freePlans: Plan[] = plans.map((plan) => ({ ...plan, built: unbuilt }));
const freeMe: Me = {
  ...me,
  org: { ...me.org, billing_status: 'none', renews_at: null },
  plan: freePlans[0]!,
};

export const onFree = {
  plans: freePlans,
  me: freeMe,
  org: { ...org, plan: freePlans[0]!, billing_status: 'none' } as Org,
};

// Glyphh's hosted models (the server's GLYPHH_LLM): a plan's tokens a month, then dollars per million tokens from the
// org's prepaid overage balance. Every number is a placeholder of the server's seed.

/** The hosted models, as `GET /v1/plans` (`models`) and `GET /v1/llm/models` list them. */
export const llmModels: LlmModel[] = [
  { id: 'adal-34b-1-0', name: 'adaL 34B 1.0', status: 'beta', input_cents_per_mtok: 60, output_cents_per_mtok: 240, context_tokens: 32_768 },
];

/** Each plan's tokens a month; Enterprise is by contract. */
export const llmTokens: Record<string, number | null> = { Free: 250_000, Basic: 5_000_000, Pro: 25_000_000, Team: 100_000_000, Enterprise: null };

/** `GET /v1/plans` with hosted models on: the plans, each with its tokens a month, and the models' rates. */
export const llmPlans = { plans: plans.map((plan) => ({ ...plan, llm_tokens: llmTokens[plan.name] ?? null })), models: llmModels };

/** Pro's month on the hosted models: 26.2 million tokens of 25 million, 1.2 million past it, charged to the balance. */
export const tokenUsage: TokenUsage = {
  month: '2026-11',
  resets_at: '2026-12-01',
  used: 26_200_000,
  max: 25_000_000,
  over_used: 1_200_000,
  models: [{ id: 'adal-34b-1-0', name: 'adaL 34B 1.0', input_tokens: 20_000_000, output_tokens: 6_200_000, requests: 4_210, charged_cents: 1129.6 }],
};

/** $18.704 left: $25 added and $5 granted, less $11.296 of charges. */
export const balance: Balance = { cents: 1870.4, micros: 18_704_000, low: false };

/** `GET /v1/billing` with hosted models off, as the server answers without GLYPHH_LLM. */
export const billing: Billing = {
  plan: pro,
  billing_status: 'active',
  renews_at: '2026-11-16T00:00:00Z',
  plan_until: null,
};

/** `GET /v1/billing` with hosted models on: the month's tokens and the balance. */
export const llmBilling: Billing = { ...billing, plan: llmPlans.plans[2]!, tokens: tokenUsage, balance };

/** `GET /v1/llm/usage?days=30`: two days of use with a day of none between. */
export const tokenDays: TokenDay[] = [
  { day: '2026-11-07', model: 'adal-34b-1-0', input_tokens: 1_200_000, output_tokens: 400_000, requests: 300, charged_cents: 0 },
  { day: '2026-11-09', model: 'adal-34b-1-0', input_tokens: 2_000_000, output_tokens: 900_000, requests: 610, charged_cents: 1129.6 },
];

/** The last day the fakes' series reach, as if today. */
export const seriesToday = '2026-11-09';

/** `GET /v1/billing/series?days=n`: n days to 9 November, oldest first, each with a little use that grows a day at a time. */
export function seriesDays(n: number): SeriesDay[] {
  const last = new Date(`${seriesToday}T00:00:00Z`).getTime();
  return Array.from({ length: n }, (_, i) => {
    const day = new Date(last - (n - 1 - i) * 86_400_000).toISOString().slice(0, 10);
    const k = i + 1;
    return { day, reads: 120 * k, decides: 80 * k, charged_cents: day === '2026-11-09' ? 1129.6 : 0 };
  });
}

/** `GET /v1/billing/payment`: a Visa on file and two invoices, newest first. */
export const payment: Payment = {
  card: { brand: 'visa', last4: '4242', exp_month: 4, exp_year: 2029 },
  invoices: [
    { id: 'in_2', number: 'GLY-0002', status: 'paid', total_cents: 9_900, currency: 'usd', created: '2026-11-01T00:00:00Z', url: 'https://invoice.stripe.test/in_2', pdf: 'https://invoice.stripe.test/in_2.pdf' },
    { id: 'in_1', number: 'GLY-0001', status: 'open', total_cents: 4_950, currency: 'usd', created: '2026-10-01T00:00:00Z', url: 'https://invoice.stripe.test/in_1', pdf: null },
  ],
};

/** `GET /v1/billing/ledger?limit=50`, newest first. */
export const ledger: LedgerEntry[] = [
  { at: '2026-11-09T14:00:00Z', kind: 'charge', amount_cents: -1129.6, amount_micros: -11_296_000, model: 'adal-34b-1-0', note: null },
  { at: '2026-11-05T10:00:00Z', kind: 'grant', amount_cents: 500, amount_micros: 5_000_000, model: null, note: 'Launch credit for testing' },
  { at: '2026-11-02T09:00:00Z', kind: 'topup', amount_cents: 2500, amount_micros: 25_000_000, model: null, note: null },
];
