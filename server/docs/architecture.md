# The Glyphh server

Glyphh's products (Ada Cloud, the connector, rrotor's licences and runtimes, apps, hosted models, plans and billing)
were retired on 2026-11-18, and their code is deleted from this repository. The games (Free Fall Frank, Bams & Brags,
Crabby Knife Fight) are other servers and never used this one. This is what is left, and why.

## What it does

| | Why it stays |
|---|---|
| The staff's sign-in | Glyphh's staff sign in on the platform (`glyphh-ai/platform`), which is this server's one OAuth client, with Google or GitHub |
| `GET /v1/me` | The platform reads who is signed in, and whether they are staff |
| The staff view, `/v1/admin/*` | Accounts, billing as recorded, traffic, the server's own health and errors, the audit log |
| Stripe's webhook | The old subscriptions' cancellations and last payments are recorded on their orgs |
| `GET /v1/health` | Fly's check, and CI's after a deploy |
| Everything else | `410 E_WOUND_DOWN`, so an old plugin, SDK, rrotor install or connector fails cleanly |

It renders nothing: every page a browser sees is the platform's.

## Routes

| Route | |
|---|---|
| `GET /v1/health` | `{status, version, database, redis}` |
| `POST /v1/stripe/webhook` | Signed by Stripe or refused; 204 |
| `GET /oauth/authorize` | The platform's authorization request (OAuth 2.1, PKCE S256): on to the platform's `/authorize` page |
| `GET /auth/providers` | `{providers: [google, github], sso: false}` |
| `GET /auth/{google\|github}/start?oauth=` | Off to the provider, tied to the browser by a short-lived cookie |
| `GET /auth/{provider}/callback` | Back from the provider: signed in (staff only), on to the platform's `/allow` page |
| `GET /auth/consent` | What the Allow page shows; CORS for the platform's origin only |
| `GET /auth/oauth/allow` | Allow or deny: back to the platform's redirect URI with a code |
| `POST /oauth/token` | Code or refresh token for tokens; the platform's client only |
| `POST /oauth/revoke` | Sign-out |
| `GET /v1/me` | `{id, email, name, role, providers, org, staff}` |
| `GET /v1/admin/dashboard`, `infra`, `alerts` | Totals and days, the server's measures, what needs a person |
| `GET /v1/admin/orgs`, `orgs/{org_id}`, `users`, `plans`, `marketing`, `traffic` | Lists for staff |
| `POST`, `DELETE /v1/admin/orgs/{org_id}/suspend` | Suspend an org, lift it |
| `GET /v1/admin/audit`, `events`; `POST /v1/admin/events/{id}/ack`, `events/ack` | The audit log; ops events and acknowledging them |

Any other address, and any of these asked with a method it does not take, answers (`api/gone.py`):

    410 {"error": {"code": "E_WOUND_DOWN",
                   "message": "Glyphh's products were retired on 2026-11-18. Questions: support@glyphh.ai",
                   "trace_id": "..."}}

A WebSocket on any path (a rrotor's runtime link) is accepted and closed with code 4401, which rrotor stops
reconnecting on. There is no switch that brings anything back: `GLYPHH_PRODUCTS` no longer exists.

Every refusal has that shape, `{"error": {"code", "message", "trace_id", ...}}`; a browser in the sign-in is sent
to the platform's `/error` page with the same code instead. A crash is `E_INTERNAL` with the trace id, never the
crash's own message. The trace id is the `x-request-id` header of every response.

## Who may sign in

Only an account whose verified email is in `GLYPHH_STAFF_EMAILS` (default `support@glyphh.ai`), and only through
the platform's own OAuth client (`GLYPHH_PLATFORM_CLIENT_ID`, made in the database at every start). Anyone else is
told the products are retired (410), at the provider's callback and on every `/v1` call; any other OAuth client
still in the database is refused at the token endpoint. The staff view also checks that the token is the
platform's, crosses orgs on purpose, and writes every request to `admin_audit`. A request with a token otherwise
sees only its own org's rows (row-level security, `db/tenancy.py`).

Access tokens are opaque, kept as hashes, one hour; refresh tokens thirty days, rotated on use. They are bound to
the resource `{public url}/mcp`: the retired connector's address, kept because every sign-in the database holds
was granted for it.

The staff view's responses still carry some of the retired products' keys, answered `0`, `[]` or `false`, because
the platform's screens read them (the dashboard's reads and models, an org's models, jobs, keys and licences, the
infrastructure page's queues, read latency and jobs, the traffic page's GitHub part). They go when the platform's
screens drop them.

