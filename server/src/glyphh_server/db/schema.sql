-- The Glyphh database: every table the server still uses, its indexes and its row-level security. The one source of
-- the schema; the server runs it before it starts (db/schema.py), so every statement here is safe to run again.
-- Glyphh's products were retired on 2026-11-18 and their tables are not made here any more: a database that still has
-- them keeps them, untouched and unread, until `python -m glyphh_server.winddown drop` removes them
-- (scripts/wind-down/README.md lists every table, kept or dropped). The kept tables are exactly as production has
-- them, column for column. The models in glyphh_server.models map these tables for queries, and
-- tests/db/test_schema_sql.py fails when they disagree.

-- oauth_clients: the platform's own sign-in client (db/seed_clients.py), the only one
CREATE TABLE IF NOT EXISTS oauth_clients (
    id UUID DEFAULT gen_random_uuid() NOT NULL,
    name TEXT NOT NULL,
    redirect_uris TEXT[] NOT NULL,
    auth_method TEXT NOT NULL,
    secret_hash TEXT,
    grant_types TEXT[] NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT oauth_clients_auth_method CHECK (auth_method IN ('none', 'client_secret_post', 'client_secret_basic')),
    CONSTRAINT oauth_clients_secret CHECK ((auth_method = 'none') = (secret_hash IS NULL)),
    CONSTRAINT oauth_clients_redirect_uris CHECK (cardinality(redirect_uris) > 0)
);

-- plans
CREATE TABLE IF NOT EXISTS plans (
    id UUID DEFAULT gen_random_uuid() NOT NULL,
    name TEXT NOT NULL,
    active BOOLEAN DEFAULT true NOT NULL,
    sort INTEGER DEFAULT 0 NOT NULL,
    PRIMARY KEY (id),
    UNIQUE (name)
);

-- plan_versions: what each org paid for, and the Stripe price the webhook knows a subscription's plan by
CREATE TABLE IF NOT EXISTS plan_versions (
    id UUID DEFAULT gen_random_uuid() NOT NULL,
    plan_id UUID NOT NULL,
    version INTEGER NOT NULL,
    stripe_price_id TEXT,
    price_cents INTEGER,
    billing_interval TEXT,
    self_serve BOOLEAN DEFAULT true NOT NULL,
    max_machines INTEGER,
    precedents INTEGER,
    sync BOOLEAN DEFAULT false NOT NULL,
    ha BOOLEAN DEFAULT false NOT NULL,
    offline BOOLEAN DEFAULT false NOT NULL,
    sso BOOLEAN DEFAULT false NOT NULL,
    cloud_precedents INTEGER,
    cloud_requests INTEGER,
    cloud_rps INTEGER,
    cloud_overage BOOLEAN DEFAULT false NOT NULL,
    llm_tokens BIGINT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT plan_versions_version UNIQUE (plan_id, version),
    CONSTRAINT plan_versions_llm CHECK (coalesce(llm_tokens, 0) >= 0),
    CONSTRAINT plan_versions_price CHECK (coalesce(price_cents, 0) >= 0),
    CONSTRAINT plan_versions_interval CHECK (billing_interval IN ('month', 'year')),
    CONSTRAINT plan_versions_limits CHECK (coalesce(max_machines, 0) >= 0 AND coalesce(precedents, 0) >= 0),
    CONSTRAINT plan_versions_cloud CHECK (coalesce(cloud_precedents, 0) >= 0 AND coalesce(cloud_requests, 0) >= 0 AND coalesce(cloud_rps, 1) > 0),
    FOREIGN KEY(plan_id) REFERENCES plans (id) ON DELETE RESTRICT,
    UNIQUE (stripe_price_id)
);
CREATE INDEX IF NOT EXISTS ix_plan_versions_plan_id ON plan_versions (plan_id);

