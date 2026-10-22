-- Ada Cloud's plans and metering (docs/specs/ada-cloud.md, section 7): each plan version's cloud limits (precedents,
-- requests a month, calls a second, whether requests past the month are metered), an org's reads by month, and the
-- reads past a metered plan's month reported to Stripe. The seed (db/seed.py) makes the versions that carry them.
ALTER TABLE plan_versions ADD COLUMN IF NOT EXISTS cloud_precedents INTEGER;
ALTER TABLE plan_versions ADD COLUMN IF NOT EXISTS cloud_requests INTEGER;
ALTER TABLE plan_versions ADD COLUMN IF NOT EXISTS cloud_rps INTEGER;
ALTER TABLE plan_versions ADD COLUMN IF NOT EXISTS cloud_overage BOOLEAN DEFAULT false NOT NULL;
ALTER TABLE plan_versions ADD CONSTRAINT plan_versions_cloud
    CHECK (coalesce(cloud_precedents, 0) >= 0 AND coalesce(cloud_requests, 0) >= 0 AND coalesce(cloud_rps, 1) > 0);

CREATE TABLE IF NOT EXISTS ada_usage (
    org_id UUID NOT NULL,
    period TEXT NOT NULL,
    requests BIGINT DEFAULT 0 NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (org_id, period),
    CONSTRAINT ada_usage_requests CHECK (requests >= 0),
    FOREIGN KEY(org_id) REFERENCES orgs (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS ada_meter_events (
    id UUID DEFAULT gen_random_uuid() NOT NULL,
    org_id UUID NOT NULL,
    customer TEXT NOT NULL,
    period TEXT NOT NULL,
    requests INTEGER NOT NULL,
    at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    sent_at TIMESTAMP WITH TIME ZONE,
    PRIMARY KEY (id),
    CONSTRAINT ada_meter_events_requests CHECK (requests > 0),
    FOREIGN KEY(org_id) REFERENCES orgs (id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_ada_meter_events_org_id ON ada_meter_events (org_id);
