-- Org apps (docs/specs/apps.md, 3.1): the catalogue's table was called artifacts in the first cut. It is apps now,
-- its key, constraints, indexes and policy named after it, and each row says its type.
ALTER TABLE artifacts RENAME TO apps;
ALTER TABLE apps RENAME CONSTRAINT artifacts_pkey TO apps_pkey;
ALTER TABLE apps RENAME CONSTRAINT artifacts_state TO apps_state;
ALTER TABLE apps RENAME CONSTRAINT artifacts_org_id_fkey TO apps_org_id_fkey;
ALTER TABLE apps RENAME CONSTRAINT artifacts_runtime_id_fkey TO apps_runtime_id_fkey;
ALTER TABLE apps RENAME CONSTRAINT artifacts_submitted_by_fkey TO apps_submitted_by_fkey;
ALTER TABLE apps RENAME CONSTRAINT artifacts_reviewed_by_fkey TO apps_reviewed_by_fkey;
ALTER INDEX artifacts_one_per_app RENAME TO apps_one_per_app;
ALTER INDEX ix_artifacts_org_id RENAME TO ix_apps_org_id;

ALTER TABLE apps ADD COLUMN IF NOT EXISTS type TEXT DEFAULT 'page' NOT NULL;
ALTER TABLE apps ADD CONSTRAINT apps_type CHECK (type IN ('page', 'dashboard', 'doc', 'diagram', 'deck', 'design'));

DROP POLICY IF EXISTS tenant ON apps;
CREATE POLICY tenant ON apps USING (nullif(current_setting('glyphh.org_id', true), '') IS NULL OR org_id = nullif(current_setting('glyphh.org_id', true), '')::uuid);
