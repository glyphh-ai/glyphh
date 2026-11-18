-- Glyphh's products were retired on 2026-11-18. This removes Ada Cloud's data: every org's own schema, ada_<org id>
-- (its models, spec versions, precedents (a partition per model), outcomes, jobs, requests and uploaded files).
-- NOT RUN BY ANYTHING. Read README.md beside it first; run it before drop-tables.sql.
--
-- One schema per transaction, on purpose: all of them in one transaction locks every table and partition at once
-- and runs Postgres out of lock memory. So a failure part-way leaves the schemas already dropped gone and the rest
-- whole; it is safe to run again until it lists none. The names are the workers' own (glyphh_ada/orgschema.py).
--
--   psql -v ON_ERROR_STOP=1 -f scripts/wind-down/drop-ada-schemas.sql "<database url>"

SELECT format('DROP SCHEMA IF EXISTS %I CASCADE', nspname)
FROM pg_namespace
WHERE nspname ~ '^ada_[0-9a-f]{32}$'
ORDER BY 1
\gexec

SELECT count(*) AS "ada schemas left" FROM pg_namespace WHERE nspname ~ '^ada_[0-9a-f]{32}$';
