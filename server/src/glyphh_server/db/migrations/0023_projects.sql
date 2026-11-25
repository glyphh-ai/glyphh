-- Swarms are projects (docs/specs/bots.md, 10): swarms, swarm_runs and swarm_turns renamed, with their keys,
-- constraints and indexes, their rows kept. A project's crew has no order and no rounds: each turn is taken by the bot
-- that has waited longest and has something to do (wait) or picked by an orchestrator (a bot of the crew, or Claude)
-- reading the repo and the instructions, until the work is done or a safety cap is reached. It runs on Glyphh cloud
-- (runs_on none) or a rrotor; review auto (merged as it opens) is now end (one pull request of the run at its end).
-- A database made before the swarms had tables has none of them here: schema.sql makes the projects' tables, every
-- statement below skips.
ALTER TABLE IF EXISTS swarms RENAME TO projects;
ALTER TABLE IF EXISTS projects RENAME CONSTRAINT swarms_pkey TO projects_pkey;
ALTER TABLE IF EXISTS projects RENAME CONSTRAINT swarms_org_id_fkey TO projects_org_id_fkey;
ALTER TABLE IF EXISTS projects RENAME CONSTRAINT swarms_created_by_fkey TO projects_created_by_fkey;
ALTER INDEX IF EXISTS swarms_one_slug RENAME TO projects_one_slug;
ALTER TABLE IF EXISTS projects DROP CONSTRAINT IF EXISTS swarms_runs_on_fkey;
ALTER TABLE IF EXISTS projects ALTER COLUMN runs_on DROP NOT NULL;
ALTER TABLE IF EXISTS projects ADD CONSTRAINT projects_runs_on_fkey
    FOREIGN KEY (runs_on) REFERENCES rrotors (id) ON DELETE SET NULL;
ALTER TABLE IF EXISTS projects DROP CONSTRAINT IF EXISTS swarms_review;
ALTER TABLE IF EXISTS projects DROP COLUMN IF EXISTS rounds;
ALTER TABLE IF EXISTS projects ADD COLUMN IF NOT EXISTS instructions TEXT DEFAULT '' NOT NULL;
ALTER TABLE IF EXISTS projects ADD COLUMN IF NOT EXISTS instructions_path TEXT DEFAULT 'PROJECT.md' NOT NULL;
ALTER TABLE IF EXISTS projects ADD COLUMN IF NOT EXISTS turn_mode TEXT DEFAULT 'wait' NOT NULL;
ALTER TABLE IF EXISTS projects ADD COLUMN IF NOT EXISTS orchestrator UUID;
ALTER TABLE IF EXISTS projects ADD CONSTRAINT projects_orchestrator_fkey
    FOREIGN KEY (orchestrator) REFERENCES bots (id) ON DELETE SET NULL;
ALTER TABLE IF EXISTS projects ADD COLUMN IF NOT EXISTS max_turns INTEGER DEFAULT 30 NOT NULL;
ALTER TABLE IF EXISTS projects ADD COLUMN IF NOT EXISTS max_spend_cents INTEGER;
ALTER TABLE IF EXISTS projects ADD COLUMN IF NOT EXISTS narrate BOOLEAN DEFAULT false NOT NULL;
ALTER TABLE IF EXISTS projects ADD CONSTRAINT projects_turn_mode CHECK (turn_mode IN ('wait', 'orchestrator'));
-- GitHub is reached through the Glyphh GitHub App: a project keeps the installation that covers its repo, and the
-- org's pasted GitHub token is gone, with every token it held (a project made before connects again, with one click,
-- when a person next runs it).
ALTER TABLE IF EXISTS projects ADD COLUMN IF NOT EXISTS github_installation_id BIGINT;
DROP TABLE IF EXISTS github_keys;