-- orgs
CREATE TABLE IF NOT EXISTS orgs (
    id UUID DEFAULT gen_random_uuid() NOT NULL,
    name TEXT NOT NULL,
    plan_version_id UUID NOT NULL,
    admin_user_id UUID,
    stripe_customer_id TEXT,
    stripe_subscription_id TEXT,
    billing_status TEXT DEFAULT 'none' NOT NULL,
    renews_at TIMESTAMP WITH TIME ZONE,
    plan_until TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    suspended_at TIMESTAMP WITH TIME ZONE,
    suspended_reason TEXT,
    source JSONB,
    first_paid_at TIMESTAMP WITH TIME ZONE,
    PRIMARY KEY (id),
    CONSTRAINT orgs_billing_status CHECK (billing_status IN ('none', 'active', 'trialing', 'past_due', 'unpaid', 'canceled', 'incomplete', 'incomplete_expired', 'paused')),
    FOREIGN KEY(plan_version_id) REFERENCES plan_versions (id) ON DELETE RESTRICT,
    UNIQUE (stripe_customer_id),
    UNIQUE (stripe_subscription_id)
);
CREATE INDEX IF NOT EXISTS ix_orgs_plan_version_id ON orgs (plan_version_id);

-- invites
CREATE TABLE IF NOT EXISTS invites (
    id UUID DEFAULT gen_random_uuid() NOT NULL,
    org_id UUID NOT NULL,
    email TEXT NOT NULL,
    token_hash TEXT NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    accepted_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(org_id) REFERENCES orgs (id) ON DELETE CASCADE,
    UNIQUE (token_hash)
);
CREATE UNIQUE INDEX IF NOT EXISTS invites_one_open ON invites (org_id, lower(email)) WHERE accepted_at IS NULL;
CREATE INDEX IF NOT EXISTS ix_invites_org_id ON invites (org_id);

