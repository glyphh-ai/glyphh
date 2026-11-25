-- Glyphh is one thing, Ada: the data of everything else goes. The code for bots, programs, projects, connections,
-- templates, apps, rrotor (self-hosted runtimes, their nodes and licences), the GitHub App and mods was removed in
-- the release before this one, so nothing reads or writes these tables and columns any more. What stays is what Ada
-- Cloud, sign-in, billing and the staff view use.
--
-- Nothing here can be undone: scripts/one-thing-backup.py comes first, and writes every table, column and row this
-- migration drops, deletes or revokes to files. Every statement is safe to run again.

-- The keys of self-hosted runtimes: no runtime is left to hold one.
DELETE FROM runtime_keys WHERE scope = 'runtime';
-- Each bot's own Ada Cloud key (named "bot <slug>", clearance 0): no bot is left to use it. Revoked, not deleted,
-- so it stays named and dated in its maker's list.
UPDATE runtime_keys SET revoked_at = now()
    WHERE scope = 'cloud' AND name LIKE 'bot %' AND clearance = 0 AND revoked_at IS NULL;

-- The tables, each before the ones it points at. Their indexes, policies and sequences go with them.
DROP TABLE IF EXISTS run_marks;
DROP TABLE IF EXISTS project_turns;
DROP TABLE IF EXISTS project_runs;
DROP TABLE IF EXISTS projects;
DROP TABLE IF EXISTS program_events;
DROP TABLE IF EXISTS program_runs;
DROP TABLE IF EXISTS programs;
DROP TABLE IF EXISTS bot_decisions;
DROP TABLE IF EXISTS bot_sessions;
DROP TABLE IF EXISTS bot_plugins;
DROP TABLE IF EXISTS bot_runs;
DROP TABLE IF EXISTS bot_keys;
DROP TABLE IF EXISTS bots;
DROP TABLE IF EXISTS connections;
DROP TABLE IF EXISTS template_installs;
DROP TABLE IF EXISTS templates;
DROP TABLE IF EXISTS apps;
DROP TABLE IF EXISTS nodes;
DROP TABLE IF EXISTS licenses;
DROP TABLE IF EXISTS github_installations;
DROP TABLE IF EXISTS mods;

-- runtime_keys is Ada Cloud's API keys and nothing else: the runtime a key was for (its foreign key to rrotors goes
-- with the column) and what that runtime reported of its use go, and `cloud` is the only scope.
DROP INDEX IF EXISTS ix_runtime_keys_rrotor_id;
ALTER TABLE runtime_keys DROP COLUMN IF EXISTS rrotor_id;
ALTER TABLE runtime_keys DROP COLUMN IF EXISTS calls;
ALTER TABLE runtime_keys DROP COLUMN IF EXISTS last_used_at;
ALTER TABLE runtime_keys DROP CONSTRAINT IF EXISTS runtime_keys_scope;
ALTER TABLE runtime_keys ADD CONSTRAINT runtime_keys_scope CHECK (scope = 'cloud');
ALTER TABLE runtime_keys ALTER COLUMN scope SET DEFAULT 'cloud';

-- rrotors last: everything that pointed at it is gone.
DROP TABLE IF EXISTS rrotors;

-- org_sso: the groups whose members reviewed the org's apps.
ALTER TABLE org_sso DROP COLUMN IF EXISTS reviewers;

-- plan_versions: rrotor's limits and features (runtime nodes, precedents a node, sync, ha, offline) and the
-- connections a plan included and their price.
ALTER TABLE plan_versions DROP CONSTRAINT IF EXISTS plan_versions_limits;
ALTER TABLE plan_versions DROP CONSTRAINT IF EXISTS plan_versions_connections;
ALTER TABLE plan_versions DROP COLUMN IF EXISTS max_machines;
ALTER TABLE plan_versions DROP COLUMN IF EXISTS precedents;
ALTER TABLE plan_versions DROP COLUMN IF EXISTS sync;
ALTER TABLE plan_versions DROP COLUMN IF EXISTS ha;
ALTER TABLE plan_versions DROP COLUMN IF EXISTS offline;
ALTER TABLE plan_versions DROP COLUMN IF EXISTS connections;
ALTER TABLE plan_versions DROP COLUMN IF EXISTS connection_cents;
