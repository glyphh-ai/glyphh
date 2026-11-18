# Wind-down: cleaning the server's database

Glyphh's products were retired on 2026-11-18. The code switch (`GLYPHH_PRODUCTS`, off by default:
[architecture.md](../../docs/architecture.md#wound-down-glyphh_products)) stops every product route. These scripts
remove the products' data. **Nothing runs them:** no deploy, test or tick. They are run by hand, once, by whoever
Chris names, after the subscriptions are cancelled ([cancel-subscriptions.md](cancel-subscriptions.md)).

| File | Does | Transaction |
|---|---|---|
| `row-counts.sql` | Read only: every table with KEEP or DROP beside it, its rows and size; Ada Cloud's schemas; the money left to settle | none |
| `drop-ada-schemas.sql` | Drops every org's Ada Cloud schema, `ada_<org id>` | one per schema (all at once runs Postgres out of lock memory: tried) |
| `drop-tables.sql` | Drops the products' tables in `public`; deletes every OAuth client but the platform's own | one, all or nothing |

## Where the database runs

Fly Managed Postgres, cluster `glyphh-ai-server-db` (id `82ylg01v1k70zx19`, org `glyphh-ai`, region `iad`, plan
`launch`), attached to the app `glyphh-ai-server` as its `GLYPHH_DATABASE_URL` secret. Redis (Upstash, on Fly:
`glyphh-ai-redis`) holds nothing kept. The three games' databases are other apps in another Fly org (`personal`:
`free-fall-frank-db`, `bams-and-brags-db`) and are not touched by anything here.

## Every table

`db/schema.sql` makes 39 tables in `public` (and `schema_migrations`, made by the schema step). Ada Cloud's data is
not among them: it is in a schema per org.

| Table | | Why |
|---|---|---|
| `schema_migrations` | KEEP | The schema step's record: without it the next start runs every migration again |
| `orgs` | KEEP | Accounts, and the only payment record the server holds: each org's Stripe customer and subscription ids, billing status, `first_paid_at`, plan version |
| `users`, `identities` | KEEP | The people and the Google or GitHub ids they sign in with |
| `invites` | KEEP | Who was asked into which org; read at sign-in |
| `plans`, `plan_versions` | KEEP | What each org paid for (`orgs.plan_version_id` points here, on delete restrict) and the Stripe price the webhook matches a cancellation to |
| `oauth_clients`, `oauth_codes`, `connector_grants`, `connector_tokens` | KEEP, platform only | The platform signs in as an OAuth client: its sessions are grants and tokens here. Every other client (Claude's connector registrations, each rrotor's) is deleted, and its grants, tokens and codes with it |
| `admin_audit`, `ops_events` | KEEP | The staff view's audit log and the server's own warnings and errors |
| `traffic_zones`, `traffic_days`, `traffic_tops` | KEEP | Glyphh's own sites' traffic from Cloudflare; glyphh.ai goes on |
| `ada_meter_events` | KEEP | Each report of metered reads sent to Stripe: what an overage line on an invoice was made of |
| `llm_ledger`, `llm_balances` | KEEP | Money: top-ups paid, grants, refunds, and each org's prepaid balance. A balance above zero is owed back (`row-counts.sql` says) |
| `ada_usage`, `ada_model_days` | DROP | Ada Cloud's reads by month and by model and day |
| `llm_usage_days` | DROP | The hosted models' tokens by day |
| `templates`, `template_installs` | DROP | The template library and what people installed (Agentic memory, the Orchestrator); the memory itself was Ada models |
| `apps` | DROP | The catalogue of apps published to rrotors |
| `rrotors`, `nodes` | DROP | Local and self-hosted runtimes and their nodes |
| `runtime_keys` | DROP | Runtime keys and Ada Cloud API keys (hashes) |
| `licenses` | DROP | Licence keys signed for paid periods |
| `installs`, `tokens`, `device_codes` | DROP | The plugin's installs, their tokens (hashes) and device sign-in codes |
| `github_installations` | DROP | The Glyphh GitHub App's installations |
| `org_sso`, `sso_domains` | DROP | Enterprise single sign-on: each org's provider, with its client secret (sealed), and its email domains |
| `github_traffic_repos`, `github_traffic_days`, `github_traffic_tops` | DROP | The public repository's traffic; it is private now |
| `mods` | DROP | One row, `ada` |
| every `ada_<org id>` schema | DROP | Ada Cloud: models, spec versions, precedents, outcomes, jobs, requests, uploaded files |

