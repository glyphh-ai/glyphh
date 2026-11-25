-- A run on a rrotor calls its tools on the server (docs/specs/bots.md, 9): a tool that asks the person is run only
-- with the person's yes to the step that runs it, kept here when they answer, by tool, and used once. A bot adds
-- tools to the org's connector by purpose (its template's connector_tools, or its own).
ALTER TABLE bot_runs ADD COLUMN IF NOT EXISTS approvals JSONB DEFAULT '{}'::jsonb NOT NULL;
ALTER TABLE bots ADD COLUMN IF NOT EXISTS connector_tools JSONB DEFAULT '[]'::jsonb NOT NULL;
