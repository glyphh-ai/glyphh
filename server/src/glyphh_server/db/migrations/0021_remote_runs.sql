-- A bot runs on the org's rrotor it is set to (docs/specs/bots.md, 9): its run is dispatched there over the link and
-- its results come back; the run keeps which rrotor, the last result's seq it took, and what the current call began
-- with. The swarms' tables (swarms, swarm_runs, swarm_turns, github_keys) are new: schema.sql makes them.
ALTER TABLE bot_runs ADD COLUMN IF NOT EXISTS rrotor_id UUID;
ALTER TABLE bot_runs ADD COLUMN IF NOT EXISTS remote_seq BIGINT DEFAULT 0 NOT NULL;
ALTER TABLE bot_runs ADD COLUMN IF NOT EXISTS remote JSONB DEFAULT '{}'::jsonb NOT NULL;
ALTER TABLE bot_runs ADD CONSTRAINT bot_runs_rrotor_id_fkey FOREIGN KEY (rrotor_id) REFERENCES rrotors (id) ON DELETE SET NULL;
ALTER TABLE bot_runs DROP CONSTRAINT IF EXISTS bot_runs_status;
ALTER TABLE bot_runs ADD CONSTRAINT bot_runs_status
    CHECK (status IN ('queued', 'running', 'dispatched', 'needs_input', 'done', 'failed', 'skipped'));
DROP INDEX IF EXISTS bot_runs_one_live;
CREATE UNIQUE INDEX bot_runs_one_live ON bot_runs (bot_id) WHERE status IN ('queued', 'running', 'dispatched', 'needs_input');