ALTER TABLE IF EXISTS swarm_runs RENAME TO project_runs;
ALTER TABLE IF EXISTS project_runs RENAME COLUMN swarm_id TO project_id;
ALTER TABLE IF EXISTS project_runs RENAME CONSTRAINT swarm_runs_pkey TO project_runs_pkey;
ALTER TABLE IF EXISTS project_runs RENAME CONSTRAINT swarm_runs_org_id_fkey TO project_runs_org_id_fkey;
ALTER TABLE IF EXISTS project_runs RENAME CONSTRAINT swarm_runs_swarm_id_fkey TO project_runs_project_id_fkey;
ALTER TABLE IF EXISTS project_runs RENAME CONSTRAINT swarm_runs_user_id_fkey TO project_runs_user_id_fkey;
ALTER TABLE IF EXISTS project_runs RENAME CONSTRAINT swarm_runs_rrotor_id_fkey TO project_runs_rrotor_id_fkey;
ALTER TABLE IF EXISTS project_runs RENAME CONSTRAINT swarm_runs_status TO project_runs_status;
ALTER INDEX IF EXISTS swarm_runs_newest RENAME TO project_runs_newest;
ALTER INDEX IF EXISTS swarm_runs_one_live RENAME TO project_runs_one_live;
ALTER TABLE IF EXISTS project_runs DROP COLUMN IF EXISTS rounds;
ALTER TABLE IF EXISTS project_runs ADD COLUMN IF NOT EXISTS turn_mode TEXT DEFAULT 'wait' NOT NULL;
ALTER TABLE IF EXISTS project_runs ADD COLUMN IF NOT EXISTS max_turns INTEGER DEFAULT 30 NOT NULL;
ALTER TABLE IF EXISTS project_runs ADD COLUMN IF NOT EXISTS max_spend_cents INTEGER;
ALTER TABLE IF EXISTS project_runs ADD COLUMN IF NOT EXISTS ended TEXT DEFAULT '' NOT NULL;
ALTER TABLE IF EXISTS project_runs ADD COLUMN IF NOT EXISTS work_branch TEXT;
ALTER TABLE IF EXISTS project_runs ADD COLUMN IF NOT EXISTS pr_url TEXT;
ALTER TABLE IF EXISTS project_runs ADD COLUMN IF NOT EXISTS number INTEGER;
ALTER TABLE IF EXISTS project_runs ADD COLUMN IF NOT EXISTS on_cloud BOOLEAN DEFAULT false NOT NULL;
ALTER TABLE IF EXISTS project_runs ADD COLUMN IF NOT EXISTS machine TEXT;
ALTER TABLE IF EXISTS project_runs ADD COLUMN IF NOT EXISTS model TEXT;
ALTER TABLE IF EXISTS project_runs ADD COLUMN IF NOT EXISTS effort TEXT;

DO $$
BEGIN
    IF to_regclass('public.projects') IS NOT NULL THEN
        UPDATE projects SET review = 'end' WHERE review = 'auto';
        UPDATE project_runs SET review = 'end' WHERE review = 'auto';
    END IF;
END $$;
ALTER TABLE IF EXISTS projects ADD CONSTRAINT projects_review CHECK (review IN ('each_turn', 'end'));

ALTER TABLE IF EXISTS swarm_turns RENAME TO project_turns;
ALTER TABLE IF EXISTS project_turns RENAME CONSTRAINT swarm_turns_pkey TO project_turns_pkey;
ALTER TABLE IF EXISTS project_turns RENAME CONSTRAINT swarm_turns_org_id_fkey TO project_turns_org_id_fkey;
ALTER TABLE IF EXISTS project_turns RENAME CONSTRAINT swarm_turns_run_id_fkey TO project_turns_run_id_fkey;
ALTER TABLE IF EXISTS project_turns RENAME CONSTRAINT swarm_turns_bot_id_fkey TO project_turns_bot_id_fkey;
ALTER TABLE IF EXISTS project_turns DROP CONSTRAINT IF EXISTS swarm_turns_status;
ALTER TABLE IF EXISTS project_turns ADD CONSTRAINT project_turns_status CHECK (status IN ('picking', 'running', 'open',
    'unchanged', 'merging', 'merged', 'conflict', 'rejecting', 'rejected', 'failed', 'cancelled'));
ALTER INDEX IF EXISTS swarm_turns_of_run RENAME TO project_turns_of_run;
ALTER INDEX IF EXISTS swarm_turns_call RENAME TO project_turns_call;
ALTER TABLE IF EXISTS project_turns DROP COLUMN IF EXISTS round;
ALTER TABLE IF EXISTS project_turns ADD COLUMN IF NOT EXISTS picked_by TEXT DEFAULT 'wait' NOT NULL;
ALTER TABLE IF EXISTS project_turns ADD COLUMN IF NOT EXISTS why TEXT DEFAULT '' NOT NULL;
ALTER TABLE IF EXISTS project_turns ADD COLUMN IF NOT EXISTS input_tokens BIGINT DEFAULT 0 NOT NULL;
ALTER TABLE IF EXISTS project_turns ADD COLUMN IF NOT EXISTS output_tokens BIGINT DEFAULT 0 NOT NULL;
ALTER TABLE IF EXISTS project_turns ADD COLUMN IF NOT EXISTS cost_micros BIGINT DEFAULT 0 NOT NULL;
