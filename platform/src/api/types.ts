/** The server's response shapes, as `glyphh-ai/server` returns them. Dates are ISO strings. */

export type Uuid = string;
export type IsoDate = string;

export type Limits = Record<string, number | null>;

export type Plan = {
  name: string;
  version: number;
  seat_price_cents: number;
  limits: { members: number | null; installs: number | null };
  mods: Record<string, { limits: Limits }>;
};

export type Me = {
  id: Uuid;
  email: string;
  name: string | null;
  role: 'admin' | 'member';
  providers: string[];
  org: { id: Uuid; name: string; seats: number; billing_status: string; renews_at: IsoDate | null };
  plan: Plan;
  used: { members: number; seats: number; installs: number };
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
  hours_allowed: number | null;
  paused: boolean;
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

export type ModelVersion = { id: Uuid; version: number; commit_sha: string; created_at: IsoDate; active_on: Uuid[] };
export type Model = { id: Uuid; name: string; repo: string | null; created_at: IsoDate; versions: ModelVersion[] };

export type Addon = {
  mod: string;
  name: string;
  description: string;
  version: number;
  price_cents: number;
  per_seat: boolean;
  monthly_cents: number;
  plans: string[];
  free: boolean;
  allowed: boolean;
  limits: Limits | null;
  added: boolean;
  quantity: number | null;
};

export type AddonPreview = {
  mod: string;
  action: 'add' | 'remove';
  prorated_cents: number;
  currency: string;
  monthly_cents: number;
  proration_date: number;
};

export type Org = {
  id: Uuid;
  name: string;
  admin_user_id: Uuid | null;
  plan: Plan;
  seats: number;
  seats_taken: number;
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
