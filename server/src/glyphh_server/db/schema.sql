-- The Glyphh database: every table, index, and the tenant role and its row-level security. The one source of the
-- schema's latest shape; the server runs it before it starts (db/schema.py), so every statement here is safe to run
-- again. Production keeps its data, so a change here comes with a migration, db/migrations/NNNN_name.sql, that brings
-- an existing database to it; tests/db/test_migrations.py fails when tests/db/baseline.sql and the migrations do not
-- make what this file makes. The models in glyphh_server.models map these tables for queries, and
-- tests/db/test_schema_sql.py fails when they disagree.

-- mods
CREATE TABLE IF NOT EXISTS mods (
    slug TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    active BOOLEAN DEFAULT true NOT NULL,
    sort INTEGER DEFAULT 0 NOT NULL,
    PRIMARY KEY (slug)
);

-- oauth_clients
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

-- plan_versions
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
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT plan_versions_version UNIQUE (plan_id, version),
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

-- ada_usage
CREATE TABLE IF NOT EXISTS ada_usage (
    org_id UUID NOT NULL,
    period TEXT NOT NULL,
    requests BIGINT DEFAULT 0 NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (org_id, period),
    CONSTRAINT ada_usage_requests CHECK (requests >= 0),
    FOREIGN KEY(org_id) REFERENCES orgs (id) ON DELETE CASCADE
);

-- ada_model_days
CREATE TABLE IF NOT EXISTS ada_model_days (
    org_id UUID NOT NULL,
    model TEXT NOT NULL,
    day DATE NOT NULL,
    metric TEXT NOT NULL,
    n BIGINT DEFAULT 0 NOT NULL,
    PRIMARY KEY (org_id, model, day, metric),
    FOREIGN KEY(org_id) REFERENCES orgs (id) ON DELETE CASCADE
);

-- ada_meter_events
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

