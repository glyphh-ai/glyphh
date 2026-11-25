-- Glyphh's own sites' traffic from Cloudflare's analytics, for the staff view (ops/traffic.py): each zone and what its
-- plan let the last pull have, each day's numbers by zone and host, each day's countries, pages and referrers. Pulled
-- by the tick each hour; staff only (the policies below).
CREATE TABLE IF NOT EXISTS traffic_zones (
    name TEXT NOT NULL,
    zone_id TEXT NOT NULL,
    plan TEXT,
    pulled_at TIMESTAMP WITH TIME ZONE NOT NULL,
    available JSONB DEFAULT '{}'::jsonb NOT NULL,
    PRIMARY KEY (name)
);

CREATE TABLE IF NOT EXISTS traffic_days (
    zone TEXT NOT NULL,
    host TEXT NOT NULL,
    day DATE NOT NULL,
    metric TEXT NOT NULL,
    n BIGINT DEFAULT 0 NOT NULL,
    PRIMARY KEY (zone, host, day, metric)
);

CREATE TABLE IF NOT EXISTS traffic_tops (
    zone TEXT NOT NULL,
    host TEXT NOT NULL,
    day DATE NOT NULL,
    kind TEXT NOT NULL,
    key TEXT NOT NULL,
    n BIGINT DEFAULT 0 NOT NULL,
    PRIMARY KEY (zone, host, day, kind, key)
);

ALTER TABLE traffic_zones ENABLE ROW LEVEL SECURITY;
ALTER TABLE traffic_zones FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS staff ON traffic_zones;
CREATE POLICY staff ON traffic_zones USING (nullif(current_setting('glyphh.org_id', true), '') IS NULL);
ALTER TABLE traffic_days ENABLE ROW LEVEL SECURITY;
ALTER TABLE traffic_days FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS staff ON traffic_days;
CREATE POLICY staff ON traffic_days USING (nullif(current_setting('glyphh.org_id', true), '') IS NULL);
ALTER TABLE traffic_tops ENABLE ROW LEVEL SECURITY;
ALTER TABLE traffic_tops FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS staff ON traffic_tops;
CREATE POLICY staff ON traffic_tops USING (nullif(current_setting('glyphh.org_id', true), '') IS NULL);
