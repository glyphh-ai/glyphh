-- The Glyphh database: every table, index, and the tenant role and its row-level security. The one source of the
-- schema; the server runs it before it starts (db/schema.py), so every statement here is safe to run again. Until
-- launch there are no migrations: a change to a table means resetting the development database
-- (`docker compose down -v`). The models in glyphh_server.models map these tables for queries, and
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

-- fly_rates
CREATE TABLE IF NOT EXISTS fly_rates (
    item TEXT NOT NULL,
    region TEXT NOT NULL,
    usd_per_30_days NUMERIC(12, 4) NOT NULL,
    effective_from DATE NOT NULL,
    source TEXT NOT NULL,
    PRIMARY KEY (item, region, effective_from),
    CONSTRAINT fly_rates_item CHECK (item IN ('small', 'medium', 'large', 'volume')),
    CONSTRAINT fly_rates_rate CHECK (usd_per_30_days >= 0)
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
    hosting_markup_pct INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT plan_versions_version UNIQUE (plan_id, version),
    CONSTRAINT plan_versions_price CHECK (coalesce(price_cents, 0) >= 0),
    CONSTRAINT plan_versions_interval CHECK (billing_interval IN ('month', 'year')),
    CONSTRAINT plan_versions_limits CHECK (coalesce(max_machines, 0) >= 0 AND coalesce(precedents, 0) >= 0),
    CONSTRAINT plan_versions_markup CHECK (coalesce(hosting_markup_pct, 0) >= 0),
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
    markup_pct INTEGER,
    plan_until TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT orgs_markup CHECK (coalesce(markup_pct, 0) >= 0),
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

-- machine_months
CREATE TABLE IF NOT EXISTS machine_months (
    rrotor_id UUID NOT NULL,
    month TEXT NOT NULL,
    org_id UUID NOT NULL,
    name TEXT NOT NULL,
    size TEXT NOT NULL,
    cost_micros BIGINT DEFAULT 0 NOT NULL,
    charge_micros BIGINT DEFAULT 0 NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (rrotor_id, month),
    FOREIGN KEY(org_id) REFERENCES orgs (id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_machine_months_org_id ON machine_months (org_id);

-- meter_events
CREATE TABLE IF NOT EXISTS meter_events (
    id UUID DEFAULT gen_random_uuid() NOT NULL,
    org_id UUID NOT NULL,
    customer TEXT NOT NULL,
    cents INTEGER NOT NULL,
    at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    sent_at TIMESTAMP WITH TIME ZONE,
    PRIMARY KEY (id),
    CONSTRAINT meter_events_cents CHECK (cents > 0),
    FOREIGN KEY(org_id) REFERENCES orgs (id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_meter_events_org_id ON meter_events (org_id);

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
    CONSTRAINT identities_provider CHECK (provider IN ('google', 'github')),
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_identities_user_id ON identities (user_id);

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

-- models
CREATE TABLE IF NOT EXISTS models (
    id UUID DEFAULT gen_random_uuid() NOT NULL,
    user_id UUID NOT NULL,
    org_id UUID NOT NULL,
    name TEXT NOT NULL,
    repo TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE,
    FOREIGN KEY(org_id) REFERENCES orgs (id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS ix_models_org_id ON models (org_id);
CREATE INDEX IF NOT EXISTS ix_models_user_id ON models (user_id);

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

-- model_versions
CREATE TABLE IF NOT EXISTS model_versions (
    id UUID DEFAULT gen_random_uuid() NOT NULL,
    model_id UUID NOT NULL,
    version INTEGER NOT NULL,
    commit_sha TEXT NOT NULL,
    manifest JSON NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT model_versions_version UNIQUE (model_id, version),
    CONSTRAINT model_versions_commit UNIQUE (model_id, commit_sha),
    FOREIGN KEY(model_id) REFERENCES models (id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_model_versions_model_id ON model_versions (model_id);

-- routine_triggers
CREATE TABLE IF NOT EXISTS routine_triggers (
    id UUID DEFAULT gen_random_uuid() NOT NULL,
    user_id UUID NOT NULL,
    model_id UUID,
    name TEXT NOT NULL,
    fire_url TEXT NOT NULL,
    token_enc TEXT NOT NULL,
    status TEXT DEFAULT 'ok' NOT NULL,
    last_fired_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT routine_triggers_status CHECK (status IN ('ok', 'broken')),
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE,
    FOREIGN KEY(model_id) REFERENCES models (id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS ix_routine_triggers_model_id ON routine_triggers (model_id);
CREATE INDEX IF NOT EXISTS ix_routine_triggers_user_id ON routine_triggers (user_id);

-- rrotors
CREATE TABLE IF NOT EXISTS rrotors (
    id UUID DEFAULT gen_random_uuid() NOT NULL,
    user_id UUID NOT NULL,
    mode TEXT NOT NULL,
    install_id UUID,
    fly_machine_id TEXT,
    fly_volume_id TEXT,
    month TEXT,
    month_seconds INTEGER DEFAULT 0 NOT NULL,
    metered_at TIMESTAMP WITH TIME ZONE,
    region TEXT,
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
    size TEXT,
    precedents BIGINT,
    precedents_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT rrotors_mode CHECK (mode IN ('hosted', 'local', 'self')),
    CONSTRAINT rrotors_local_install CHECK ((mode = 'local') = (install_id IS NOT NULL)),
    CONSTRAINT rrotors_self_address CHECK ((mode = 'self') = (public_url IS NOT NULL AND name IS NOT NULL)),
    CONSTRAINT rrotors_hosted_machine CHECK ((mode = 'hosted') = (size IS NOT NULL AND name IS NOT NULL)),
    CONSTRAINT rrotors_size CHECK (size IN ('small', 'medium', 'large')),
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE,
    UNIQUE (install_id),
    FOREIGN KEY(install_id) REFERENCES installs (id) ON DELETE CASCADE,
    UNIQUE (token_hash)
);
CREATE INDEX IF NOT EXISTS ix_rrotors_user_id ON rrotors (user_id);

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

-- telemetry_logs, telemetry_metrics, telemetry_spans: server-side logging (OTLP), kept GLYPHH_TELEMETRY_RETENTION_DAYS
CREATE TABLE IF NOT EXISTS telemetry_logs (
    id UUID DEFAULT gen_random_uuid() NOT NULL,
    org_id UUID NOT NULL,
    rrotor_id UUID NOT NULL,
    node_id TEXT,
    at TIMESTAMP WITH TIME ZONE NOT NULL,
    severity INTEGER NOT NULL,
    level TEXT NOT NULL,
    body TEXT NOT NULL,
    audit TEXT,
    trace_id TEXT,
    span_id TEXT,
    attributes JSONB NOT NULL,
    received_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(org_id) REFERENCES orgs (id) ON DELETE CASCADE,
    FOREIGN KEY(rrotor_id) REFERENCES rrotors (id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_telemetry_logs_rrotor_id ON telemetry_logs (rrotor_id);
CREATE INDEX IF NOT EXISTS telemetry_logs_newest ON telemetry_logs (org_id, at, id);
CREATE INDEX IF NOT EXISTS telemetry_logs_at ON telemetry_logs (at);

CREATE TABLE IF NOT EXISTS telemetry_metrics (
    id UUID DEFAULT gen_random_uuid() NOT NULL,
    org_id UUID NOT NULL,
    rrotor_id UUID NOT NULL,
    node_id TEXT,
    series TEXT NOT NULL,
    name TEXT NOT NULL,
    unit TEXT NOT NULL,
    kind TEXT NOT NULL,
    minute TIMESTAMP WITH TIME ZONE NOT NULL,
    at TIMESTAMP WITH TIME ZONE NOT NULL,
    value DOUBLE PRECISION,
    count BIGINT,
    attributes JSONB NOT NULL,
    received_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(org_id) REFERENCES orgs (id) ON DELETE CASCADE,
    FOREIGN KEY(rrotor_id) REFERENCES rrotors (id) ON DELETE CASCADE
);
CREATE UNIQUE INDEX IF NOT EXISTS telemetry_metrics_point ON telemetry_metrics (rrotor_id, series, minute);
CREATE INDEX IF NOT EXISTS telemetry_metrics_newest ON telemetry_metrics (org_id, name, at);
CREATE INDEX IF NOT EXISTS telemetry_metrics_at ON telemetry_metrics (at);

CREATE TABLE IF NOT EXISTS telemetry_spans (
    id UUID DEFAULT gen_random_uuid() NOT NULL,
    org_id UUID NOT NULL,
    rrotor_id UUID NOT NULL,
    node_id TEXT,
    trace_id TEXT NOT NULL,
    span_id TEXT NOT NULL,
    parent_span_id TEXT,
    name TEXT NOT NULL,
    kind TEXT NOT NULL,
    started_at TIMESTAMP WITH TIME ZONE NOT NULL,
    ended_at TIMESTAMP WITH TIME ZONE NOT NULL,
    status TEXT NOT NULL,
    attributes JSONB NOT NULL,
    received_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(org_id) REFERENCES orgs (id) ON DELETE CASCADE,
    FOREIGN KEY(rrotor_id) REFERENCES rrotors (id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_telemetry_spans_rrotor_id ON telemetry_spans (rrotor_id);
CREATE INDEX IF NOT EXISTS telemetry_spans_newest ON telemetry_spans (org_id, started_at);
CREATE INDEX IF NOT EXISTS telemetry_spans_at ON telemetry_spans (started_at);

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
    PRIMARY KEY (id),
    FOREIGN KEY(rrotor_id) REFERENCES rrotors (id) ON DELETE CASCADE,
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE,
    UNIQUE (key_hash)
);
CREATE INDEX IF NOT EXISTS ix_runtime_keys_rrotor_id ON runtime_keys (rrotor_id);
CREATE INDEX IF NOT EXISTS ix_runtime_keys_user_id ON runtime_keys (user_id);
CREATE UNIQUE INDEX IF NOT EXISTS rrotors_hosted_name ON rrotors (user_id, name) WHERE mode = 'hosted';
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

-- deployments
CREATE TABLE IF NOT EXISTS deployments (
    rrotor_id UUID NOT NULL,
    model_version_id UUID NOT NULL,
    deployed_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    active BOOLEAN DEFAULT true NOT NULL,
    PRIMARY KEY (rrotor_id, model_version_id),
    FOREIGN KEY(rrotor_id) REFERENCES rrotors (id) ON DELETE CASCADE,
    FOREIGN KEY(model_version_id) REFERENCES model_versions (id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_deployments_model_version_id ON deployments (model_version_id);

-- model_events
CREATE TABLE IF NOT EXISTS model_events (
    id UUID DEFAULT gen_random_uuid() NOT NULL,
    model_id UUID NOT NULL,
    routine_trigger_id UUID,
    kind TEXT NOT NULL,
    session_url TEXT,
    at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(model_id) REFERENCES models (id) ON DELETE CASCADE,
    FOREIGN KEY(routine_trigger_id) REFERENCES routine_triggers (id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_model_events_model_id ON model_events (model_id);
CREATE INDEX IF NOT EXISTS ix_model_events_routine_trigger_id ON model_events (routine_trigger_id);

-- runs
CREATE TABLE IF NOT EXISTS runs (
    id UUID DEFAULT gen_random_uuid() NOT NULL,
    model_version_id UUID NOT NULL,
    rrotor_id UUID NOT NULL,
    function TEXT NOT NULL,
    caller TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    ended_at TIMESTAMP WITH TIME ZONE,
    seconds INTEGER,
    PRIMARY KEY (id),
    CONSTRAINT runs_caller CHECK (caller IN ('routine', 'claude', 'panel', 'test')),
    FOREIGN KEY(model_version_id) REFERENCES model_versions (id) ON DELETE CASCADE,
    FOREIGN KEY(rrotor_id) REFERENCES rrotors (id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_runs_model_version_id ON runs (model_version_id);
CREATE INDEX IF NOT EXISTS ix_runs_rrotor_id ON runs (rrotor_id);

-- approvals
CREATE TABLE IF NOT EXISTS approvals (
    id UUID DEFAULT gen_random_uuid() NOT NULL,
    run_id UUID NOT NULL,
    step TEXT NOT NULL,
    prompt TEXT NOT NULL,
    answer TEXT,
    asked_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    notified_at TIMESTAMP WITH TIME ZONE,
    answered_at TIMESTAMP WITH TIME ZONE,
    PRIMARY KEY (id),
    FOREIGN KEY(run_id) REFERENCES runs (id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_approvals_run_id ON approvals (run_id);

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
ALTER TABLE machine_months ENABLE ROW LEVEL SECURITY;
ALTER TABLE machine_months FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant ON machine_months;
CREATE POLICY tenant ON machine_months USING (nullif(current_setting('glyphh.org_id', true), '') IS NULL OR org_id = nullif(current_setting('glyphh.org_id', true), '')::uuid);
ALTER TABLE meter_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE meter_events FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant ON meter_events;
CREATE POLICY tenant ON meter_events USING (nullif(current_setting('glyphh.org_id', true), '') IS NULL OR org_id = nullif(current_setting('glyphh.org_id', true), '')::uuid);
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
ALTER TABLE routine_triggers ENABLE ROW LEVEL SECURITY;
ALTER TABLE routine_triggers FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant ON routine_triggers;
CREATE POLICY tenant ON routine_triggers USING (nullif(current_setting('glyphh.org_id', true), '') IS NULL OR user_id IN (SELECT id FROM users));
ALTER TABLE models ENABLE ROW LEVEL SECURITY;
ALTER TABLE models FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant ON models;
CREATE POLICY tenant ON models USING (nullif(current_setting('glyphh.org_id', true), '') IS NULL OR org_id = nullif(current_setting('glyphh.org_id', true), '')::uuid);
ALTER TABLE model_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE model_versions FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant ON model_versions;
CREATE POLICY tenant ON model_versions USING (nullif(current_setting('glyphh.org_id', true), '') IS NULL OR model_id IN (SELECT id FROM models));
ALTER TABLE deployments ENABLE ROW LEVEL SECURITY;
ALTER TABLE deployments FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant ON deployments;
CREATE POLICY tenant ON deployments USING (nullif(current_setting('glyphh.org_id', true), '') IS NULL OR model_version_id IN (SELECT id FROM model_versions));
ALTER TABLE runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE runs FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant ON runs;
CREATE POLICY tenant ON runs USING (nullif(current_setting('glyphh.org_id', true), '') IS NULL OR model_version_id IN (SELECT id FROM model_versions));
ALTER TABLE approvals ENABLE ROW LEVEL SECURITY;
ALTER TABLE approvals FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant ON approvals;
CREATE POLICY tenant ON approvals USING (nullif(current_setting('glyphh.org_id', true), '') IS NULL OR run_id IN (SELECT id FROM runs));
ALTER TABLE model_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE model_events FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant ON model_events;
CREATE POLICY tenant ON model_events USING (nullif(current_setting('glyphh.org_id', true), '') IS NULL OR model_id IN (SELECT id FROM models));
ALTER TABLE licenses ENABLE ROW LEVEL SECURITY;
ALTER TABLE licenses FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant ON licenses;
CREATE POLICY tenant ON licenses USING (nullif(current_setting('glyphh.org_id', true), '') IS NULL OR org_id = nullif(current_setting('glyphh.org_id', true), '')::uuid);
ALTER TABLE nodes ENABLE ROW LEVEL SECURITY;
ALTER TABLE nodes FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant ON nodes;
CREATE POLICY tenant ON nodes USING (nullif(current_setting('glyphh.org_id', true), '') IS NULL OR rrotor_id IN (SELECT id FROM rrotors));
ALTER TABLE telemetry_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE telemetry_logs FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant ON telemetry_logs;
CREATE POLICY tenant ON telemetry_logs USING (nullif(current_setting('glyphh.org_id', true), '') IS NULL OR org_id = nullif(current_setting('glyphh.org_id', true), '')::uuid);
ALTER TABLE telemetry_metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE telemetry_metrics FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant ON telemetry_metrics;
CREATE POLICY tenant ON telemetry_metrics USING (nullif(current_setting('glyphh.org_id', true), '') IS NULL OR org_id = nullif(current_setting('glyphh.org_id', true), '')::uuid);
ALTER TABLE telemetry_spans ENABLE ROW LEVEL SECURITY;
ALTER TABLE telemetry_spans FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant ON telemetry_spans;
CREATE POLICY tenant ON telemetry_spans USING (nullif(current_setting('glyphh.org_id', true), '') IS NULL OR org_id = nullif(current_setting('glyphh.org_id', true), '')::uuid);