## Stripe

The server starts no checkout, changes no subscription and reports no usage. The webhook reads the subscription an
event names from Stripe and keeps the org true to it: its status, its plan version (by the subscription's price),
when it renews; an ended subscription puts the org on Free. A top-up of a prepaid balance that is paid after the
wind-down (a Checkout started before it) is still credited to `llm_ledger` and `llm_balances`, once per session,
and logged as a warning: it is money owed back. Cancelling the subscriptions is a procedure, not code:
[`scripts/wind-down/cancel-subscriptions.md`](../scripts/wind-down/cancel-subscriptions.md).

## The tick

Every minute (`ops/tend.py`), one server process at a time (a Postgres advisory lock): a heartbeat on Redis, the
warnings and errors logged since the last tick moved from Redis to `ops_events`, and once an hour, with
`GLYPHH_CLOUDFLARE_API_TOKEN`, Glyphh's own sites' traffic pulled from Cloudflare.

## Starting up, and migrations

Before the server starts, the image runs the schema step, `python -m glyphh_server.db.schema`: the migrations a
database has not had (`db/migrations/NNNN_name.sql`, recorded in `schema_migrations`), then `db/schema.sql`, which
is the schema's latest shape and safe to run again, then a check that no mapped column is missing, then the seeds
(the plans, on a new database only; the platform's OAuth client, always). Migrations 0001 to 0014 were the
products' and are folded into `schema.sql`; there is none today, and the next is 0015.

`schema.sql` declares only the kept tables, so a start never makes a dropped table again; and nothing in the server
drops one. A database that still has the products' tables keeps them, unread, until the wind-down command is run by
hand: [`scripts/wind-down/README.md`](../scripts/wind-down/README.md).

## Data

Postgres (Fly Managed Postgres). Redis holds nothing kept.

| Tables | |
|---|---|
| `orgs`, `users`, `identities`, `invites` | Accounts: everyone is in exactly one org; an org carries its Stripe customer and subscription ids and billing status |
| `plans`, `plan_versions` | What was sold; every org is on a version |
| `oauth_clients`, `oauth_codes`, `connector_grants`, `connector_tokens` | The platform's client and its sign-ins |
| `admin_audit`, `ops_events` | Staff requests; the server's warnings and errors |
| `traffic_zones`, `traffic_days`, `traffic_tops` | Cloudflare's numbers for Glyphh's sites |
| `ada_meter_events`, `llm_ledger`, `llm_balances` | Money on record: metered reads reported to Stripe, prepaid balances and their entries |
| `schema_migrations` | The schema step's record |

## Settings

From the environment, prefix `GLYPHH_` (or `.env`, never committed).

| Setting | |
|---|---|
| `GLYPHH_ENV` | `dev`, `test` or `prod` |
| `GLYPHH_DATABASE_URL` | Postgres; a plain `postgres://` URL is made the asyncpg driver's |
| `GLYPHH_REDIS_URL` | Redis |
| `GLYPHH_SECRET_KEY` | Signs the sign-in steps; 32 characters or more, required |
| `GLYPHH_PUBLIC_URL`, `GLYPHH_PLATFORM_URL` | This server's address and the platform's |
| `GLYPHH_PLATFORM_CLIENT_ID`, `GLYPHH_PLATFORM_CLIENT_SECRET` | The platform's OAuth client, as the platform holds them |
| `GLYPHH_GOOGLE_CLIENT_ID`, `_SECRET`; `GLYPHH_GITHUB_CLIENT_ID`, `_SECRET` | The sign-in providers |
| `GLYPHH_STAFF_EMAILS` | Who may sign in, comma-separated; default `support@glyphh.ai` |
| `GLYPHH_STRIPE_SECRET_KEY`, `GLYPHH_STRIPE_WEBHOOK_SECRET` | The webhook's: reading a subscription, checking a signature |
| `GLYPHH_CLOUDFLARE_API_TOKEN` | Read-only, for the staff view's traffic; unset, not connected |
| `GLYPHH_VERSION`, `GLYPHH_LOG_LEVEL` | The build's commit; the log level |
| `GLYPHH_RESET_DATABASE` | Only for `python -m glyphh_server.db.reset`, by hand, never on deploy |
