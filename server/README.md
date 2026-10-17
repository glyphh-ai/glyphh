# server

The Glyphh server: the one cloud part behind Glyphh's mods for Claude, sold as one subscription: a plan, and every mod on the account (`ada`) an add-on on the same subscription; and one mod bought once, per machine, with no account (`glyphh-drip`: a Stripe Payment Link, then a licence the server signs for that install). It renders nothing: people use the platform (`glyphh-ai/platform`), or Claude through the Glyphh connector (`/mcp`, signed in with OAuth). It keeps accounts, one org per user, invites, the mods catalog, versioned per-seat plans billed through Stripe, each version with every included mod's limits, the versioned add-on catalog and each org's add-ons (one subscription item each, kept true by Stripe's webhook), installs signed in by device flow (RFC 8628), one per machine, a signed license carrying each included mod and its limits, and the record of Ada models: runtimes (one hosted per user, one local per install, each with its own token), the models (`models`, as rrotor runs them) and their versions (a commit each, in the person's own repo), deployments, runs, approvals, connector grants, the Glyphh GitHub App's installations (repo-scoped tokens minted per deploy), routine triggers (fired on a model's events, their tokens encrypted) and model events. The connector (OAuth 2.1 and `/mcp`, with the account and model tools and the account panel), the models record and the hosted runtimes (one Fly machine per person, made on first start, reached directly at `https://<machine>.glyphh.app` with a runtime key, stopped when idle, its plan's hours tallied) are built; calling a model never passes through here. What a person makes stays on their machine or in their runtime. `docs/architecture.md` is the contract: the API, the data model and the plans.

## Run it

    docker compose up --build

The API is on http://localhost:8080 (`/v1/health`, `/openapi.json`, the docs at `/docs`). Compose runs Postgres, Redis and the server.

Redis carries only live signals (pub/sub): an approval reaches whichever server process holds the person's `/v1/approvals/stream`, and a call reaches whichever holds the runtime's `/v1/runtime/link`. Nothing kept lives there; Postgres holds the record, so Redis saves nothing to disk. In production Redis runs on the server's own Fly machine, beside the server.

Before the server starts, the image runs the schema step (`python -m glyphh_server.db.schema`): it runs `db/schema.sql`, the one file that holds the schema (every table and index, and the tenant role and its row-level security; safe to run again), then seeds the mods (`ada`; a mod no longer seeded is retired), the plans (Free, Pro, Team), each with its first version (no plan includes a mod), and the add-ons, each with its first version (prices, per seat and limits are placeholders marked TBD in `db/seed_addons.py`). Until relaunch there are no migrations: after a change to an existing table the server refuses to boot and says so; reset the dev database with `docker compose down -v`.

Settings come from the environment (prefix `GLYPHH_`, or `.env`, never committed):

| Setting | What |
|---|---|
| `GLYPHH_ENV` | `dev` (default), `test` or `prod` |
| `GLYPHH_DATABASE_URL` | Postgres (`postgresql+asyncpg://…`) |
| `GLYPHH_REDIS_URL` | Redis, for live signals only (`redis://…`); in production on the server's own Fly machine |
| `GLYPHH_PUBLIC_URL` | The server's own address: the device flow's link and the provider callbacks (`/auth/{google,github}/callback`) |
| `GLYPHH_PLATFORM_URL` | The platform, the one web app (`https://app.glyphh.ai`; `http://localhost:3000` by default): where every browser step of a flow is sent. The server renders nothing |
| `GLYPHH_SECRET_KEY` | 32+ characters; signs the steps of the device sign-in page and of linking a provider |
| `GLYPHH_GOOGLE_CLIENT_ID`, `_SECRET`, `GLYPHH_GITHUB_CLIENT_ID`, `_SECRET` | Sign-in providers; a provider without both is not offered |
| `GLYPHH_LICENSE_KEY` | Base64 of a raw 32-byte Ed25519 private key that signs licenses. Required in prod; without it in dev and test a key is made at start (licenses then don't survive a restart) |
| `GLYPHH_STRIPE_SECRET_KEY`, `GLYPHH_STRIPE_WEBHOOK_SECRET` | Billing; without them billing answers `E_UNAVAILABLE` |
| `GLYPHH_STRIPE_PRICE_PRO`, `GLYPHH_STRIPE_PRICE_TEAM` | The Stripe prices the plans sell on. A price a plan's newest version doesn't sell on becomes a new plan version at the next boot |
| `GLYPHH_STRIPE_PRICE_ADA` | The Stripe prices the add-ons sell on (recurring, monthly, in the plans' currency). An add-on without one isn't on sale; a new one becomes a new add-on version at the next boot |
| `GLYPHH_GITHUB_APP_ID`, `GLYPHH_GITHUB_APP_PRIVATE_KEY`, `GLYPHH_GITHUB_APP_SLUG` | The Glyphh GitHub App: its id, its private key (PEM; line breaks may be written as `\n`) and its slug (the install page is `https://github.com/apps/<slug>/installations/new`). Set the App's Setup URL to `{public_url}/v1/github/callback`. Without all three, installing the App answers `E_UNAVAILABLE` |
| `GLYPHH_FLY_API_TOKEN`, `GLYPHH_FLY_APP`, `GLYPHH_FLY_IMAGE` | Hosted runtimes on Fly: a deploy token, the one app the machines live in, and the hosted rrotor image (`registry.fly.io/<app>:<version>`, private: it carries the Ada part). Without all three, hosting is off (`E_UNAVAILABLE` `hosting_off`). Also `GLYPHH_FLY_PUBLIC_DOMAIN` (`glyphh.app`: each runtime is `https://<machine>.<domain>`, a wildcard certificate and DNS record on the app), `GLYPHH_FLY_REGION` (`iad`), `GLYPHH_FLY_CPUS` (1), `GLYPHH_FLY_MEMORY_MB` (1024), `GLYPHH_FLY_VOLUME_GB` (3), `GLYPHH_RUNTIME_IDLE_MINUTES` (10) |
| `GLYPHH_SECRETS_KEY` | Base64 of 32 random bytes; encrypts routine trigger tokens at rest (AES-256-GCM). Without it routine triggers answer `E_UNAVAILABLE`; changing it makes the stored tokens unreadable |
| `GLYPHH_INVITE_URL` | Where an invite's link points (its token rides `?invite=`); defaults to `{public_url}/join` |
| `GLYPHH_MCP_ORIGINS` | Browser origins `/mcp` accepts besides the server's own, comma-separated; defaults to `https://claude.ai,https://claude.com`. A request without an `Origin` always passes |

Make a license key, or a secrets key, with:

    python -c "import base64,os; print(base64.b64encode(os.urandom(32)).decode())"

## Layout

`src/glyphh_server/`, built database first, then the service functions, then thin routes:

- `models/`: the schema, one table per module (drawn in `docs/architecture.md`, Data model)
- `db/`: the engine, `schema.sql` and the schema step, the seed, the drift check, tenancy (row-level security keyed on the org) and `signals.py`, the Redis client for live signals
- `ops/`: the service functions, one per capability; `ops/auth/` signing in and tokens, `ops/billing/` Stripe, `ops/connector/` the connector's OAuth 2.1 authorization server (clients, codes, grants, tokens)
- `api/`: the routes, every one with an OpenAPI operation id; `api/device_pages.py` is the device flow's plain HTML page, `api/link_pages.py` linking another sign-in provider through the same provider pages, `api/github_pages.py` installing the GitHub App in the browser, `api/oauth_pages.py` the connector's authorization and Allow page, `api/oauth.py` and `api/oauth_meta.py` its token, registration, revocation and metadata endpoints (refusals in OAuth's own shape), `api/mcp.py` `/mcp`
- `mcp/`: the connector's MCP server: the protocol (2026-07-28 and the earlier `initialize` revisions), the tools (`mcp/tools/`) and the account panel (`mcp/panel/`, an MCP App that inlines the MCP Apps client bundle)
- `obs/`: JSON logs, each line with its trace id; every refusal is `{"error": {"code", "message", "trace_id"}}`, but on the OAuth endpoints (OAuth's `{"error", "error_description"}`) and `/mcp`'s protocol errors (JSON-RPC)

## Test it

    docker compose --profile test run --rm --build test

The suite runs against a real Postgres (its own `glyphh_test` database, made fresh each run) and a real Redis and fails under 100% line and branch coverage. Google, GitHub (sign-in and the GitHub App), Stripe and Anthropic's routines are faked at the HTTP layer; no test reaches them, and the keys the tests use are made fresh each run. `tests/test_code_shape.py` keeps files under 200 lines, functions under 40 and classes under 120. Lint with `uv run ruff check . && uv run ruff format --check .`.

To try billing against Stripe's test mode locally, forward its events with `stripe listen --forward-to localhost:8080/v1/stripe/webhook` and set the webhook secret it prints.

## Builds

Every push and pull request runs lint and the suite in Docker (`.github/workflows/ci.yml`). Every merge to main then publishes the image to `ghcr.io/glyphh-ai/server`, tagged with the commit and `main`.

## Docs

    uv sync --group docs
    uv run mkdocs serve

Then open http://127.0.0.1:8000/architecture/. The one doc is `docs/architecture.md`; diagrams are Mermaid blocks and reload on save.
