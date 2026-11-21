-- Glyphh's public repositories' traffic from GitHub, for the staff view (ops/traffic/github.py): each repository's last
-- 14 days as last pulled, each day's views and clones kept beyond GitHub's 14 days, each day's pull of its popular
-- referrers and paths. Pulled by the tick each hour; staff only (the policies below).
CREATE TABLE IF NOT EXISTS github_traffic_repos (
    repo TEXT NOT NULL,
    pulled_at TIMESTAMP WITH TIME ZONE NOT NULL,
    views BIGINT DEFAULT 0 NOT NULL,
    view_uniques BIGINT DEFAULT 0 NOT NULL,
    clones BIGINT DEFAULT 0 NOT NULL,
    clone_uniques BIGINT DEFAULT 0 NOT NULL,
    PRIMARY KEY (repo)
);

CREATE TABLE IF NOT EXISTS github_traffic_days (
    repo TEXT NOT NULL,
    day DATE NOT NULL,
    views BIGINT DEFAULT 0 NOT NULL,
    view_uniques BIGINT DEFAULT 0 NOT NULL,
    clones BIGINT DEFAULT 0 NOT NULL,
    clone_uniques BIGINT DEFAULT 0 NOT NULL,
    PRIMARY KEY (repo, day)
);

CREATE TABLE IF NOT EXISTS github_traffic_tops (
    repo TEXT NOT NULL,
    pulled_on DATE NOT NULL,
    kind TEXT NOT NULL,
    key TEXT NOT NULL,
    count BIGINT DEFAULT 0 NOT NULL,
    uniques BIGINT DEFAULT 0 NOT NULL,
    PRIMARY KEY (repo, pulled_on, kind, key)
);

ALTER TABLE github_traffic_repos ENABLE ROW LEVEL SECURITY;
ALTER TABLE github_traffic_repos FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS staff ON github_traffic_repos;
CREATE POLICY staff ON github_traffic_repos USING (nullif(current_setting('glyphh.org_id', true), '') IS NULL);
ALTER TABLE github_traffic_days ENABLE ROW LEVEL SECURITY;
ALTER TABLE github_traffic_days FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS staff ON github_traffic_days;
CREATE POLICY staff ON github_traffic_days USING (nullif(current_setting('glyphh.org_id', true), '') IS NULL);
ALTER TABLE github_traffic_tops ENABLE ROW LEVEL SECURITY;
ALTER TABLE github_traffic_tops FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS staff ON github_traffic_tops;
CREATE POLICY staff ON github_traffic_tops USING (nullif(current_setting('glyphh.org_id', true), '') IS NULL);
