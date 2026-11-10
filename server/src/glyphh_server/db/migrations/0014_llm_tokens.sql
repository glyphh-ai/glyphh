-- Glyphh-hosted models' tokens (docs/specs/tokens.md): each plan version's monthly token allowance, the org's overage
-- balance entry by entry in microdollars, the balance and the month's allowance used, and each model's day. The seed
-- (db/seed.py) makes the versions that carry the allowance; the policies are schema.sql's, run after this.
ALTER TABLE plan_versions ADD COLUMN IF NOT EXISTS llm_tokens BIGINT;
ALTER TABLE plan_versions ADD CONSTRAINT plan_versions_llm CHECK (coalesce(llm_tokens, 0) >= 0);

CREATE TABLE IF NOT EXISTS llm_ledger (
    id UUID DEFAULT gen_random_uuid() NOT NULL,
    org_id UUID NOT NULL,
    at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    kind TEXT NOT NULL,
    amount_micros BIGINT NOT NULL,
    stripe_ref TEXT,
    model TEXT,
    period TEXT,
    note TEXT,
    PRIMARY KEY (id),
    CONSTRAINT llm_ledger_kind CHECK (kind IN ('topup', 'charge', 'grant', 'refund')),
    FOREIGN KEY(org_id) REFERENCES orgs (id) ON DELETE CASCADE,
    UNIQUE (stripe_ref)
);
CREATE INDEX IF NOT EXISTS llm_ledger_newest ON llm_ledger (org_id, at);
CREATE UNIQUE INDEX IF NOT EXISTS llm_ledger_charge_day ON llm_ledger (org_id, model, period) WHERE kind = 'charge';

CREATE TABLE IF NOT EXISTS llm_balances (
    org_id UUID NOT NULL,
    micros BIGINT DEFAULT 0 NOT NULL,
    period TEXT DEFAULT '' NOT NULL,
    tokens BIGINT DEFAULT 0 NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (org_id),
    FOREIGN KEY(org_id) REFERENCES orgs (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS llm_usage_days (
    org_id UUID NOT NULL,
    model TEXT NOT NULL,
    day DATE NOT NULL,
    input_tokens BIGINT DEFAULT 0 NOT NULL,
    output_tokens BIGINT DEFAULT 0 NOT NULL,
    requests BIGINT DEFAULT 0 NOT NULL,
    charged_micros BIGINT DEFAULT 0 NOT NULL,
    PRIMARY KEY (org_id, model, day),
    FOREIGN KEY(org_id) REFERENCES orgs (id) ON DELETE CASCADE
);
