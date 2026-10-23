-- Glyphh's staff view (glyphh_server/admin): an org can be suspended by staff, keeps where its sign-up came from (the
-- website's glyphh_src cookie: utm_* and the ad click ids, ops/attribution.py) and when it first paid; a person keeps
-- where they came from too. Every staff request is written to admin_audit; the server's own errors and warnings to
-- ops_events (obs/events.py). Neither table is ever seen by a session acting for an org.
ALTER TABLE orgs ADD COLUMN IF NOT EXISTS suspended_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE orgs ADD COLUMN IF NOT EXISTS suspended_reason TEXT;
ALTER TABLE orgs ADD COLUMN IF NOT EXISTS source JSONB;
ALTER TABLE orgs ADD COLUMN IF NOT EXISTS first_paid_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS source JSONB;

CREATE TABLE IF NOT EXISTS admin_audit (
    id UUID DEFAULT gen_random_uuid() NOT NULL,
    at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    staff_user_id UUID NOT NULL,
    staff_email TEXT NOT NULL,
    action TEXT NOT NULL,
    org_id UUID,
    target TEXT,
    detail JSONB DEFAULT '{}'::jsonb NOT NULL,
    outcome TEXT DEFAULT 'ok' NOT NULL,
    PRIMARY KEY (id)
);
CREATE INDEX IF NOT EXISTS admin_audit_at ON admin_audit (at);
CREATE INDEX IF NOT EXISTS admin_audit_org ON admin_audit (org_id, at);

CREATE TABLE IF NOT EXISTS ops_events (
    id UUID DEFAULT gen_random_uuid() NOT NULL,
    first_at TIMESTAMP WITH TIME ZONE NOT NULL,
    last_at TIMESTAMP WITH TIME ZONE NOT NULL,
    severity TEXT NOT NULL,
    kind TEXT NOT NULL,
    source TEXT NOT NULL,
    message TEXT NOT NULL,
    detail JSONB DEFAULT '{}'::jsonb NOT NULL,
    org_id UUID,
    trace_id TEXT,
    count INTEGER DEFAULT 1 NOT NULL,
    acknowledged_at TIMESTAMP WITH TIME ZONE,
    acknowledged_by TEXT,
    PRIMARY KEY (id),
    CONSTRAINT ops_events_severity CHECK (severity IN ('warning', 'error', 'critical')),
    CONSTRAINT ops_events_count CHECK (count > 0)
);
CREATE INDEX IF NOT EXISTS ops_events_last ON ops_events (last_at);

ALTER TABLE admin_audit ENABLE ROW LEVEL SECURITY;
ALTER TABLE admin_audit FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS staff ON admin_audit;
CREATE POLICY staff ON admin_audit USING (nullif(current_setting('glyphh.org_id', true), '') IS NULL);
ALTER TABLE ops_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE ops_events FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS staff ON ops_events;
CREATE POLICY staff ON ops_events USING (nullif(current_setting('glyphh.org_id', true), '') IS NULL);
