-- Two settings a bot's owner chooses (docs/specs/bots.md, 13): the folders of its rrotor's machine it may read or
-- change ([{path, access}], none unless chosen; the rrotor gives its run exactly these), and how hard Claude works on
-- its agent steps (the Claude API's output_config.effort; medium unless chosen).
ALTER TABLE bots ADD COLUMN IF NOT EXISTS folders JSONB DEFAULT '[]'::jsonb NOT NULL;
ALTER TABLE bots ADD COLUMN IF NOT EXISTS effort TEXT DEFAULT 'medium' NOT NULL;
ALTER TABLE bots DROP CONSTRAINT IF EXISTS bots_effort;
ALTER TABLE bots ADD CONSTRAINT bots_effort CHECK (effort IN ('low', 'medium', 'high', 'xhigh', 'max'));
