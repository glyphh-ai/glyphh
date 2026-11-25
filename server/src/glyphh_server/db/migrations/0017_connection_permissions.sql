-- Per connection, what its bots may do with each tool (docs/specs/bots.md, 9): allow, ask (the step waits for the
-- person's yes) or deny; a tool not named asks.
ALTER TABLE connections ADD COLUMN IF NOT EXISTS permissions JSONB DEFAULT '{}'::jsonb NOT NULL;
