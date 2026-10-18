/** The server's response shapes, as `glyphh-ai/server` returns them. Dates are ISO strings. */

export type Uuid = string;
export type IsoDate = string;

/** What a plan turns on, as each runtime's licence carries it. */
export type PlanFeatures = { sync: boolean; ha: boolean; offline: boolean; sso: boolean };

/** A plan as `GET /v1/plans` lists it. Members, installs, self-hosted runtimes and Ada are unlimited on every plan. */
export type Plan = {
  name: string;
  version: number;
  /** The flat price for each interval; null for a plan sold by contract. */
  price_cents: number | null;
  /** Null on Free. */
  interval: 'month' | 'year' | null;
  /** Bought here through Stripe's checkout; otherwise by talking to Glyphh. */
  self_serve: boolean;
  /** Hosted machines, and the precedents managed on them; null is unlimited. */
  limits: { machines: number | null; precedents: number | null };
  features: PlanFeatures;
  markup_hidden: true;
};

/** One hosted machine's cost this month, in cents, as billed. */
export type MachineCost = { id: Uuid; name: string; size: MachineSize; cents: number };

export type Me = {
  id: Uuid;
  email: string;
  name: string | null;
  role: 'admin' | 'member';
  providers: string[];
  /** `plan_until`: when an Enterprise grant ends; null on any other plan. */
  org: { id: Uuid; name: string; billing_status: string; renews_at: IsoDate | null; plan_until: IsoDate | null };
  plan: Plan;
  /** Precedents across the org's hosted runtimes, against the plan's managed bucket (null: unlimited). */
  precedents: { used: number; limit: number | null };
  /** Hosted machines this month so far. */
  hosting: { month: string; month_to_date_cents: number; machines: MachineCost[] };
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

export type RuntimeState = 'none' | 'stopped' | 'online' | 'offline';

export type Runtime = {
  runtime_id: Uuid | null;
  address: string | null;
  state: RuntimeState;
  region: string | null;
  image_version: string | null;
  last_seen_at: IsoDate | null;
  seconds_used: number;
};

export type RuntimeKey = {
  id: Uuid;
  name: string;
  created_at: IsoDate;
  expires_at: IsoDate | null;
  revoked_at: IsoDate | null;
  /** Calls the key let in, as the runtime reports them each minute. */
  calls: number;
  last_used_at: IsoDate | null;
};
export type NewRuntimeKey = RuntimeKey & { key: string };

/** A hosted machine's size: Fly's guest and the volume under it. */
export type MachineSize = 'small' | 'medium' | 'large';

/** One of a person's hosted machines, as `GET /v1/runtimes` lists them. */
export type Machine = {
  id: Uuid;
  name: string;
  size: MachineSize;
  state: 'stopped' | 'online' | 'offline';
  address: string | null;
  /** Seconds it has run this month. */
  month_seconds: number;
  created_at: IsoDate;
};

/** How a self-hosted rrotor last reported in: `stopped` until it first links. */
export type SelfRuntimeState = 'stopped' | 'online' | 'offline';

/** A runtime someone runs themselves (Docker Compose, Helm, Terraform), registered with the server. */
export type SelfRuntime = {
  id: Uuid;
  name: string;
  /** Where it answers, such as `https://rrotor.acme.com`. */
  public_url: string;
  state: SelfRuntimeState;
  version: string | null;
  last_seen_at: IsoDate | null;
  last_heartbeat_at: IsoDate | null;
};

/** A registration as the server answers it once: the token, and the env rrotor runs with, filled in. */
export type NewSelfRuntime = Pick<SelfRuntime, 'id' | 'name' | 'public_url'> & { token: string; env: Record<string, string> };

/** A long-lived licence for an air-gapped runtime, set as RROTOR_LICENCE. */
export type OfflineLicence = { token: string; expires_at: IsoDate };

export type ModelVersion = { id: Uuid; version: number; commit_sha: string; created_at: IsoDate; active_on: Uuid[] };
export type Model = { id: Uuid; name: string; repo: string | null; created_at: IsoDate; versions: ModelVersion[] };

/** One size at a plan's rates: what it costs a month and a second while it runs. */
export type SizeRate = { size: MachineSize; usd_per_month: number; usd_per_second: number };

/**
 * `GET /v1/rates`: the hosted machine rates for each plan with hosting. The top-level `sizes` are Fly's own; the pages
 * show only a plan's.
 */
export type Rates = {
  effective_from: IsoDate;
  source: string;
  sizes: Array<SizeRate & { cpu_kind: string; cpus: number; memory_mb: number; volume_gb: number }>;
  volume_usd_per_gb_month: number;
  plans: Record<string, { sizes: SizeRate[]; volume_usd_per_gb_month: number }>;
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

export type Provider = 'google' | 'github';

export type DeviceConsent = { kind: 'device'; code: string; name: string; surface: string; email: string };
export type OAuthConsent = { kind: 'oauth'; client: string; returns_to: string | null; resource: string; email: string };
export type Consent = DeviceConsent | OAuthConsent;

export type ApiErrorBody = {
  error: { code: string; message: string; trace_id?: string; reason?: string; [detail: string]: unknown };
};