The server keeps no card, invoice or payment rows: those are Stripe's.

## Before: a backup

A full dump to a local file, through Fly's proxy (the URL's user, password and database are the ones in the app's
`GLYPHH_DATABASE_URL`; read them from the cluster's page on Fly, never paste them into a file here):

    fly mpg proxy 82ylg01v1k70zx19                      # in one terminal: localhost:16380
    pg_dump --format=custom --no-owner --file glyphh-server-$(date +%F).dump \
      "postgresql://<user>:<password>@localhost:16380/<database>"
    pg_restore --list glyphh-server-$(date +%F).dump | wc -l     # it opens, and lists what it holds

Fly's own backups of the cluster: `fly mpg backup list 82ylg01v1k70zx19`, and `fly mpg backup create 82ylg01v1k70zx19`
for one made now. Nothing in the server, the platform or rrotor writes database backups to R2: the R2 bucket
`glyphh-apps` is used by Bams & Brags for its photos (prefix `bamsandbrags/`). If backups of this database are in a
bucket, something outside these repositories put them there.

The dump holds customers' precedents and uploaded files. Say how long it is kept, and delete it then.

## Running it

1. Cancel the subscriptions first and wait for Stripe's webhooks to land (`orgs.billing_status` no longer `active`):
   the webhook finds an org by the ids this database holds.
2. Deploy the wound-down server (`GLYPHH_PRODUCTS` unset), so nothing is writing to the products' tables.
3. Look: `psql -v ON_ERROR_STOP=1 -f scripts/wind-down/row-counts.sql "<url>"` (the proxy's URL, as above), or
   `fly mpg connect 82ylg01v1k70zx19 -f scripts/wind-down/row-counts.sql`. A table marked `NOT IN THE LIST` is new
   since this was written: stop and decide.
4. Take the backup above.
5. `psql -v ON_ERROR_STOP=1 -f scripts/wind-down/drop-ada-schemas.sql "<url>"`. It ends with `ada schemas left: 0`;
   run it again if it stopped part-way.
6. `psql -v ON_ERROR_STOP=1 -v platform_client=<the server's GLYPHH_PLATFORM_CLIENT_ID> -f scripts/wind-down/drop-tables.sql "<url>"`.
   It refuses to start without the id, or with one no client has.
7. Restart the server at once: `fly apps restart glyphh-ai-server`. Until it restarts, a staff sign-in fails (it
   reads `org_sso`).
8. `row-counts.sql` again.

Everyone signed in through the platform stays signed in. Claude's connector registrations are gone; `/mcp` answers
without them (it asks for no token while wound down).

## What the server does at its next start, and what is left to do

**The dropped `public` tables come back, empty.** The schema step runs `db/schema.sql` at every start, and the code
that maps those tables is still there behind the switch, so it makes them again with no rows. That is harmless (the
data is gone, and the server starts and answers: tried against a test database), but the tables are not gone for
good until the products' code is deleted: the models, `db/schema.sql`, a migration that drops them, and the modules
that use them (`glyphh_ada`, `mcp`, `llm`, `ops/link`, `ops/templates`, the licence, runtime, apps, device and
billing-plan routes, and their tests). That is a pass of its own, not done here. Ada Cloud's schemas do not come
back: only its workers make them, and they are off.

**Turning the switch back on** (`GLYPHH_PRODUCTS=on`) after the clean-up gives working, empty products: no models,
keys, runtimes or installs.

## Tried

On a throwaway copy of the test suite's database (39 tables, 119 Ada schemas): `drop-tables.sql` without the id and
with a wrong id changed nothing; `drop-ada-schemas.sql` left none; `drop-tables.sql` left the 19 kept tables, one
OAuth client and every user and org; the schema step then ran and the wound-down server answered its health check.
Never run against production.
