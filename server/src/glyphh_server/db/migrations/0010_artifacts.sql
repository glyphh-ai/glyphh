-- Org artifacts (docs/specs/artifacts.md): the identity provider's groups kept on each person at single sign-on, the
-- groups that review an org's artifacts beside its admin, and the catalogue of apps on the org's rrotors.
ALTER TABLE users ADD COLUMN IF NOT EXISTS groups TEXT[] DEFAULT '{}'::text[] NOT NULL;
ALTER TABLE org_sso ADD COLUMN IF NOT EXISTS reviewers TEXT[] DEFAULT '{}'::text[] NOT NULL;

CREATE TABLE IF NOT EXISTS artifacts (
    id UUID DEFAULT gen_random_uuid() NOT NULL,
    org_id UUID NOT NULL,
    runtime_id UUID NOT NULL,
    name TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    version INTEGER NOT NULL,
    commit_sha TEXT NOT NULL,
    roles TEXT[] DEFAULT '{}'::text[] NOT NULL,
    state TEXT DEFAULT 'draft' NOT NULL,
    submitted_by UUID,
    submitted_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    reviewed_by UUID,
    reviewed_at TIMESTAMP WITH TIME ZONE,
    reason TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT artifacts_state CHECK (state IN ('draft', 'approved', 'rejected', 'retired')),
    FOREIGN KEY(org_id) REFERENCES orgs (id) ON DELETE CASCADE,
    FOREIGN KEY(runtime_id) REFERENCES rrotors (id) ON DELETE CASCADE,
    FOREIGN KEY(submitted_by) REFERENCES users (id) ON DELETE SET NULL,
    FOREIGN KEY(reviewed_by) REFERENCES users (id) ON DELETE SET NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS artifacts_one_per_app ON artifacts (runtime_id, name);
CREATE INDEX IF NOT EXISTS ix_artifacts_org_id ON artifacts (org_id);

ALTER TABLE artifacts ENABLE ROW LEVEL SECURITY;
ALTER TABLE artifacts FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant ON artifacts;
CREATE POLICY tenant ON artifacts USING (nullif(current_setting('glyphh.org_id', true), '') IS NULL OR org_id = nullif(current_setting('glyphh.org_id', true), '')::uuid);
