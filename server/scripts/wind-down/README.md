# Wind-down: cleaning the server's database

Glyphh's products were retired on 2026-11-18, and their code is deleted from this server: what is left is the
staff's sign-in, the staff view, Stripe's webhook and the health check
([architecture.md](../../docs/architecture.md)). Their **data** is still in the database until the command below
removes it. **Nothing runs that command:** no deploy, start, tick or test of the server. It is run by hand, once,
by whoever Chris names, after the subscriptions are cancelled ([cancel-subscriptions.md](cancel-subscriptions.md))
and a backup is taken.

    python -m glyphh_server.winddown counts
    python -m glyphh_server.winddown drop --platform-client-id <uuid> --yes-i-have-a-backup

It is part of the server's image (`src/glyphh_server/winddown.py`) and uses the app's own database setting, so it
is run inside the app's machine and no credential leaves it:

    fly ssh console -a glyphh-ai-server -C "python -m glyphh_server.winddown counts"

| Command | Does | Transactions |
|---|---|---|
| `counts` | Read only. The rows of every table below with `keep` or `drop` beside it (`absent` once dropped), any table in neither list, how many Ada Cloud schemas there are, orgs still `active` or `past_due`, orgs holding a subscription id, prepaid balances above zero and their total, OAuth clients that are not the platform's. Numbers only: never an email, a name, a key or a token | none |
| `drop` | Drops every org's Ada Cloud schema (`ada_<org id>`), then the products' tables in `public`, then deletes every OAuth client but the platform's own (its grants, tokens and codes go with a client). Prints each thing it dropped | one per schema (all at once runs Postgres out of lock memory: tried), then one for all the tables and the clients |

`drop` refuses, changing nothing, without both flags, with an id that is not a UUID, with one that is not the
server's own `GLYPHH_PLATFORM_CLIENT_ID`, or when no `oauth_clients` row has it. It is safe to run again: what is
gone is skipped, and a second run says `Nothing to drop: it was all gone already.` On any error it says so and ends
with status 1, the transaction it was in rolled back (the tables' one: none of them dropped, no client deleted);
schemas dropped before that stay dropped, and running it again finishes the job. A table in neither list is left
alone and named by `counts`.

## Where the database runs

Fly Managed Postgres, cluster `glyphh-ai-server-db` (id `82ylg01v1k70zx19`, org `glyphh-ai`, region `iad`, plan
`launch`), attached to the app `glyphh-ai-server` as its `GLYPHH_DATABASE_URL` secret. Redis (Upstash, on Fly:
`glyphh-ai-redis`) holds nothing kept. The three games' databases are other apps in another Fly org (`personal`:
`free-fall-frank-db`, `bams-and-brags-db`) and are not touched by anything here.

## Every table

Production's schema on the day the products were retired had 38 tables in `public`, and `schema_migrations`, made
by the schema step (`tests/db/production_2026_11_18.sql` is that schema, kept for the tests). Ada Cloud's data was
not among them: it is in a schema per org. The lists are `KEEP` and `DROP` in `winddown.py`; a test holds `KEEP` to
exactly the tables `db/schema.sql` makes and the models map, and both lists together to production's schema.

