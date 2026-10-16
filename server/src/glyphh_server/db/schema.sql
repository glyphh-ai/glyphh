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

-- plans
CREATE TABLE IF NOT EXISTS plans (
    id UUID DEFAULT gen_random_uuid() NOT NULL,
    name TEXT NOT NULL,
    active BOOLEAN DEFAULT true NOT NULL,
    sort INTEGER DEFAULT 0 NOT NULL,
    PRIMARY KEY (id),
    UNIQUE (name)
);

-- addons
CREATE TABLE IF NOT EXISTS addons (
    id UUID DEFAULT gen_random_uuid() NOT NULL,
    mod TEXT NOT NULL,
    version INTEGER NOT NULL,
    stripe_price_id TEXT,
    price_cents INTEGER NOT NULL,
    per_seat BOOLEAN DEFAULT true NOT NULL,
    plans TEXT[] DEFAULT '{}' NOT NULL,
    free BOOLEAN DEFAULT false NOT NULL,
    limits JSONB DEFAULT '{}' NOT NULL,
    active BOOLEAN DEFAULT true NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT addons_version UNIQUE (mod, version),
    CONSTRAINT addons_price CHECK (price_cents >= 0),
    CONSTRAINT addons_limits CHECK (jsonb_typeof(limits) = 'object'),
    FOREIGN KEY(mod) REFERENCES mods (slug) ON DELETE RESTRICT,
    UNIQUE (stripe_price_id)
);
CREATE INDEX IF NOT EXISTS ix_addons_mod ON addons (mod);

-- plan_versions
CREATE TABLE IF NOT EXISTS plan_versions (
    id UUID DEFAULT gen_random_uuid() NOT NULL,
    plan_id UUID NOT NULL,
    version INTEGER NOT NULL,
    stripe_price_id TEXT,
    seat_price_cents INTEGER NOT NULL,
    max_members INTEGER,
    max_installs INTEGER,
    runtime_hours INTEGER,
    storage_cents_per_gb INTEGER,
    mod_limits JSONB DEFAULT '{}' NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT plan_versions_version UNIQUE (plan_id, version),
    CONSTRAINT plan_versions_price CHECK (seat_price_cents >= 0),
    CONSTRAINT plan_versions_limits CHECK (coalesce(max_members, 1) > 0 AND coalesce(max_installs, 1) > 0),
    CONSTRAINT plan_versions_mod_limits CHECK (jsonb_typeof(mod_limits) = 'object'),
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
    seats INTEGER DEFAULT 1 NOT NULL,
    billing_status TEXT DEFAULT 'none' NOT NULL,
    renews_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT orgs_seats CHECK (seats > 0),
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

-- org_addons
CREATE TABLE IF NOT EXISTS org_addons (
    org_id UUID NOT NULL,
    mod TEXT NOT NULL,
    addon_id UUID NOT NULL,
    stripe_item_id TEXT,
    quantity INTEGER DEFAULT 1 NOT NULL,
    status TEXT DEFAULT 'active' NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (org_id, mod),
    CONSTRAINT org_addons_quantity CHECK (quantity > 0),
    CONSTRAINT org_addons_status CHECK (status IN ('active', 'removed')),
    FOREIGN KEY(org_id) REFERENCES orgs (id) ON DELETE CASCADE,
    FOREIGN KEY(mod) REFERENCES mods (slug) ON DELETE RESTRICT,
    FOREIGN KEY(addon_id) REFERENCES addons (id) ON DELETE RESTRICT,
    UNIQUE (stripe_item_id)
);
CREATE INDEX IF NOT EXISTS ix_org_addons_addon_id ON org_addons (addon_id);

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
    region TEXT,
    image_version TEXT,
    state TEXT NOT NULL,
    token_hash TEXT NOT NULL,
    last_seen_at TIMESTAMP WITH TIME ZONE,
    seq BIGINT DEFAULT 0 NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT rrotors_mode CHECK (mode IN ('hosted', 'local')),
    CONSTRAINT rrotors_local_install CHECK ((mode = 'local') = (install_id IS NOT NULL)),
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE,
    UNIQUE (install_id),
    FOREIGN KEY(install_id) REFERENCES installs (id) ON DELETE CASCADE,
    UNIQUE (token_hash)
);
CREATE INDEX IF NOT EXISTS ix_rrotors_user_id ON rrotors (user_id);
CREATE UNIQUE INDEX IF NOT EXISTS rrotors_one_hosted ON rrotors (user_id) WHERE mode = 'hosted';

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

