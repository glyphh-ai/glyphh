-- Glyphh's products were retired on 2026-11-18. This removes their data from the server's database.
-- NOT RUN BY ANYTHING: no deploy, test or script calls it. Read README.md beside it first: the backup to take, the
-- row counts to look at (row-counts.sql), how to run it and what the server does at its next start.
--
-- One transaction: it all happens or none of it does. Run with psql and ON_ERROR_STOP, and give the platform's own
-- OAuth client id (the server's GLYPHH_PLATFORM_CLIENT_ID, a UUID, not a secret) so its sign-ins are the ones kept:
--
--   psql -v ON_ERROR_STOP=1 -v platform_client=<uuid> -f scripts/wind-down/drop-tables.sql "<database url>"
--
-- KEPT, untouched: schema_migrations, plans, plan_versions, orgs (their Stripe customer and subscription ids and
-- billing status), users, identities, invites, admin_audit, ops_events, traffic_zones, traffic_days, traffic_tops,
-- ada_meter_events, llm_ledger, llm_balances. KEPT, narrowed to the platform's own sign-ins: oauth_clients,
-- oauth_codes, connector_grants, connector_tokens.

\if :{?platform_client}
\else
  \echo 'Give the platform client id: -v platform_client=<uuid> (the server''s GLYPHH_PLATFORM_CLIENT_ID).'
  \quit
\endif

-- The platform's client must be there: without it step 3 would end every sign-in, staff's included.
SELECT EXISTS (SELECT 1 FROM oauth_clients WHERE id = :'platform_client'::uuid) AS platform_found \gset
\if :platform_found
\else
  \echo 'No oauth_clients row has the platform client id given: nothing was changed.'
  \quit
\endif

BEGIN;

-- It gives up rather than queue behind a long statement.
SET LOCAL lock_timeout = '10s';

-- 1. Ada Cloud's per-org schemas (ada_<org id>) are NOT dropped here but by drop-ada-schemas.sql, run before this:
--    dropping them all in one transaction takes a lock on every table and partition at once, which runs Postgres out
--    of lock memory (tried on a test database: "out of shared memory" at about a hundred schemas).

-- 2. The products' tables in public, children before the tables they point at.
--    Ada Cloud's counts (the reports sent to Stripe's meter, ada_meter_events, are kept: they are what was billed).
DROP TABLE IF EXISTS ada_model_days;
DROP TABLE IF EXISTS ada_usage;
--    The hosted models' use by day (the balance and its ledger are kept: they are money).
DROP TABLE IF EXISTS llm_usage_days;
--    Templates and what people installed of them (Agentic memory, the Orchestrator).
DROP TABLE IF EXISTS template_installs;
DROP TABLE IF EXISTS templates;
--    rrotor: the apps catalogue, runtime nodes, runtime keys and Ada Cloud API keys (both in runtime_keys), then the
--    runtimes themselves.
DROP TABLE IF EXISTS apps;
DROP TABLE IF EXISTS nodes;
DROP TABLE IF EXISTS runtime_keys;
DROP TABLE IF EXISTS rrotors;
--    Licence keys signed for paid periods.
DROP TABLE IF EXISTS licenses;
--    The plugin's installs: device codes and install tokens, then the installs.
DROP TABLE IF EXISTS device_codes;
DROP TABLE IF EXISTS tokens;
DROP TABLE IF EXISTS installs;
--    The Glyphh GitHub App's installations.
DROP TABLE IF EXISTS github_installations;
--    Enterprise single sign-on: the email domains, then each org's provider (its client secret, sealed).
DROP TABLE IF EXISTS sso_domains;
DROP TABLE IF EXISTS org_sso;
--    The public repositories' traffic (the repository is private now).
DROP TABLE IF EXISTS github_traffic_tops;
DROP TABLE IF EXISTS github_traffic_days;
DROP TABLE IF EXISTS github_traffic_repos;
--    The mods list (one row, `ada`).
DROP TABLE IF EXISTS mods;

-- 3. The connector: every OAuth client but the platform's own, and with each (ON DELETE CASCADE) its grants,
--    tokens and codes. The tables stay: the platform signs in through them.
DELETE FROM oauth_clients WHERE id <> :'platform_client'::uuid;

COMMIT;