| Table | | The code that uses it |
|---|---|---|
| `schema_migrations` | KEEP | `db/schema.py`: the schema step's record of migrations |
| `orgs` | KEEP | Accounts, and each org's Stripe customer and subscription ids, billing status, `first_paid_at` and plan version: written by the webhook (`ops/billing/sync.py`), made at a first sign-in (`ops/orgs.py`), read by the staff view (`admin/`) and `GET /v1/me` |
| `users`, `identities` | KEEP | The people and the Google or GitHub ids they sign in with: `ops/auth/signin.py`, `ops/me.py`, `admin/users.py` |
| `invites` | KEEP | An invite still open is honoured at its person's first sign-in (`ops/invites.py`); nothing makes one any more |
| `plans`, `plan_versions` | KEEP | What each org paid for (`orgs.plan_version_id` points here, on delete restrict) and the Stripe price the webhook matches a subscription to (`ops/billing/items.py`); Free's version for a new org or an ended subscription (`ops/plans.py`); listed by `admin/plans.py`; seeded on a new database only (`db/seed.py`) |
| `oauth_clients`, `oauth_codes`, `connector_grants`, `connector_tokens` | KEEP, platform only | The platform signs in as an OAuth client: its sessions are grants and tokens here (`ops/connector/`, `api/oauth.py`, `api/oauth_pages.py`, `db/seed_clients.py`). `drop` deletes every other client (Claude's connector registrations, each rrotor's), and its grants, tokens and codes with it |
| `admin_audit`, `ops_events` | KEEP | The staff view's audit log (`admin/audit.py`) and the server's own warnings and errors (`obs/events_store.py`) |
| `traffic_zones`, `traffic_days`, `traffic_tops` | KEEP | Glyphh's own sites' traffic from Cloudflare (`ops/traffic/`, `admin/traffic.py`); glyphh.ai goes on |
| `ada_meter_events` | KEEP, a record | Each report of metered reads sent to Stripe: what an overage line on an invoice was made of. Nothing writes it any more; the staff dashboard adds up the month's (`admin/money.py`) |
| `llm_ledger`, `llm_balances` | KEEP | Money: top-ups paid, grants, refunds, and each org's prepaid balance. A top-up paid late is still credited by the webhook (`ops/billing/topup.py`); the staff view shows an org's balance (`admin/org_detail.py`). A balance above zero is owed back (`counts` says how many and how much) |
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

The server keeps no card, invoice or payment rows: those are Stripe's. The kept tables keep every column they had
(some no longer read: a plan version's limits, a user's `groups`): nothing here alters a kept table. Postgres's
`vector` extension, which Ada Cloud's schemas used, stays installed and unused.

## The order, in production

1. **Cancel the subscriptions** ([cancel-subscriptions.md](cancel-subscriptions.md)) and wait for Stripe's webhooks
   to land: the webhook finds an org by the ids this database holds. `counts` must say 0 orgs `active` or
   `past_due` (or Chris has decided about each that is left), and what to do about any balance above zero.
2. **Deploy this server** (a merge to main; CI deploys). Its start runs the schema step, which makes nothing new on
   production's database and leaves the products' tables as they are: no code reads them any more. Check
   `https://api.glyphh.ai/v1/health` and a staff sign-in on the platform.
3. **Back up** (below), and check the dump opens.
4. **`counts`**, and read it: a table "in neither list" is new since this was written, so stop and decide; note the
   rows of the kept tables.
5. **`drop`** with the platform's client id (the app's `GLYPHH_PLATFORM_CLIENT_ID`, a UUID, not a secret) and
   `--yes-i-have-a-backup`. It ends `Done.`; if it ends `Failed`, read why and run it again.
6. **Restart** is not needed (no code reads what was dropped), but one proves a start on the cleaned database:
   `fly apps restart glyphh-ai-server`.
