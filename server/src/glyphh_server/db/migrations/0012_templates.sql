-- The template library (docs/specs/templates.md): the templates Glyphh ships, seeded at every start, and each
-- person's installs of them (their org's rows only).
CREATE TABLE IF NOT EXISTS templates (
    slug TEXT NOT NULL,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    summary TEXT NOT NULL,
    version INTEGER NOT NULL,
    body JSONB NOT NULL,
    active BOOLEAN DEFAULT true NOT NULL,
    sort INTEGER DEFAULT 0 NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (slug)
);

CREATE TABLE IF NOT EXISTS template_installs (
    id UUID DEFAULT gen_random_uuid() NOT NULL,
    org_id UUID NOT NULL,
    user_id UUID NOT NULL,
    slug TEXT NOT NULL,
    version INTEGER NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(org_id) REFERENCES orgs (id) ON DELETE CASCADE,
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE,
    FOREIGN KEY(slug) REFERENCES templates (slug) ON DELETE CASCADE
);
CREATE UNIQUE INDEX IF NOT EXISTS template_installs_one_per_person ON template_installs (user_id, slug);
CREATE INDEX IF NOT EXISTS ix_template_installs_org_id ON template_installs (org_id);

ALTER TABLE template_installs ENABLE ROW LEVEL SECURITY;
ALTER TABLE template_installs FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant ON template_installs;
CREATE POLICY tenant ON template_installs USING (nullif(current_setting('glyphh.org_id', true), '') IS NULL OR org_id = nullif(current_setting('glyphh.org_id', true), '')::uuid);
