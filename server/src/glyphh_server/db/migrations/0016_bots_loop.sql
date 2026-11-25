-- Bots run the SDK's loop (docs/specs/bots.md): a bot is a bot package (its loop, gates and limits in spec, its
-- skills), keeps the runner's state and an Ada key of its own; a run can stop for the person's answer
-- (needs_input) or be skipped by a hard limit, keeps its log, data and question; an org may set its own Anthropic
-- API key. The bots made before this were the free-running agent's: they are removed, with their runs.
DELETE FROM bots;

ALTER TABLE bots DROP COLUMN IF EXISTS models;
ALTER TABLE bots DROP COLUMN IF EXISTS max_turns;
ALTER TABLE bots DROP COLUMN IF EXISTS usd_per_run_micros;
ALTER TABLE bots ADD COLUMN IF NOT EXISTS spec JSONB DEFAULT '{}'::jsonb NOT NULL;
ALTER TABLE bots ADD COLUMN IF NOT EXISTS skills JSONB DEFAULT '{}'::jsonb NOT NULL;
ALTER TABLE bots ADD COLUMN IF NOT EXISTS state BYTEA;
ALTER TABLE bots ADD COLUMN IF NOT EXISTS ada_key TEXT DEFAULT '' NOT NULL;

ALTER TABLE bot_runs DROP COLUMN IF EXISTS steps;
ALTER TABLE bot_runs ADD COLUMN IF NOT EXISTS log JSONB DEFAULT '[]'::jsonb NOT NULL;
ALTER TABLE bot_runs ADD COLUMN IF NOT EXISTS data JSONB DEFAULT '{}'::jsonb NOT NULL;
ALTER TABLE bot_runs ADD COLUMN IF NOT EXISTS question JSONB DEFAULT '{}'::jsonb NOT NULL;
ALTER TABLE bot_runs ADD COLUMN IF NOT EXISTS loop_run TEXT DEFAULT '' NOT NULL;
ALTER TABLE bot_runs ADD COLUMN IF NOT EXISTS own_key BOOLEAN DEFAULT false NOT NULL;
ALTER TABLE bot_runs DROP CONSTRAINT IF EXISTS bot_runs_status;
ALTER TABLE bot_runs ADD CONSTRAINT bot_runs_status
    CHECK (status IN ('queued', 'running', 'needs_input', 'done', 'failed', 'skipped'));
CREATE UNIQUE INDEX IF NOT EXISTS bot_runs_one_live ON bot_runs (bot_id) WHERE status IN ('queued', 'running', 'needs_input');

CREATE TABLE IF NOT EXISTS bot_keys (
    org_id UUID NOT NULL,
    anthropic_key TEXT NOT NULL,
    hint TEXT NOT NULL,
    set_by UUID,
    set_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (org_id),
    FOREIGN KEY(org_id) REFERENCES orgs (id) ON DELETE CASCADE,
    FOREIGN KEY(set_by) REFERENCES users (id) ON DELETE SET NULL
);
