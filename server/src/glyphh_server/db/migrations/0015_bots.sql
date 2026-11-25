-- Hosted bots (docs/specs/bots.md): an org's connections to other services (Pipedream accounts), its bots and their
-- runs. The policies are schema.sql's, run after this.
CREATE TABLE IF NOT EXISTS connections (
    id UUID DEFAULT gen_random_uuid() NOT NULL,
    org_id UUID NOT NULL,
    app TEXT NOT NULL,
    app_name TEXT NOT NULL,
    app_icon TEXT DEFAULT '' NOT NULL,
    account_id TEXT NOT NULL,
    label TEXT DEFAULT '' NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(org_id) REFERENCES orgs (id) ON DELETE CASCADE
);
CREATE UNIQUE INDEX IF NOT EXISTS connections_one_account ON connections (org_id, account_id);

CREATE TABLE IF NOT EXISTS bots (
    id UUID DEFAULT gen_random_uuid() NOT NULL,
    org_id UUID NOT NULL,
    created_by UUID,
    slug TEXT NOT NULL,
    name TEXT NOT NULL,
    summary TEXT DEFAULT '' NOT NULL,
    look JSONB DEFAULT '{}'::jsonb NOT NULL,
    instructions TEXT DEFAULT '' NOT NULL,
    model TEXT NOT NULL,
    models JSONB DEFAULT '[]'::jsonb NOT NULL,
    scopes JSONB DEFAULT '[]'::jsonb NOT NULL,
    max_turns INTEGER DEFAULT 20 NOT NULL,
    usd_per_run_micros BIGINT DEFAULT 2000000 NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(org_id) REFERENCES orgs (id) ON DELETE CASCADE,
    FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS bots_one_slug ON bots (org_id, slug);

CREATE TABLE IF NOT EXISTS bot_runs (
    id UUID DEFAULT gen_random_uuid() NOT NULL,
    org_id UUID NOT NULL,
    bot_id UUID NOT NULL,
    user_id UUID,
    status TEXT DEFAULT 'queued' NOT NULL,
    input TEXT DEFAULT '' NOT NULL,
    output TEXT DEFAULT '' NOT NULL,
    error TEXT DEFAULT '' NOT NULL,
    steps JSONB DEFAULT '[]'::jsonb NOT NULL,
    input_tokens BIGINT DEFAULT 0 NOT NULL,
    output_tokens BIGINT DEFAULT 0 NOT NULL,
    cost_micros BIGINT DEFAULT 0 NOT NULL,
    machine TEXT DEFAULT '' NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    started_at TIMESTAMP WITH TIME ZONE,
    finished_at TIMESTAMP WITH TIME ZONE,
    PRIMARY KEY (id),
    CONSTRAINT bot_runs_status CHECK (status IN ('queued', 'running', 'done', 'failed')),
    FOREIGN KEY(org_id) REFERENCES orgs (id) ON DELETE CASCADE,
    FOREIGN KEY(bot_id) REFERENCES bots (id) ON DELETE CASCADE,
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS bot_runs_newest ON bot_runs (bot_id, created_at);
