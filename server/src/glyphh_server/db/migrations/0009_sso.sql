-- Single sign-on by OpenID Connect, per org (Enterprise, ops/sso.py): the org's issuer and client (its secret sealed),
-- the email domains that route a sign-in to it, and whether its people must use it. An SSO account is a third identity
-- provider, `sso`.
CREATE TABLE IF NOT EXISTS org_sso (
    org_id UUID NOT NULL,
    issuer TEXT NOT NULL,
    client_id TEXT NOT NULL,
    client_secret TEXT NOT NULL,
    enforced BOOLEAN DEFAULT false NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (org_id),
    FOREIGN KEY(org_id) REFERENCES orgs (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS sso_domains (
    domain TEXT NOT NULL,
    org_id UUID NOT NULL,
    PRIMARY KEY (domain),
    FOREIGN KEY(org_id) REFERENCES org_sso (org_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_sso_domains_org_id ON sso_domains (org_id);

ALTER TABLE identities DROP CONSTRAINT IF EXISTS identities_provider;
ALTER TABLE identities ADD CONSTRAINT identities_provider CHECK (provider IN ('google', 'github', 'sso'));

ALTER TABLE org_sso ENABLE ROW LEVEL SECURITY;
ALTER TABLE org_sso FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant ON org_sso;
CREATE POLICY tenant ON org_sso USING (nullif(current_setting('glyphh.org_id', true), '') IS NULL OR org_id = nullif(current_setting('glyphh.org_id', true), '')::uuid);
ALTER TABLE sso_domains ENABLE ROW LEVEL SECURITY;
ALTER TABLE sso_domains FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant ON sso_domains;
CREATE POLICY tenant ON sso_domains USING (nullif(current_setting('glyphh.org_id', true), '') IS NULL OR org_id = nullif(current_setting('glyphh.org_id', true), '')::uuid);