7. **Verify:** `counts` again (every `drop` table `absent`, `ada schemas: 0`, 0 clients that are not the
   platform's, the kept tables' rows as noted except the OAuth tables, which shrank to the platform's); the health
   check; the staff view still open in a browser that was signed in before (its session survives), and a fresh
   sign-in.
8. **Unset the secrets nothing reads** (below), and remove the `ada` and `adajobs` machines if any are left
   (`fly machine list -a glyphh-ai-server`; their process groups are gone from `fly.toml`).

## Before: a backup

A full dump to a local file, through Fly's proxy (the URL's user, password and database are the ones in the app's
`GLYPHH_DATABASE_URL`; read them from the cluster's page on Fly, never paste them into a file here):

    fly mpg proxy 82ylg01v1k70zx19                      # in one terminal: localhost:16380
    pg_dump --format=custom --no-owner --file glyphh-server-$(date +%F).dump \
      "postgresql://<user>:<password>@localhost:16380/<database>"
    pg_restore --list glyphh-server-$(date +%F).dump | wc -l     # it opens, and lists what it holds

Fly's own backups of the cluster: `fly mpg backup list 82ylg01v1k70zx19`, and `fly mpg backup create 82ylg01v1k70zx19`
for one made now. Nothing in the server, the platform or rrotor writes database backups to R2: the R2 bucket
`glyphh-apps` is used by Bams & Brags for its photos (prefix `bamsandbrags/`).

The dump holds customers' precedents and uploaded files. Say how long it is kept, and delete it then.

## Fly secrets nothing reads any more

Names only. Once this server is deployed, none of these is read by any setting; unset them with
`fly secrets unset -a glyphh-ai-server <NAME> ...` (each unset restarts the app):

`GLYPHH_PRODUCTS`, `GLYPHH_RROTOR`, `GLYPHH_ADA_CLOUD`, `GLYPHH_ADA_HOSTS`, `GLYPHH_ADA_URL`,
`GLYPHH_ADA_READ_TIMEOUT`, `GLYPHH_ADA_WRITE_TIMEOUT`, `GLYPHH_ADA_WORKERS`, `GLYPHH_ADA_KERNELS_DIR`,
`GLYPHH_ADA_KERNEL_WORKERS`, `GLYPHH_ADA_IMPORT_BYTES`, `GLYPHH_LLM`, `GLYPHH_INFERENCE_URL`,
`GLYPHH_INFERENCE_KEY`, `GLYPHH_INFERENCE_TIMEOUT`, `GLYPHH_LICENSE_SIGNING_KEY`, `GLYPHH_LICENSE_KEY` (its old
name), `GLYPHH_STRIPE_PRICE_BASIC`, `GLYPHH_STRIPE_PRICE_PRO`, `GLYPHH_STRIPE_PRICE_TEAM`,
`GLYPHH_STRIPE_PRICE_ADA`, `GLYPHH_STRIPE_METER_ADA`, `GLYPHH_GITHUB_APP_ID`, `GLYPHH_GITHUB_APP_PRIVATE_KEY`,
`GLYPHH_GITHUB_APP_SLUG`, `GLYPHH_GITHUB_TRAFFIC_TOKEN`, `GLYPHH_GITHUB_TRAFFIC_REPOS`, `GLYPHH_INVITE_URL`,
`GLYPHH_MCP_ORIGINS`.

Which of them are set on the app is for `fly secrets list -a glyphh-ai-server` to say (this list is every setting
the code stopped reading). In GitHub, the repository secret `ADA_DEPLOY_KEY` is unused too: no build reads the
private Ada kernel any more. Still read: `GLYPHH_DATABASE_URL`, `GLYPHH_REDIS_URL`, `GLYPHH_SECRET_KEY`,
`GLYPHH_PLATFORM_CLIENT_ID`, `GLYPHH_PLATFORM_CLIENT_SECRET`, `GLYPHH_GOOGLE_CLIENT_ID` and `_SECRET`,
`GLYPHH_GITHUB_CLIENT_ID` and `_SECRET`, `GLYPHH_STRIPE_SECRET_KEY`, `GLYPHH_STRIPE_WEBHOOK_SECRET`,
`GLYPHH_STAFF_EMAILS`, `GLYPHH_CLOUDFLARE_API_TOKEN`, and CI's `FLY_API_TOKEN`.

## Tried

`tests/db/test_winddown.py`, on a throwaway database with production's schema, rows in the products' tables, three
Ada schemas, two other OAuth clients and money to settle: `counts` right and changing nothing; `drop` refused
without its flags or with another id; `drop` leaving exactly the 19 kept tables, one OAuth client and every user
and org, the platform's token still good; a second run dropping nothing; a failure rolled back and finished by
running again; the next start making none of it again. Never run against production.
