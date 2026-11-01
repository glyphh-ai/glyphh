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
   * `machines`: runtime nodes, every rrotor linked for the org, local or self-hosted (Free 1, Basic 1, Pro 3,
   * Team 10). `precedents`: what one node may hold, across its models (Free and Basic 5,000, Pro 50,000, Team
   * 500,000). Null is unlimited.
   */
  limits: { machines: number | null; precedents: number | null };
  features: PlanFeatures;
  /** Whether each feature is built; a feature not in it (or no map at all) is built. */
  built?: { [feature: string]: boolean | undefined };
  /** Ada Cloud's limits, the org's whatever its people, models or keys; null (or missing) while Ada Cloud is off. */
  cloud?: CloudLimits | null;
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
  /** The identity provider's groups, from single sign-on; missing on an older server. */
  groups?: string[];
  /** Reviews the org's artifacts: the admin, or a member in a reviewer group. Missing on an older server. */
  reviewer?: boolean;
  /** `plan_until`: when an Enterprise grant ends; null on any other plan. */
  org: { id: Uuid; name: string; billing_status: string; renews_at: IsoDate | null; plan_until: IsoDate | null };
  plan: Plan;
  /** The most any one of the org's runtimes holds, local or self-hosted, against the plan's per node (null: unlimited). */
  precedents: { used: number; limit: number | null };
  /** Ada Cloud is on (`GLYPHH_ADA_CLOUD`): the platform is Ada's, with no runtimes. Missing on an older server: off. */
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

/** A key that calls one of the person's self-hosted runtimes at its address. */
export type RuntimeKey = {
  id: Uuid;
  /** The self-hosted runtime it calls. */
  runtime_id: Uuid;
  name: string;
  created_at: IsoDate;
  expires_at: IsoDate | null;
  revoked_at: IsoDate | null;
  /** Calls the key let in, as the runtime reports them each minute. */
  calls: number;
  last_used_at: IsoDate | null;
};
export type NewRuntimeKey = RuntimeKey & { key: string };

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
  /** A local rrotor (an install's, started from Claude) or one self-hosted at its own address. */
  mode: 'local' | 'self';
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
  /** The groups whose members review the org's artifacts, beside the admin. Missing on an older server. */
  reviewers?: string[];
  updated_at: IsoDate;
};
/** What `PUT /v1/org/sso` takes; the secret left out keeps the one set. */
export type SsoIn = { issuer: string; client_id: string; client_secret?: string; domains: string[]; enforced: boolean; reviewers?: string[] };

export type ArtifactState = 'draft' | 'approved' | 'rejected' | 'retired';

/** An app published to one of the org's rrotors, as the catalogue lists it (`GET /v1/artifacts`); the page itself never passes through the server. */
export type Artifact = {
  id: Uuid;
  runtime_id: Uuid;
  runtime_name: string;
  runtime_url: string;
  name: string;
  title: string;
  description: string;
  version: number;
  commit_sha: string;
  /** The roles that may open it; empty: everyone in the org. */
  roles: string[];
  state: ArtifactState;
  submitted_by: { id: Uuid; name: string | null; email: string } | null;
  submitted_at: IsoDate;
  reviewed_by: { id: Uuid; name: string | null; email: string } | null;
  reviewed_at: IsoDate | null;
  /** A rejection's reason. */
  reason: string | null;
  /** Where it opens: `{runtime_url}/apps/{name}/`. */
  url: string;
};

export type ArtifactPage = { artifacts: Artifact[]; page: number; per_page: number; total: number };

export type Provider = 'google' | 'github';
export const SSO = 'sso';

export type DeviceConsent = { kind: 'device'; code: string; name: string; surface: string; email: string };
export type OAuthConsent = { kind: 'oauth'; client: string; returns_to: string | null; resource: string; email: string };
export type Consent = DeviceConsent | OAuthConsent;

export type ApiErrorBody = {
  error: { code: string; message: string; trace_id?: string; reason?: string; [detail: string]: unknown };
};
