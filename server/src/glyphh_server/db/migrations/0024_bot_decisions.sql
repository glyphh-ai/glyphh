-- A bot's gates' decisions, readable and trainable (docs/specs/bots.md, 12): each gate's decision on each item of each
-- run, copied from the runner's runs.sqlite after each go; schema.sql adds its row-level security after.
CREATE TABLE IF NOT EXISTS bot_decisions (
    id UUID DEFAULT gen_random_uuid() NOT NULL,
    org_id UUID NOT NULL,
    bot_id UUID NOT NULL,
    loop_run TEXT DEFAULT '' NOT NULL,
    gate TEXT NOT NULL,
    step TEXT DEFAULT '' NOT NULL,
    n INTEGER DEFAULT 0 NOT NULL,
    key TEXT DEFAULT '' NOT NULL,
    kind TEXT DEFAULT 'gate' NOT NULL,
    label TEXT DEFAULT '' NOT NULL,
    fields JSONB DEFAULT '{}'::jsonb NOT NULL,
    "case" JSONB DEFAULT '{}'::jsonb NOT NULL,
    outcome TEXT,
    who TEXT DEFAULT 'ada' NOT NULL,
    mode TEXT DEFAULT '' NOT NULL,
    p DOUBLE PRECISION,
    guess TEXT,
    recorded BOOLEAN DEFAULT false NOT NULL,
    corrected TEXT,
    confirmed BOOLEAN DEFAULT false NOT NULL,
    precedent TEXT DEFAULT '' NOT NULL,
    body TEXT DEFAULT '' NOT NULL,
    search TSVECTOR GENERATED ALWAYS AS (to_tsvector('simple'::regconfig, body)) STORED,
    at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT bot_decisions_who CHECK (who IN ('ada', 'you', 'default')),
    FOREIGN KEY(org_id) REFERENCES orgs (id) ON DELETE CASCADE,
    FOREIGN KEY(bot_id) REFERENCES bots (id) ON DELETE CASCADE
);
CREATE UNIQUE INDEX IF NOT EXISTS bot_decisions_one ON bot_decisions (bot_id, loop_run, gate, step, n, key);
CREATE INDEX IF NOT EXISTS bot_decisions_newest ON bot_decisions (bot_id, at);
CREATE INDEX IF NOT EXISTS bot_decisions_search ON bot_decisions USING gin (search);

-- The marketplace's bots read their tools' answers where they are: GitHub's Search Issues and Pull Requests, Google
-- Calendar's List Events and Gmail's Find Email each answer a list (`ret`), not {items} or {messages}, so a bot
-- installed from them gated no item at all. Installed copies are brought to the templates' paths.
UPDATE bots SET spec = replace(replace(replace(replace(replace(spec::text,
    '"$prs.ret.items"', '"$prs.ret"'),
    'merged pull requests: $merged.ret.items"', 'merged pull requests: $merged.ret"'),
    '"$events.ret.items"', '"$events.ret"'),
    '"$mail.ret.messages"', '"$mail.ret"'),
    '"$tickets.ret.messages"', '"$tickets.ret"')::jsonb
WHERE spec::text LIKE '%.ret.items"%' OR spec::text LIKE '%.ret.messages"%';
