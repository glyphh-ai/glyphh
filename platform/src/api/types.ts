/** The server's response shapes, as `glyphh-ai/server` returns them. Dates are ISO strings. */

export type Uuid = string;
export type IsoDate = string;

/** The features the platform has words for; the server may name more. */
export type FeatureName = 'sync' | 'ha' | 'offline' | 'sso' | 'rbac' | 'audit';

/** One feature as the server may state it: on the plan, and whether Glyphh has built it yet. */
export type FeatureState = { included: boolean; built: boolean };

/**
 * What a plan turns on, as each runtime's licence carries it: a boolean per feature, with whether each is built in the
 * plan's separate `built` map. A server may instead answer `{included, built}` per feature; both are read alike.
 */
export type PlanFeatures = Partial<Record<FeatureName, boolean | FeatureState>> & { [feature: string]: boolean | FeatureState | undefined };

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
  /**
   * `machines`: runtime nodes, every runtime linked for the org, hosted or self-hosted (Free 1, Pro 3, Team 10).
   * `precedents`: what one node may hold, across its models (Free 5,000, Pro 50,000, Team 500,000). Null is unlimited.
   */
  limits: { machines: number | null; precedents: number | null };
  features: PlanFeatures;
  /** Whether each feature is built; a feature not in it (or no map at all) is built. */
  built?: { [feature: string]: boolean | undefined };
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
  /** The most any one of the org's runtimes holds, hosted or self-hosted, against the plan's per node (null: unlimited). */
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

/** A runtime someone runs themselves (Docker, Helm, Terraform), registered with the server. */
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

/** A licence key's state: `live` is delivered to the org's runtimes; `revoked` when its subscription or grant ended. */
export type LicenceKeyState = 'live' | 'expired' | 'revoked';

/**
 * One licence key, as `GET /v1/license/keys` lists it: the plan's terms signed for one paid period. rrotor runs on it;
 * a node with none runs as Community (Free's limits).
 */
export type LicenceKey = {
  license_id: Uuid;
  /** The plan's name in lower case: pro, team or enterprise. */
  tier: string;
  /** Null is unlimited. */
  max_nodes: number | null;
  /** Precedents one node may hold, across its models; null is unlimited. */
  max_precedents: number | null;
  cluster_sync_enabled: boolean;
  issued_at: IsoDate;
  /** rrotor holds it 14 days past this, then runs as Community. */
  expires_at: IsoDate;
  revoked_at: IsoDate | null;
  state: LicenceKeyState;
  /** The key itself: `GLYPHH_LICENSE_KEY`, or `/etc/rrotor/license.key`, on a node. */
  key: string;
};

/** `GET /v1/license/keys`: every key issued to the org, newest first, and the newest live one (null on Free). */
export type LicenceKeys = { license_key: string | null; keys: LicenceKey[] };

/** One runtime node, as its heartbeat or link last said it. */
export type RuntimeNode = {
  runtime_id: Uuid;
  /** The runtime's name. */
  runtime: string | null;
  mode: 'hosted' | 'self';
  /** As the node named itself; null for a runtime that has said no node (it counts as one). */
  node_id: string | null;
  cluster_id: Uuid | null;
  role: 'standalone' | 'head' | 'follower' | null;
  /** Its store's precedents across its models, as it last said. */
  precedents: number | null;
  version: string | null;
  seen_at: IsoDate | null;
};

/** `GET /v1/license/nodes`: the org's runtime nodes against the plan's. Soft: `over` is shown, nothing is refused. */
export type RuntimeNodes = { count: number; max_nodes: number | null; over: boolean; nodes: RuntimeNode[] };

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

/** `GET /v1/rates` while Glyphh hosts nothing (`GLYPHH_HOSTING=off`): this, or the rates with an empty `plans`. */
export type HostingOff = { hosting: 'off' };

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

/**
 * rrotor's opt-in server-side telemetry (`RROTOR_SERVER_LOGS=on`), as `GET /v1/telemetry/*` answers it. By default a
 * runtime sends none, and these lists are empty. Read tolerantly: a field the platform does not know is kept, and an
 * optional one may be missing.
 */

/** OTLP's severity, named as the server names it: a filter by one means it and above. */
export type LogLevel = 'trace' | 'debug' | 'info' | 'warn' | 'error' | 'fatal';

/** What every record carries: when, and which runtime and node sent it. `attributes` are rrotor's, nested ones dotted. */
type Sent = {
  id?: Uuid;
  at: IsoDate;
  runtime_id?: Uuid | null;
  /** The runtime's name. */
  runtime?: string | null;
  /** The node it came from (its service.instance.id). */
  node_id?: string | null;
  attributes?: Record<string, unknown> | null;
  [field: string]: unknown;
};

/** One log record. */
export type LogRecord = Sent & {
  level?: LogLevel | string | null;
  /** OTLP's severity number, 1 to 24. */
  severity?: number | null;
  /** The message. */
  body?: string | null;
  trace_id?: string | null;
  span_id?: string | null;
};

/** `GET /v1/telemetry/logs`: newest first, without the audit events, and the next page's cursor (null on the last). */
export type LogsPage = { records?: LogRecord[]; next_cursor?: string | null; [field: string]: unknown };

/**
 * One audit event: its kind (run.call, model.deploy, access.denied, …) and its fields as attributes, flattened:
 * `actor.type` (key, sign-in, local, server, rrotor, anonymous), `actor.key_sha256`, `actor.sub`, `via`,
 * `outcome.status`, `outcome.code`.
 */
export type AuditEvent = Sent & { kind?: string | null };

/** `GET /v1/telemetry/audit`: newest first, and the next page's cursor (null on the last). */
export type AuditPage = { events?: AuditEvent[]; next_cursor?: string | null; [field: string]: unknown };

/**
 * The latest point of one metric series: a node, a metric and its point's attributes. rrotor's are `rrotor.runs`
 * (sum: model, function, status), `rrotor.run.seconds` (histogram), `rrotor.precedents` (gauge: model),
 * `rrotor.precedents.cap`, `rrotor.link.state` (gauge: state) and `rrotor.drain.dropped` (sum: drain, signal).
 */
export type MetricPoint = {
  runtime_id?: Uuid | null;
  runtime?: string | null;
  node_id?: string | null;
  name: string;
  unit?: string | null;
  kind?: 'gauge' | 'sum' | 'histogram' | string | null;
  /** A gauge's or sum's value; a histogram's sum. */
  value?: number | null;
  /** A histogram's count. */
  count?: number | null;
  attributes?: Record<string, unknown> | null;
  at?: IsoDate | null;
  [field: string]: unknown;
};

/** `GET /v1/telemetry/metrics`: the latest point of each series. */
export type MetricsAnswer = { metrics?: MetricPoint[]; [field: string]: unknown };
