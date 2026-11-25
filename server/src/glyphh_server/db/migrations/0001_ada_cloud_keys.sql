-- Ada Cloud's API keys (glyphh_ada/keys.py): a runtime key of scope 'cloud', with a clearance. Every key made
-- before this is a runtime key with full clearance.
ALTER TABLE runtime_keys ADD COLUMN IF NOT EXISTS scope TEXT DEFAULT 'runtime' NOT NULL;
ALTER TABLE runtime_keys ADD COLUMN IF NOT EXISTS clearance NUMERIC(4, 3) DEFAULT 1 NOT NULL;
ALTER TABLE runtime_keys ADD CONSTRAINT runtime_keys_scope CHECK (scope IN ('runtime', 'cloud'));
ALTER TABLE runtime_keys ADD CONSTRAINT runtime_keys_clearance CHECK (clearance >= 0 AND clearance <= 1);
