-- Connections' pricing (docs/pricing.md): each plan version's connections included and the price of each one past
-- them, a month. Both null until Chris sets them: every connection included, none charged. The seed (db/seed.py)
-- makes the versions that carry them.
ALTER TABLE plan_versions ADD COLUMN IF NOT EXISTS connections INTEGER;
ALTER TABLE plan_versions ADD COLUMN IF NOT EXISTS connection_cents INTEGER;
ALTER TABLE plan_versions ADD CONSTRAINT plan_versions_connections
    CHECK (coalesce(connections, 0) >= 0 AND coalesce(connection_cents, 0) >= 0);