-- licenses
CREATE TABLE IF NOT EXISTS licenses (
    id UUID NOT NULL,
    org_id UUID NOT NULL,
    tier TEXT NOT NULL,
    max_nodes INTEGER,
    max_precedents INTEGER,
    cluster_sync_enabled BOOLEAN NOT NULL,
    issued_at TIMESTAMP WITH TIME ZONE NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    customer_id TEXT NOT NULL,
    revoked_at TIMESTAMP WITH TIME ZONE,
    key TEXT NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT licenses_tier CHECK (tier IN ('free', 'pro', 'team', 'enterprise')),
    CONSTRAINT licenses_limits CHECK (coalesce(max_nodes, 1) >= 1 AND coalesce(max_precedents, 0) >= 0),
    FOREIGN KEY(org_id) REFERENCES orgs (id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS licenses_newest ON licenses (org_id, issued_at);

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

-- connector_grants
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

-- github_installations
CREATE TABLE IF NOT EXISTS github_installations (
    id UUID DEFAULT gen_random_uuid() NOT NULL,
    user_id UUID NOT NULL,
    installation_id BIGINT NOT NULL,
    account_login TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    removed_at TIMESTAMP WITH TIME ZONE,
    PRIMARY KEY (id),
    UNIQUE (user_id),
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE,
    UNIQUE (installation_id)
);

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

-- org_sso: an org's single sign-on by OpenID Connect (Enterprise); the client secret is sealed (ops/auth/sealed.py)
CREATE TABLE IF NOT EXISTS org_sso (
    org_id UUID NOT NULL,
    issuer TEXT NOT NULL,
    client_id TEXT NOT NULL,
    client_secret TEXT NOT NULL,
    enforced BOOLEAN DEFAULT false NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    reviewers TEXT[] DEFAULT '{}'::text[] NOT NULL,
    PRIMARY KEY (org_id),
    FOREIGN KEY(org_id) REFERENCES orgs (id) ON DELETE CASCADE
);

-- sso_domains: the email domains that route a sign-in to an org's single sign-on; a domain is one org's
CREATE TABLE IF NOT EXISTS sso_domains (
    domain TEXT NOT NULL,
    org_id UUID NOT NULL,
    PRIMARY KEY (domain),
    FOREIGN KEY(org_id) REFERENCES org_sso (org_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_sso_domains_org_id ON sso_domains (org_id);

-- installs
CREATE TABLE IF NOT EXISTS installs (
    id UUID DEFAULT gen_random_uuid() NOT NULL,
    user_id UUID NOT NULL,
    machine_id TEXT NOT NULL,
    name TEXT NOT NULL,
    surface TEXT NOT NULL,
    mod_version TEXT NOT NULL,
    last_seen_at TIMESTAMP WITH TIME ZONE,
    revoked_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT installs_surface CHECK (surface IN ('desktop', 'cli')),
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);
CREATE UNIQUE INDEX IF NOT EXISTS installs_user_machine ON installs (user_id, machine_id) WHERE revoked_at IS NULL;
CREATE INDEX IF NOT EXISTS ix_installs_user_id ON installs (user_id);

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

-- device_codes
CREATE TABLE IF NOT EXISTS device_codes (
    device_code_hash TEXT NOT NULL,
    user_code TEXT NOT NULL,
    install_id UUID,
    machine_id TEXT NOT NULL,
    name TEXT NOT NULL,
    surface TEXT NOT NULL,
    mod_version TEXT NOT NULL,
    interval INTEGER DEFAULT 5 NOT NULL,
    polled_at TIMESTAMP WITH TIME ZONE,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    approved_at TIMESTAMP WITH TIME ZONE,
    denied_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (device_code_hash),
    CONSTRAINT device_codes_surface CHECK (surface IN ('desktop', 'cli')),
    CONSTRAINT device_codes_one_answer CHECK (approved_at IS NULL OR denied_at IS NULL),
    UNIQUE (user_code),
    FOREIGN KEY(install_id) REFERENCES installs (id) ON DELETE CASCADE
);

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

-- rrotors
CREATE TABLE IF NOT EXISTS rrotors (
    id UUID DEFAULT gen_random_uuid() NOT NULL,
    user_id UUID NOT NULL,
    mode TEXT NOT NULL,
    install_id UUID,
    image_version TEXT,
    state TEXT NOT NULL,
    token_hash TEXT NOT NULL,
    last_seen_at TIMESTAMP WITH TIME ZONE,
    seq BIGINT DEFAULT 0 NOT NULL,
    name TEXT,
    public_url TEXT,
    last_heartbeat_at TIMESTAMP WITH TIME ZONE,
    machine_hash TEXT,
    active_runs INTEGER,
    precedents BIGINT,
    precedents_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT rrotors_mode CHECK (mode IN ('local', 'self')),
    CONSTRAINT rrotors_local_install CHECK ((mode = 'local') = (install_id IS NOT NULL)),
    CONSTRAINT rrotors_self_address CHECK ((mode = 'self') = (public_url IS NOT NULL AND name IS NOT NULL)),
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE,
    UNIQUE (install_id),
    FOREIGN KEY(install_id) REFERENCES installs (id) ON DELETE CASCADE,
    UNIQUE (token_hash)
);
CREATE INDEX IF NOT EXISTS ix_rrotors_user_id ON rrotors (user_id);

-- apps: the catalogue of apps on an org's rrotors (docs/specs/apps.md), one row per app per rrotor
CREATE TABLE IF NOT EXISTS apps (
    id UUID DEFAULT gen_random_uuid() NOT NULL,
    org_id UUID NOT NULL,
    runtime_id UUID NOT NULL,
    name TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    type TEXT DEFAULT 'page' NOT NULL,
    version INTEGER NOT NULL,
    commit_sha TEXT NOT NULL,
    roles TEXT[] DEFAULT '{}'::text[] NOT NULL,
    state TEXT DEFAULT 'draft' NOT NULL,
    submitted_by UUID,
    submitted_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    reviewed_by UUID,
    reviewed_at TIMESTAMP WITH TIME ZONE,
    reason TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT apps_state CHECK (state IN ('draft', 'approved', 'rejected', 'retired')),
    CONSTRAINT apps_type CHECK (type IN ('page', 'dashboard', 'doc', 'diagram', 'deck', 'design')),
    FOREIGN KEY(org_id) REFERENCES orgs (id) ON DELETE CASCADE,
    FOREIGN KEY(runtime_id) REFERENCES rrotors (id) ON DELETE CASCADE,
    FOREIGN KEY(submitted_by) REFERENCES users (id) ON DELETE SET NULL,
    FOREIGN KEY(reviewed_by) REFERENCES users (id) ON DELETE SET NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS apps_one_per_app ON apps (runtime_id, name);
CREATE INDEX IF NOT EXISTS ix_apps_org_id ON apps (org_id);

-- templates: the template library Glyphh ships (docs/specs/templates.md), seeded at every start; not an org's
CREATE TABLE IF NOT EXISTS templates (
    slug TEXT NOT NULL,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    summary TEXT NOT NULL,
    version INTEGER NOT NULL,
    body JSONB NOT NULL,
    active BOOLEAN DEFAULT true NOT NULL,
    sort INTEGER DEFAULT 0 NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (slug)
);

-- template_installs: each person's installed templates, one per template
CREATE TABLE IF NOT EXISTS template_installs (
    id UUID DEFAULT gen_random_uuid() NOT NULL,
    org_id UUID NOT NULL,
    user_id UUID NOT NULL,
    slug TEXT NOT NULL,
    version INTEGER NOT NULL,
    made TEXT[] DEFAULT '{}'::text[] NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(org_id) REFERENCES orgs (id) ON DELETE CASCADE,
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE,
    FOREIGN KEY(slug) REFERENCES templates (slug) ON DELETE CASCADE
);
CREATE UNIQUE INDEX IF NOT EXISTS template_installs_one_per_person ON template_installs (user_id, slug);
CREATE INDEX IF NOT EXISTS ix_template_installs_org_id ON template_installs (org_id);

-- nodes
CREATE TABLE IF NOT EXISTS nodes (
    rrotor_id UUID NOT NULL,
    node_id TEXT NOT NULL,
    cluster_id UUID,
    role TEXT,
    precedents BIGINT,
    version TEXT,
    seen_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (rrotor_id, node_id),
    CONSTRAINT nodes_role CHECK (role IN ('standalone', 'head', 'follower')),
    FOREIGN KEY(rrotor_id) REFERENCES rrotors (id) ON DELETE CASCADE
);

-- runtime_keys
CREATE TABLE IF NOT EXISTS runtime_keys (
    id UUID DEFAULT gen_random_uuid() NOT NULL,
    rrotor_id UUID,
    user_id UUID NOT NULL,
    name TEXT NOT NULL,
    key_hash TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE,
    revoked_at TIMESTAMP WITH TIME ZONE,
    calls BIGINT DEFAULT 0 NOT NULL,
    last_used_at TIMESTAMP WITH TIME ZONE,
    scope TEXT DEFAULT 'runtime' NOT NULL,
    clearance NUMERIC(4, 3) DEFAULT 1 NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(rrotor_id) REFERENCES rrotors (id) ON DELETE CASCADE,
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE,
    UNIQUE (key_hash),
    CONSTRAINT runtime_keys_scope CHECK (scope IN ('runtime', 'cloud')),
    CONSTRAINT runtime_keys_clearance CHECK (clearance >= 0 AND clearance <= 1)
);
CREATE INDEX IF NOT EXISTS ix_runtime_keys_rrotor_id ON runtime_keys (rrotor_id);
CREATE INDEX IF NOT EXISTS ix_runtime_keys_user_id ON runtime_keys (user_id);
CREATE UNIQUE INDEX IF NOT EXISTS rrotors_self_url ON rrotors (user_id, public_url) WHERE mode = 'self';
CREATE INDEX IF NOT EXISTS rrotors_self_host ON rrotors (public_url) WHERE mode = 'self';

-- tokens
CREATE TABLE IF NOT EXISTS tokens (
    id UUID DEFAULT gen_random_uuid() NOT NULL,
    install_id UUID NOT NULL,
    token_hash TEXT NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    revoked_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(install_id) REFERENCES installs (id) ON DELETE CASCADE,
    UNIQUE (token_hash)
);
CREATE INDEX IF NOT EXISTS ix_tokens_install_id ON tokens (install_id);

-- admin_audit: every request Glyphh's staff make of the staff view (glyphh_server/admin/audit.py): who, what, when,
-- which org. ops_events: the server's own errors and warnings, alike ones in a minute folded into one row with a count
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

-- traffic_*: Glyphh's own sites' traffic from Cloudflare's analytics (ops/traffic.py), pulled by the tick each hour:
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

-- github_traffic_*: Glyphh's public repositories' traffic from GitHub (ops/traffic/github.py), pulled by the tick each
-- hour: each repository's last 14 days as last pulled, each day's views and clones (kept beyond GitHub's 14 days),
-- each day's pull of its popular referrers and paths. Staff only (the policies at the end).
CREATE TABLE IF NOT EXISTS github_traffic_repos (
    repo TEXT NOT NULL,
    pulled_at TIMESTAMP WITH TIME ZONE NOT NULL,
    views BIGINT DEFAULT 0 NOT NULL,
    view_uniques BIGINT DEFAULT 0 NOT NULL,
    clones BIGINT DEFAULT 0 NOT NULL,
    clone_uniques BIGINT DEFAULT 0 NOT NULL,
    PRIMARY KEY (repo)
);

CREATE TABLE IF NOT EXISTS github_traffic_days (
    repo TEXT NOT NULL,
    day DATE NOT NULL,
    views BIGINT DEFAULT 0 NOT NULL,
    view_uniques BIGINT DEFAULT 0 NOT NULL,
    clones BIGINT DEFAULT 0 NOT NULL,
    clone_uniques BIGINT DEFAULT 0 NOT NULL,
    PRIMARY KEY (repo, day)
);

CREATE TABLE IF NOT EXISTS github_traffic_tops (
    repo TEXT NOT NULL,
    pulled_on DATE NOT NULL,
    kind TEXT NOT NULL,
    key TEXT NOT NULL,
    count BIGINT DEFAULT 0 NOT NULL,
    uniques BIGINT DEFAULT 0 NOT NULL,
    PRIMARY KEY (repo, pulled_on, kind, key)
);

-- orgs.admin_user_id and users.org_id point at each other, so the org's admin is added once both tables exist.
DO $$ BEGIN
  IF NOT EXISTS (SELECT FROM pg_constraint WHERE conname = 'orgs_admin_user_id_fkey') THEN
    ALTER TABLE orgs ADD CONSTRAINT orgs_admin_user_id_fkey
      FOREIGN KEY (admin_user_id) REFERENCES users (id) ON DELETE SET NULL;
  END IF;
END $$;

-- Tenant isolation. A request made with an install's token, or with a connector access token on /mcp, has its org in
-- glyphh.org_id for its transaction (db/tenancy.py), and each policy below shows it only that org's rows. With no org
-- set (sign-in, the connector's OAuth endpoints, Stripe's webhook, the schema step and the few operations that cross
-- orgs on purpose) every row is seen. The policies bind the connecting role itself (FORCE), so no other role is
-- needed; a superuser bypasses them, so the server connects as an ordinary role.
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
ALTER TABLE ada_usage ENABLE ROW LEVEL SECURITY;
ALTER TABLE ada_usage FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant ON ada_usage;
CREATE POLICY tenant ON ada_usage USING (nullif(current_setting('glyphh.org_id', true), '') IS NULL OR org_id = nullif(current_setting('glyphh.org_id', true), '')::uuid);
ALTER TABLE ada_model_days ENABLE ROW LEVEL SECURITY;
ALTER TABLE ada_model_days FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant ON ada_model_days;
CREATE POLICY tenant ON ada_model_days USING (nullif(current_setting('glyphh.org_id', true), '') IS NULL OR org_id = nullif(current_setting('glyphh.org_id', true), '')::uuid);
ALTER TABLE ada_meter_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE ada_meter_events FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant ON ada_meter_events;
CREATE POLICY tenant ON ada_meter_events USING (nullif(current_setting('glyphh.org_id', true), '') IS NULL OR org_id = nullif(current_setting('glyphh.org_id', true), '')::uuid);
ALTER TABLE org_sso ENABLE ROW LEVEL SECURITY;
ALTER TABLE org_sso FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant ON org_sso;
CREATE POLICY tenant ON org_sso USING (nullif(current_setting('glyphh.org_id', true), '') IS NULL OR org_id = nullif(current_setting('glyphh.org_id', true), '')::uuid);
ALTER TABLE sso_domains ENABLE ROW LEVEL SECURITY;
ALTER TABLE sso_domains FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant ON sso_domains;
CREATE POLICY tenant ON sso_domains USING (nullif(current_setting('glyphh.org_id', true), '') IS NULL OR org_id = nullif(current_setting('glyphh.org_id', true), '')::uuid);
ALTER TABLE identities ENABLE ROW LEVEL SECURITY;
ALTER TABLE identities FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant ON identities;
CREATE POLICY tenant ON identities USING (nullif(current_setting('glyphh.org_id', true), '') IS NULL OR user_id IN (SELECT id FROM users));
ALTER TABLE installs ENABLE ROW LEVEL SECURITY;
ALTER TABLE installs FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant ON installs;
CREATE POLICY tenant ON installs USING (nullif(current_setting('glyphh.org_id', true), '') IS NULL OR user_id IN (SELECT id FROM users));
ALTER TABLE tokens ENABLE ROW LEVEL SECURITY;
ALTER TABLE tokens FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant ON tokens;
CREATE POLICY tenant ON tokens USING (nullif(current_setting('glyphh.org_id', true), '') IS NULL OR install_id IN (SELECT id FROM installs));
ALTER TABLE rrotors ENABLE ROW LEVEL SECURITY;
ALTER TABLE rrotors FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant ON rrotors;
CREATE POLICY tenant ON rrotors USING (nullif(current_setting('glyphh.org_id', true), '') IS NULL OR user_id IN (SELECT id FROM users));
ALTER TABLE apps ENABLE ROW LEVEL SECURITY;
ALTER TABLE apps FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant ON apps;
CREATE POLICY tenant ON apps USING (nullif(current_setting('glyphh.org_id', true), '') IS NULL OR org_id = nullif(current_setting('glyphh.org_id', true), '')::uuid);
ALTER TABLE template_installs ENABLE ROW LEVEL SECURITY;
ALTER TABLE template_installs FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant ON template_installs;
CREATE POLICY tenant ON template_installs USING (nullif(current_setting('glyphh.org_id', true), '') IS NULL OR org_id = nullif(current_setting('glyphh.org_id', true), '')::uuid);
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
ALTER TABLE github_installations ENABLE ROW LEVEL SECURITY;
ALTER TABLE github_installations FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant ON github_installations;
CREATE POLICY tenant ON github_installations USING (nullif(current_setting('glyphh.org_id', true), '') IS NULL OR user_id IN (SELECT id FROM users));
ALTER TABLE runtime_keys ENABLE ROW LEVEL SECURITY;
ALTER TABLE runtime_keys FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant ON runtime_keys;
CREATE POLICY tenant ON runtime_keys USING (nullif(current_setting('glyphh.org_id', true), '') IS NULL OR user_id IN (SELECT id FROM users));
ALTER TABLE licenses ENABLE ROW LEVEL SECURITY;
ALTER TABLE licenses FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant ON licenses;
CREATE POLICY tenant ON licenses USING (nullif(current_setting('glyphh.org_id', true), '') IS NULL OR org_id = nullif(current_setting('glyphh.org_id', true), '')::uuid);
ALTER TABLE nodes ENABLE ROW LEVEL SECURITY;
ALTER TABLE nodes FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant ON nodes;
CREATE POLICY tenant ON nodes USING (nullif(current_setting('glyphh.org_id', true), '') IS NULL OR rrotor_id IN (SELECT id FROM rrotors));
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
ALTER TABLE github_traffic_repos ENABLE ROW LEVEL SECURITY;
ALTER TABLE github_traffic_repos FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS staff ON github_traffic_repos;
CREATE POLICY staff ON github_traffic_repos USING (nullif(current_setting('glyphh.org_id', true), '') IS NULL);
ALTER TABLE github_traffic_days ENABLE ROW LEVEL SECURITY;
ALTER TABLE github_traffic_days FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS staff ON github_traffic_days;
CREATE POLICY staff ON github_traffic_days USING (nullif(current_setting('glyphh.org_id', true), '') IS NULL);
ALTER TABLE github_traffic_tops ENABLE ROW LEVEL SECURITY;
ALTER TABLE github_traffic_tops FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS staff ON github_traffic_tops;
CREATE POLICY staff ON github_traffic_tops USING (nullif(current_setting('glyphh.org_id', true), '') IS NULL);
