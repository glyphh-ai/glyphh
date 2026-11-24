/** The server's response shapes, as `glyphh-ai/server` returns them. Dates are ISO strings. */

export type Uuid = string;
export type IsoDate = string;

/** The features the platform has words for; the server may name more, and those are not shown. */
export type FeatureName = 'sso' | 'rbac' | 'audit';

/** One feature as the server may state it: on the plan, and whether Glyphh has built it yet. */
export type FeatureState = { included: boolean; built: boolean };

/**
 * What a plan turns on: a boolean per feature, with whether each is built in the plan's separate `built` map. A server
 * may instead answer `{included, built}` per feature; both are read alike.
 */
export type PlanFeatures = Partial<Record<FeatureName, boolean | FeatureState>> & { [feature: string]: boolean | FeatureState | undefined };

/**
 * A plan as `GET /v1/plans` lists it. Members, installs, models and keys are unlimited on every plan. Only what the
 * platform reads is named here; anything else the server sends is left alone.
 */
export type Plan = {
  name: string;
  version: number;
  /** The flat price for each interval; null for a plan sold by contract. */
  price_cents: number | null;
  /** Null on Free. */
  interval: 'month' | 'year' | null;
  /** Bought here through Stripe's checkout; otherwise by talking to Glyphh. */
  self_serve: boolean;
  /** Missing: the plan turns nothing on. */
  features?: PlanFeatures;
  /** Whether each feature is built; a feature not in it (or no map at all) is built. */
  built?: { [feature: string]: boolean | undefined };
  /** Ada Cloud's limits, the org's whatever its people, models or keys; null (or missing) while Ada Cloud is off. */
  cloud?: CloudLimits | null;
  /**
   * Tokens a month on Glyphh's hosted models (Free 250,000, Basic 5,000,000, Pro 25,000,000, Team 100,000,000); null is
   * by contract (Enterprise).
   */
  llm_tokens?: number | null;
};

/**
 * A plan's Ada Cloud limits (the server's cloud_* on a plan version): Free 1,000 precedents, 5,000 requests a month,
 * 5 a second; Basic 10,000, 50,000, 10; Pro 100,000, 1,000,000, 50; Team 1,000,000, 5,000,000, 200; Enterprise by
 * contract (null: unlimited). Past the month Basic, Pro and Team are metered (`overage`); Free is refused until the
 * month turns.
 */
export type CloudLimits = {
  precedents: number | null;
  /** Reads (decide, query, probabilities, facts) a calendar month, UTC. */
  requests_per_month: number | null;
  /** Calls a second, the org's together. */
  requests_per_second: number | null;
  overage: boolean;
  /** What 10,000 requests past the month cost; null when none are sold. */
  overage_cents_per_10k: number | null;
};

/**
 * What the org uses of Ada Cloud against its plan: one shape for Ada's `GET /v1/usage` and `cloud` on /v1/me and
 * /v1/billing. Requests are reads (a decide of several outputs counts once per output), by calendar month, UTC.
 */
export type CloudUsage = {
  plan: string;
  /** YYYY-MM, UTC. */
  month: string;
  /** When the month's count starts again, YYYY-MM-DD. */
  resets_at: string;
  /** The org's live models. */
  models: number;
  /** A null max is by contract: unlimited. */
  precedents: { used: number; max: number | null };
  /** `over`: requests past the month, metered; `overage`: past it is metered (Pro, Team), else refused (Free). */
  requests: { used: number; max: number | null; over: number; overage: boolean };
  /** Calls a second; null: by contract. */
  requests_per_second: number | null;
};

export type Me = {
  id: Uuid;
  email: string;
  name: string | null;
  role: 'admin' | 'member';
  providers: string[];
  /** `plan_until`: when an Enterprise grant ends; null on any other plan. */
  org: { id: Uuid; name: string; billing_status: string; renews_at: IsoDate | null; plan_until: IsoDate | null };
  plan: Plan;
  /** Ada Cloud is on (`GLYPHH_ADA_CLOUD`): Home, Models, API Keys and Usage are there. Missing: off. */
  ada_cloud?: boolean;
  /** Ada Cloud's use against the plan; null (or missing) while it is off. */
  cloud?: CloudUsage | null;
  /** Glyphh's staff (the server's GLYPHH_STAFF_EMAILS): the platform opens the staff view. Missing: not staff. */
  staff?: boolean;
};

export type Install = {
  id: Uuid;
  machine_id: string;
  name: string;
  surface: string;
  mod_version: string;
  last_seen_at: IsoDate | null;
  created_at: IsoDate;
  current: boolean;
};

export type Org = {
  id: Uuid;
  name: string;
  admin_user_id: Uuid | null;
  plan: Plan;
  members: number;
  billing_status: string;
};

export type Member = { id: Uuid; email: string; name: string | null; role: string; joined_at: IsoDate };
export type Invite = { id: Uuid; email: string; expires_at: IsoDate; created_at: IsoDate };
export type NewInvite = { invite: Invite; link: string };

/** The sign-in providers the server offers, in its order, and whether any org signs in with single sign-on. */
export type Providers = { providers: string[]; sso: boolean };

