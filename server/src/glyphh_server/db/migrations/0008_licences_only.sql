-- The server grants licences and keeps nothing of a program: no hosted runtime, no hosting meter or rates, no record
-- of programs, their versions, deployments, runs, approvals, events or routine triggers, and no runtime's logs. Hosted
-- runtimes go (their keys and nodes with them), and so do the runtime keys that named no runtime (every hosted one).
DELETE FROM rrotors WHERE mode = 'hosted';
DELETE FROM runtime_keys WHERE scope = 'runtime' AND rrotor_id IS NULL;

DROP TABLE IF EXISTS approvals;
DROP TABLE IF EXISTS runs;
DROP TABLE IF EXISTS deployments;
DROP TABLE IF EXISTS model_events;
DROP TABLE IF EXISTS routine_triggers;
DROP TABLE IF EXISTS model_versions;
DROP TABLE IF EXISTS models;
DROP TABLE IF EXISTS telemetry_logs;
DROP TABLE IF EXISTS telemetry_metrics;
DROP TABLE IF EXISTS telemetry_spans;
DROP TABLE IF EXISTS machine_months;
DROP TABLE IF EXISTS meter_events;
DROP TABLE IF EXISTS fly_rates;

ALTER TABLE rrotors DROP CONSTRAINT IF EXISTS rrotors_hosted_machine;
ALTER TABLE rrotors DROP CONSTRAINT IF EXISTS rrotors_size;
ALTER TABLE rrotors DROP CONSTRAINT IF EXISTS rrotors_mode;
ALTER TABLE rrotors ADD CONSTRAINT rrotors_mode CHECK (mode IN ('local', 'self'));
DROP INDEX IF EXISTS rrotors_hosted_name;
ALTER TABLE rrotors DROP COLUMN IF EXISTS fly_machine_id;
ALTER TABLE rrotors DROP COLUMN IF EXISTS fly_volume_id;
ALTER TABLE rrotors DROP COLUMN IF EXISTS month;
ALTER TABLE rrotors DROP COLUMN IF EXISTS month_seconds;
ALTER TABLE rrotors DROP COLUMN IF EXISTS metered_at;
ALTER TABLE rrotors DROP COLUMN IF EXISTS region;
ALTER TABLE rrotors DROP COLUMN IF EXISTS size;

ALTER TABLE plan_versions DROP CONSTRAINT IF EXISTS plan_versions_markup;
ALTER TABLE plan_versions DROP COLUMN IF EXISTS hosting_markup_pct;
ALTER TABLE orgs DROP CONSTRAINT IF EXISTS orgs_markup;
ALTER TABLE orgs DROP COLUMN IF EXISTS markup_pct;
