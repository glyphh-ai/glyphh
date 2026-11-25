-- A bot's own mascot, permission mode and voice (docs/specs/bots.md, 9). The mascot is black-and-white SVG drawn from
-- the person's words, made safe before it is kept (ops/bots/svg.py) and shown in place of its cat; empty, the bot is
-- its cat (look). The permission mode says which tool steps wait for the person: ask (unless the connection allows
-- the tool; what bots did before), connection (only those the connection says to ask about) or auto (none; a denied
-- tool still fails). The voice is one of the open TTS voices (ops/bots/voices.py) it speaks in; empty, none chosen.
ALTER TABLE bots ADD COLUMN IF NOT EXISTS mascot TEXT DEFAULT '' NOT NULL;
ALTER TABLE bots ADD COLUMN IF NOT EXISTS permission_mode TEXT DEFAULT 'ask' NOT NULL;
ALTER TABLE bots ADD COLUMN IF NOT EXISTS voice TEXT DEFAULT '' NOT NULL;
ALTER TABLE bots ADD CONSTRAINT bots_permission_mode CHECK (permission_mode IN ('ask', 'connection', 'auto'));
