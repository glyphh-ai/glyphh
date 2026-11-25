-- A bot's schedule and where it runs (docs/specs/bots.md, 9). The schedule is kept as the person chose it, in plain
-- words ({every, at, weekday, day, timezone, input}; empty: off), never as cron; next_run_at is its next run, worked
-- out by the server (ops/bots/schedule.py) and fired by the minute tick (ops/bots/due.py). runs_on is the org's rrotor
-- the bot runs on; empty, Glyphh cloud (what every bot did before); a rrotor deleted, the bot is back on the cloud.
ALTER TABLE bots ADD COLUMN IF NOT EXISTS schedule JSONB DEFAULT '{}'::jsonb NOT NULL;
ALTER TABLE bots ADD COLUMN IF NOT EXISTS next_run_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE bots ADD COLUMN IF NOT EXISTS runs_on UUID;
ALTER TABLE bots ADD CONSTRAINT bots_runs_on_fkey FOREIGN KEY (runs_on) REFERENCES rrotors (id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS bots_due ON bots (next_run_at) WHERE next_run_at IS NOT NULL;