/** An org's single sign-on by OpenID Connect, as `GET /v1/org/sso` shows it: never the client secret. */
export type Sso = {
  issuer: string;
  client_id: string;
  domains: string[];
  /** The org's people sign in with it and nothing else. */
  enforced: boolean;
  /** The redirect URI to register at the identity provider. */
  callback_url: string;
  updated_at: IsoDate;
};
/** What `PUT /v1/org/sso` takes; the secret left out keeps the one set. */
export type SsoIn = { issuer: string; client_id: string; client_secret?: string; domains: string[]; enforced: boolean };

export type Provider = 'google' | 'github';
export const SSO = 'sso';

export type DeviceConsent = { kind: 'device'; code: string; name: string; surface: string; email: string };
export type OAuthConsent = { kind: 'oauth'; client: string; returns_to: string | null; resource: string; email: string };
export type Consent = DeviceConsent | OAuthConsent;

export type ApiErrorBody = {
  error: { code: string; message: string; trace_id?: string; reason?: string; [detail: string]: unknown };
};

// Glyphh's hosted models: a monthly token allowance on the plan, then dollars per million tokens from a prepaid balance.

export type LlmModelStatus = 'beta' | 'stable' | 'deprecated';

/** A hosted model and its rates, as `GET /v1/plans` (`models`) and `GET /v1/llm/models` list it. */
export type LlmModel = {
  /** Such as `adal-34b-1-0`. */
  id: string;
  /** Such as "adaL 34B 1.0". */
  name: string;
  status: LlmModelStatus;
  /** What a million input tokens cost past the allowance, in cents: 60 is $0.60. */
  input_cents_per_mtok: number;
  output_cents_per_mtok: number;
  context_tokens: number;
};

/** `GET /v1/plans`: the plans alone (an older server, or hosted models off), or with the hosted models' rates. */
export type PlansAnswer = Plan[] | { plans: Plan[]; models?: LlmModel[] };

/** `GET /v1/llm/models`: the registry, as a list or under `models`. */
export type LlmModelsAnswer = LlmModel[] | { models: LlmModel[] };

/** One model's use this month. `charged_cents` is what went on the balance past the allowance; it may be fractional. */
export type TokenModelUse = {
  id: string;
  name: string;
  input_tokens: number;
  output_tokens: number;
  requests: number;
  charged_cents: number;
};

/** The month's tokens against the plan's allowance (input and output together, by calendar month, UTC). */
export type TokenUsage = {
  /** YYYY-MM, UTC. */
  month: string;
  /** When the allowance starts again, YYYY-MM-DD. */
  resets_at: string;
  used: number;
  /** Null is by contract. */
  max: number | null;
  /** Tokens past the allowance, charged to the balance. */
  over_used: number;
  models: TokenModelUse[];
};

/** The prepaid overage balance, in dollars: `cents` may be fractional, `micros` (1 = $0.000001) is exact. */
export type Balance = { cents: number; micros?: number; low: boolean };

/**
 * `GET /v1/billing`: the plan and its use: Ada Cloud's (while on), the hosted models' tokens this month and the
 * balance; any of the three may be missing.
 */
export type Billing = {
  plan: Plan;
  billing_status: string;
  renews_at: IsoDate | null;
  plan_until: IsoDate | null;
  cloud?: CloudUsage | null;
  tokens?: TokenUsage | null;
  balance?: Balance | null;
};

/** One model's use on one day, UTC, as `GET /v1/llm/usage?days=30` lists it under `days`. */
export type TokenDay = {
  /** YYYY-MM-DD. */
  day: string;
  model: string;
  input_tokens: number;
  output_tokens: number;
  requests: number;
  charged_cents: number;
};

export type LedgerKind = 'topup' | 'charge' | 'grant' | 'refund';

/** One movement of the balance, as `GET /v1/billing/ledger?limit=50` lists it under `entries`, newest first. Charges are negative. */
export type LedgerEntry = {
  at: IsoDate;
  kind: LedgerKind;
  amount_cents: number;
  amount_micros?: number;
  model: string | null;
  note: string | null;
};

/**
 * One UTC day of the org's use, as `GET /v1/billing/series?days=30` lists it under `days`, oldest first and one a day:
 * Ada Cloud's reads (decides among them) and what the balance was charged.
 */
export type SeriesDay = {
  /** YYYY-MM-DD. */
  day: string;
  reads: number;
  decides: number;
  charged_cents: number;
  charged_micros?: number;
};

/** The card on file, as Stripe has it; nothing of it is kept by Glyphh. */
export type PaymentCard = { brand: string; last4: string; exp_month: number; exp_year: number };

export type Invoice = {
  id: string;
  number: string | null;
  status: 'draft' | 'open' | 'paid' | 'uncollectible' | 'void' | string;
  total_cents: number;
  currency: string;
  created: IsoDate;
  /** Stripe's page for it. */
  url: string | null;
  pdf: string | null;
};

/** `GET /v1/billing/payment` (the admin's): the card on file (null: none) and the last twelve invoices, newest first. */
export type Payment = { card: PaymentCard | null; invoices: Invoice[] };
