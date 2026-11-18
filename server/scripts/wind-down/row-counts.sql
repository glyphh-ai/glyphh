-- Read only: what the server's database holds, to look at before scripts/wind-down/drop-tables.sql and again after.
-- Every table of db/schema.sql, with what the clean-up does to it, then Ada Cloud's per-org schemas.
--
--   psql -v ON_ERROR_STOP=1 -f scripts/wind-down/row-counts.sql "<database url>"

SELECT c.relname AS "table",
       CASE
         WHEN c.relname IN ('schema_migrations', 'plans', 'plan_versions', 'orgs', 'users', 'identities', 'invites',
                            'admin_audit', 'ops_events', 'traffic_zones', 'traffic_days', 'traffic_tops',
                            'ada_meter_events', 'llm_ledger', 'llm_balances') THEN 'KEEP'
         WHEN c.relname IN ('oauth_clients', 'oauth_codes', 'connector_grants', 'connector_tokens') THEN 'KEEP (platform only)'
         WHEN c.relname IN ('ada_model_days', 'ada_usage', 'llm_usage_days', 'template_installs', 'templates', 'apps',
                            'nodes', 'runtime_keys', 'rrotors', 'licenses', 'device_codes', 'tokens', 'installs',
                            'github_installations', 'sso_domains', 'org_sso', 'github_traffic_tops',
                            'github_traffic_days', 'github_traffic_repos', 'mods') THEN 'DROP'
         ELSE 'NOT IN THE LIST: look before running'
       END AS "clean-up",
       (xpath('/row/n/text()', query_to_xml(format('SELECT count(*) AS n FROM public.%I', c.relname), false, true, '')))[1]::text::bigint AS "rows",
       pg_size_pretty(pg_total_relation_size(c.oid)) AS "size"
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND c.relkind = 'r'
ORDER BY 2, 1;

-- Ada Cloud: one schema per org that ever made a model. All of them are dropped.
SELECT count(DISTINCT n.nspname) AS "ada schemas",
       pg_size_pretty(coalesce(sum(pg_total_relation_size(c.oid)), 0)) AS "their size"
FROM pg_namespace n
LEFT JOIN pg_class c ON c.relnamespace = n.oid AND c.relkind IN ('r', 'p')
WHERE n.nspname ~ '^ada_[0-9a-f]{32}$';

-- Money to settle before anything is dropped: orgs still subscribed, and overage balances still held.
SELECT billing_status, count(*) AS orgs FROM orgs GROUP BY 1 ORDER BY 1;
SELECT count(*) AS "orgs with a subscription id" FROM orgs WHERE stripe_subscription_id IS NOT NULL;
SELECT count(*) AS "balances above zero", coalesce(sum(micros), 0) AS "micro-dollars held" FROM llm_balances WHERE micros > 0;

-- The connector: OAuth clients, and how many are not the platform's own (those go, with their grants and tokens).
SELECT count(*) AS "oauth clients", count(*) FILTER (WHERE name <> 'Glyphh') AS "not named Glyphh" FROM oauth_clients;
