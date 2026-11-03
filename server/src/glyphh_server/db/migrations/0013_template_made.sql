-- A template's `make` op (docs/specs/templates.md): the models an install made for its person, by name, so that
-- removing the template deletes them too.
ALTER TABLE template_installs ADD COLUMN IF NOT EXISTS made TEXT[] DEFAULT '{}'::text[] NOT NULL;