-- Tenant isolation. A request made with an install's token, or with a connector access token on /mcp, runs as
-- glyphh_tenant with its org in glyphh.org_id (db/tenancy.py), and each policy below shows it only that org's rows.
-- Sign-in, the connector's OAuth endpoints, Stripe's webhook and the few operations that cross orgs on purpose run as
-- the connecting role, which the policies don't bind.
DO $$ BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'glyphh_tenant') THEN CREATE ROLE glyphh_tenant NOLOGIN; END IF;
END $$;
GRANT glyphh_tenant TO CURRENT_USER;
GRANT USAGE ON SCHEMA public TO glyphh_tenant;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO glyphh_tenant;

ALTER TABLE orgs ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant ON orgs;
CREATE POLICY tenant ON orgs USING (id = nullif(current_setting('glyphh.org_id', true), '')::uuid);
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant ON users;
CREATE POLICY tenant ON users USING (org_id = nullif(current_setting('glyphh.org_id', true), '')::uuid);
ALTER TABLE invites ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant ON invites;
CREATE POLICY tenant ON invites USING (org_id = nullif(current_setting('glyphh.org_id', true), '')::uuid);
ALTER TABLE org_addons ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant ON org_addons;
CREATE POLICY tenant ON org_addons USING (org_id = nullif(current_setting('glyphh.org_id', true), '')::uuid);
ALTER TABLE identities ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant ON identities;
CREATE POLICY tenant ON identities USING (user_id IN (SELECT id FROM users));
ALTER TABLE installs ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant ON installs;
CREATE POLICY tenant ON installs USING (user_id IN (SELECT id FROM users));
ALTER TABLE tokens ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant ON tokens;
CREATE POLICY tenant ON tokens USING (install_id IN (SELECT id FROM installs));
ALTER TABLE rrotors ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant ON rrotors;
CREATE POLICY tenant ON rrotors USING (user_id IN (SELECT id FROM users));
ALTER TABLE connector_grants ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant ON connector_grants;
CREATE POLICY tenant ON connector_grants USING (user_id IN (SELECT id FROM users));
ALTER TABLE connector_tokens ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant ON connector_tokens;
CREATE POLICY tenant ON connector_tokens USING (grant_id IN (SELECT id FROM connector_grants));
ALTER TABLE oauth_codes ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant ON oauth_codes;
CREATE POLICY tenant ON oauth_codes USING (user_id IN (SELECT id FROM users));
ALTER TABLE github_installations ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant ON github_installations;
CREATE POLICY tenant ON github_installations USING (user_id IN (SELECT id FROM users));
ALTER TABLE routine_triggers ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant ON routine_triggers;
CREATE POLICY tenant ON routine_triggers USING (user_id IN (SELECT id FROM users));
ALTER TABLE models ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant ON models;
CREATE POLICY tenant ON models USING (org_id = nullif(current_setting('glyphh.org_id', true), '')::uuid);
ALTER TABLE model_versions ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant ON model_versions;
CREATE POLICY tenant ON model_versions USING (model_id IN (SELECT id FROM models));
ALTER TABLE deployments ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant ON deployments;
CREATE POLICY tenant ON deployments USING (model_version_id IN (SELECT id FROM model_versions));
ALTER TABLE runs ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant ON runs;
CREATE POLICY tenant ON runs USING (model_version_id IN (SELECT id FROM model_versions));
ALTER TABLE approvals ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant ON approvals;
CREATE POLICY tenant ON approvals USING (run_id IN (SELECT id FROM runs));
ALTER TABLE model_events ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant ON model_events;
CREATE POLICY tenant ON model_events USING (model_id IN (SELECT id FROM models));