-- ada_meter_events, llm_ledger, llm_balances: the money the retired products left on record (models/money.py): each
-- report of metered reads sent to Stripe, each org's prepaid balance entry by entry in microdollars, and the balance.
CREATE TABLE IF NOT EXISTS ada_meter_events (
    id UUID DEFAULT gen_random_uuid() NOT NULL,
    org_id UUID NOT NULL,
    customer TEXT NOT NULL,
    period TEXT NOT NULL,
    requests INTEGER NOT NULL,
    at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    sent_at TIMESTAMP WITH TIME ZONE,
    PRIMARY KEY (id),
    CONSTRAINT ada_meter_events_requests CHECK (requests > 0),
    FOREIGN KEY(org_id) REFERENCES orgs (id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_ada_meter_events_org_id ON ada_meter_events (org_id);

CREATE TABLE IF NOT EXISTS llm_ledger (
    id UUID DEFAULT gen_random_uuid() NOT NULL,
    org_id UUID NOT NULL,
    at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    kind TEXT NOT NULL,
    amount_micros BIGINT NOT NULL,
    stripe_ref TEXT,
    model TEXT,
    period TEXT,
    note TEXT,
    PRIMARY KEY (id),
    CONSTRAINT llm_ledger_kind CHECK (kind IN ('topup', 'charge', 'grant', 'refund')),
    FOREIGN KEY(org_id) REFERENCES orgs (id) ON DELETE CASCADE,
    UNIQUE (stripe_ref)
);
CREATE INDEX IF NOT EXISTS llm_ledger_newest ON llm_ledger (org_id, at);
CREATE UNIQUE INDEX IF NOT EXISTS llm_ledger_charge_day ON llm_ledger (org_id, model, period) WHERE kind = 'charge';

CREATE TABLE IF NOT EXISTS llm_balances (
    org_id UUID NOT NULL,
    micros BIGINT DEFAULT 0 NOT NULL,
    period TEXT DEFAULT '' NOT NULL,
    tokens BIGINT DEFAULT 0 NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (org_id),
    FOREIGN KEY(org_id) REFERENCES orgs (id) ON DELETE CASCADE
);

-- users
CREATE TABLE IF NOT EXISTS users (
    id UUID DEFAULT gen_random_uuid() NOT NULL,
    org_id UUID NOT NULL,
    email TEXT NOT NULL,
    name TEXT,
    role TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    source JSONB,
    groups TEXT[] DEFAULT '{}'::text[] NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT users_role CHECK (role IN ('admin', 'member')),
    FOREIGN KEY(org_id) REFERENCES orgs (id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS ix_users_org_id ON users (org_id);
CREATE UNIQUE INDEX IF NOT EXISTS users_email ON users (lower(email));

-- connector_grants: a person's sign-in through an OAuth client (the platform's): its session
CREATE TABLE IF NOT EXISTS connector_grants (
    id UUID DEFAULT gen_random_uuid() NOT NULL,
    user_id UUID NOT NULL,
    client_id UUID NOT NULL,
    scope TEXT NOT NULL,
    resource TEXT NOT NULL,
    last_used_at TIMESTAMP WITH TIME ZONE,
    revoked_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE,
    FOREIGN KEY(client_id) REFERENCES oauth_clients (id) ON DELETE CASCADE
);
CREATE UNIQUE INDEX IF NOT EXISTS connector_grants_user_client ON connector_grants (user_id, client_id) WHERE revoked_at IS NULL;
CREATE INDEX IF NOT EXISTS ix_connector_grants_client_id ON connector_grants (client_id);
CREATE INDEX IF NOT EXISTS ix_connector_grants_user_id ON connector_grants (user_id);

-- identities
CREATE TABLE IF NOT EXISTS identities (
    provider TEXT NOT NULL,
    provider_user_id TEXT NOT NULL,
    user_id UUID NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (provider, provider_user_id),
    CONSTRAINT identities_provider CHECK (provider IN ('google', 'github', 'sso')),
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_identities_user_id ON identities (user_id);

-- connector_tokens
CREATE TABLE IF NOT EXISTS connector_tokens (
    id UUID DEFAULT gen_random_uuid() NOT NULL,
    grant_id UUID NOT NULL,
    kind TEXT NOT NULL,
    token_hash TEXT NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    used_at TIMESTAMP WITH TIME ZONE,
    revoked_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT connector_tokens_kind CHECK (kind IN ('access', 'refresh')),
    FOREIGN KEY(grant_id) REFERENCES connector_grants (id) ON DELETE CASCADE,
    UNIQUE (token_hash)
);
CREATE INDEX IF NOT EXISTS ix_connector_tokens_grant_id ON connector_tokens (grant_id);

-- oauth_codes
CREATE TABLE IF NOT EXISTS oauth_codes (
    code_hash TEXT NOT NULL,
    client_id UUID NOT NULL,
    user_id UUID NOT NULL,
    redirect_uri TEXT NOT NULL,
    code_challenge TEXT NOT NULL,
    scope TEXT NOT NULL,
    resource TEXT NOT NULL,
    grant_id UUID,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    used_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (code_hash),
    FOREIGN KEY(client_id) REFERENCES oauth_clients (id) ON DELETE CASCADE,
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE,
    FOREIGN KEY(grant_id) REFERENCES connector_grants (id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_oauth_codes_client_id ON oauth_codes (client_id);
CREATE INDEX IF NOT EXISTS ix_oauth_codes_user_id ON oauth_codes (user_id);

-- admin_audit, ops_events: every staff request (admin/audit.py) and the server's own warnings and errors
-- (obs/events.py). Neither is ever seen by a session acting for an org (the policies at the end).
CREATE TABLE IF NOT EXISTS admin_audit (
    id UUID DEFAULT gen_random_uuid() NOT NULL,
    at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    staff_user_id UUID NOT NULL,
    staff_email TEXT NOT NULL,
    action TEXT NOT NULL,
    org_id UUID,
    target TEXT,
    detail JSONB DEFAULT '{}'::jsonb NOT NULL,
    outcome TEXT DEFAULT 'ok' NOT NULL,
    PRIMARY KEY (id)
);
CREATE INDEX IF NOT EXISTS admin_audit_at ON admin_audit (at);
CREATE INDEX IF NOT EXISTS admin_audit_org ON admin_audit (org_id, at);

CREATE TABLE IF NOT EXISTS ops_events (
    id UUID DEFAULT gen_random_uuid() NOT NULL,
    first_at TIMESTAMP WITH TIME ZONE NOT NULL,
    last_at TIMESTAMP WITH TIME ZONE NOT NULL,
    severity TEXT NOT NULL,
    kind TEXT NOT NULL,
    source TEXT NOT NULL,
    message TEXT NOT NULL,
    detail JSONB DEFAULT '{}'::jsonb NOT NULL,
    org_id UUID,
    trace_id TEXT,
    count INTEGER DEFAULT 1 NOT NULL,
    acknowledged_at TIMESTAMP WITH TIME ZONE,
    acknowledged_by TEXT,
    PRIMARY KEY (id),
    CONSTRAINT ops_events_severity CHECK (severity IN ('warning', 'error', 'critical')),
    CONSTRAINT ops_events_count CHECK (count > 0)
);
CREATE INDEX IF NOT EXISTS ops_events_last ON ops_events (last_at);

-- traffic_*: Glyphh's own sites' traffic from Cloudflare's analytics (ops/traffic/), pulled by the tick each hour:
-- each zone and what its plan let the last pull have, each day's numbers by zone and host (host '' the whole zone),
-- each day's countries, pages and referrers. Staff only (the policies at the end).
CREATE TABLE IF NOT EXISTS traffic_zones (
    name TEXT NOT NULL,
    zone_id TEXT NOT NULL,
    plan TEXT,
    pulled_at TIMESTAMP WITH TIME ZONE NOT NULL,
    available JSONB DEFAULT '{}'::jsonb NOT NULL,
    PRIMARY KEY (name)
);

CREATE TABLE IF NOT EXISTS traffic_days (
    zone TEXT NOT NULL,
    host TEXT NOT NULL,
    day DATE NOT NULL,
    metric TEXT NOT NULL,
    n BIGINT DEFAULT 0 NOT NULL,
    PRIMARY KEY (zone, host, day, metric)
);

CREATE TABLE IF NOT EXISTS traffic_tops (
    zone TEXT NOT NULL,
    host TEXT NOT NULL,
    day DATE NOT NULL,
    kind TEXT NOT NULL,
    key TEXT NOT NULL,
    n BIGINT DEFAULT 0 NOT NULL,
    PRIMARY KEY (zone, host, day, kind, key)
);

-- orgs.admin_user_id and users.org_id point at each other, so the org's admin is added once both tables exist.
DO $$ BEGIN
  IF NOT EXISTS (SELECT FROM pg_constraint WHERE conname = 'orgs_admin_user_id_fkey') THEN
    ALTER TABLE orgs ADD CONSTRAINT orgs_admin_user_id_fkey
      FOREIGN KEY (admin_user_id) REFERENCES users (id) ON DELETE SET NULL;
  END IF;
END $$;

-- Tenant isolation. A request made with an access token has its org in glyphh.org_id for its transaction
-- (db/tenancy.py), and each policy below shows it only that org's rows. With no org set (sign-in, the OAuth
-- endpoints, Stripe's webhook, the schema step, the staff view and the wind-down command) every row is seen. The
-- policies bind the connecting role itself (FORCE), so no other role is needed; a superuser bypasses them, so the
-- server connects as an ordinary role.
ALTER TABLE orgs ENABLE ROW LEVEL SECURITY;
ALTER TABLE orgs FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant ON orgs;
CREATE POLICY tenant ON orgs USING (nullif(current_setting('glyphh.org_id', true), '') IS NULL OR id = nullif(current_setting('glyphh.org_id', true), '')::uuid);
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE users FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant ON users;
CREATE POLICY tenant ON users USING (nullif(current_setting('glyphh.org_id', true), '') IS NULL OR org_id = nullif(current_setting('glyphh.org_id', true), '')::uuid);
ALTER TABLE invites ENABLE ROW LEVEL SECURITY;
ALTER TABLE invites FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant ON invites;
CREATE POLICY tenant ON invites USING (nullif(current_setting('glyphh.org_id', true), '') IS NULL OR org_id = nullif(current_setting('glyphh.org_id', true), '')::uuid);
ALTER TABLE ada_meter_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE ada_meter_events FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant ON ada_meter_events;
CREATE POLICY tenant ON ada_meter_events USING (nullif(current_setting('glyphh.org_id', true), '') IS NULL OR org_id = nullif(current_setting('glyphh.org_id', true), '')::uuid);
ALTER TABLE llm_ledger ENABLE ROW LEVEL SECURITY;
ALTER TABLE llm_ledger FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant ON llm_ledger;
CREATE POLICY tenant ON llm_ledger USING (nullif(current_setting('glyphh.org_id', true), '') IS NULL OR org_id = nullif(current_setting('glyphh.org_id', true), '')::uuid);
ALTER TABLE llm_balances ENABLE ROW LEVEL SECURITY;
ALTER TABLE llm_balances FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant ON llm_balances;
CREATE POLICY tenant ON llm_balances USING (nullif(current_setting('glyphh.org_id', true), '') IS NULL OR org_id = nullif(current_setting('glyphh.org_id', true), '')::uuid);
ALTER TABLE identities ENABLE ROW LEVEL SECURITY;
ALTER TABLE identities FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant ON identities;
CREATE POLICY tenant ON identities USING (nullif(current_setting('glyphh.org_id', true), '') IS NULL OR user_id IN (SELECT id FROM users));
ALTER TABLE connector_grants ENABLE ROW LEVEL SECURITY;
ALTER TABLE connector_grants FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant ON connector_grants;
CREATE POLICY tenant ON connector_grants USING (nullif(current_setting('glyphh.org_id', true), '') IS NULL OR user_id IN (SELECT id FROM users));
ALTER TABLE connector_tokens ENABLE ROW LEVEL SECURITY;
ALTER TABLE connector_tokens FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant ON connector_tokens;
CREATE POLICY tenant ON connector_tokens USING (nullif(current_setting('glyphh.org_id', true), '') IS NULL OR grant_id IN (SELECT id FROM connector_grants));
ALTER TABLE oauth_codes ENABLE ROW LEVEL SECURITY;
ALTER TABLE oauth_codes FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant ON oauth_codes;
CREATE POLICY tenant ON oauth_codes USING (nullif(current_setting('glyphh.org_id', true), '') IS NULL OR user_id IN (SELECT id FROM users));
-- Staff only: a session acting for an org sees no row of these.
ALTER TABLE admin_audit ENABLE ROW LEVEL SECURITY;
ALTER TABLE admin_audit FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS staff ON admin_audit;
CREATE POLICY staff ON admin_audit USING (nullif(current_setting('glyphh.org_id', true), '') IS NULL);
ALTER TABLE ops_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE ops_events FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS staff ON ops_events;
CREATE POLICY staff ON ops_events USING (nullif(current_setting('glyphh.org_id', true), '') IS NULL);
ALTER TABLE traffic_zones ENABLE ROW LEVEL SECURITY;
ALTER TABLE traffic_zones FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS staff ON traffic_zones;
CREATE POLICY staff ON traffic_zones USING (nullif(current_setting('glyphh.org_id', true), '') IS NULL);
ALTER TABLE traffic_days ENABLE ROW LEVEL SECURITY;
ALTER TABLE traffic_days FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS staff ON traffic_days;
CREATE POLICY staff ON traffic_days USING (nullif(current_setting('glyphh.org_id', true), '') IS NULL);
ALTER TABLE traffic_tops ENABLE ROW LEVEL SECURITY;
ALTER TABLE traffic_tops FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS staff ON traffic_tops;
CREATE POLICY staff ON traffic_tops USING (nullif(current_setting('glyphh.org_id', true), '') IS NULL);
