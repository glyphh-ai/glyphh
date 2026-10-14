# server

The Glyphh server: the one cloud part behind Glyphh's mods for Claude (`glyphh`, `glyphh-workspaces`, `glyphh-rpa`, `glyphh-programs`), sold as one subscription. It keeps accounts, one org per user, invites, the mods catalog, versioned per-seat plans billed through Stripe, installs signed in by device flow (RFC 8628), one per machine, workspace names (for the plan's limit), a signed license naming the mods the plan includes, and the record of programs: runtimes (one hosted per user, one local per install, each with its own token), programs and their versions (a commit each, in the person's own repo), deployments, runs, approvals, connector grants, the Glyphh GitHub App's installations (repo-scoped tokens minted per deploy), routine triggers (fired on a program's events, their tokens encrypted) and program events. The programs, runs and connector API is still to build. What a person makes stays on their machine or in their runtime. `docs/architecture.md` is the contract: the API, the data model and the plans.

## Run it

    docker compose up --build

The API is on http://localhost:8080 (`/v1/health`, `/openapi.json`, the docs at `/docs`).

Before the server starts, the image runs the schema step (`python -m glyphh_server.db.schema`): it creates missing tables, applies row-level security and seeds the mods (`glyphh`, `glyphh-workspaces` and `glyphh-programs` free, `glyphh-rpa` not) and the plans (Free, Pro, Team), each with its first version. Free includes the free mods; Pro and Team (`all_mods`) include every active mod. Until relaunch there are no migrations: after a change to an existing table the server refuses to boot and says so; reset the dev database with `docker compose down -v`.

Settings come from the environment (prefix `GLYPHH_`, or `.env`, never committed):

| Setting | What |
|---|---|
| `GLYPHH_ENV` | `dev` (default), `test` or `prod` |
| `GLYPHH_PUBLIC_URL` | The server's own address: the device flow's link and the provider callbacks (`/auth/{google,github}/callback`) |
| `GLYPHH_SECRET_KEY` | 32+ characters; signs the steps of the device sign-in page and of linking a provider |
| `GLYPHH_GOOGLE_CLIENT_ID`, `_SECRET`, `GLYPHH_GITHUB_CLIENT_ID`, `_SECRET` | Sign-in providers; a provider without both is not offered |
| `GLYPHH_LICENSE_KEY` | Base64 of a raw 32-byte Ed25519 private key that signs licenses. Required in prod; without it in dev and test a key is made at start (licenses then don't survive a restart) |
| `GLYPHH_STRIPE_SECRET_KEY`, `GLYPHH_STRIPE_WEBHOOK_SECRET` | Billing; without them billing answers `E_UNAVAILABLE` |
| `GLYPHH_STRIPE_PRICE_PRO`, `GLYPHH_STRIPE_PRICE_TEAM` | The Stripe prices the plans sell on. A price a plan's newest version doesn't sell on becomes a new plan version at the next boot |
| `GLYPHH_GITHUB_APP_ID`, `GLYPHH_GITHUB_APP_PRIVATE_KEY`, `GLYPHH_GITHUB_APP_SLUG` | The Glyphh GitHub App: its id, its private key (PEM; line breaks may be written as `\n`) and its slug (the install page is `https://github.com/apps/<slug>/installations/new`). Set the App's Setup URL to `{public_url}/v1/github/callback`. Without all three, installing the App answers `E_UNAVAILABLE` |
| `GLYPHH_SECRETS_KEY` | Base64 of 32 random bytes; encrypts routine trigger tokens at rest (AES-256-GCM). Without it routine triggers answer `E_UNAVAILABLE`; changing it makes the stored tokens unreadable |
| `GLYPHH_INVITE_URL` | Where an invite's link points (its token rides `?invite=`); defaults to `{public_url}/join` |

Make a license key, or a secrets key, with:

    python -c "import base64,os; print(base64.b64encode(os.urandom(32)).decode())"

## Layout

`src/glyphh_server/`, built database first, then the service functions, then thin routes:

- `models/`: the schema, one table per module (drawn in `docs/architecture.md`, Data model)
- `db/`: the engine, the schema step, the seed, the drift check and tenancy (row-level security keyed on the org)
- `ops/`: the service functions, one per capability; `ops/auth/` signing in and tokens, `ops/billing/` Stripe
- `api/`: the routes, every one with an OpenAPI operation id; `api/device_pages.py` is the device flow's plain HTML page, `api/link_pages.py` linking another sign-in provider through the same provider pages, `api/github_pages.py` installing the GitHub App in the browser
- `obs/`: JSON logs, each line with its trace id; every refusal is `{"error": {"code", "message", "trace_id"}}`

## Test it

    docker compose --profile test run --rm --build test

The suite runs against a real Postgres (its own `glyphh_test` database, made fresh each run) and fails under 100% line and branch coverage. Google, GitHub (sign-in and the GitHub App), Stripe and Anthropic's routines are faked at the HTTP layer; no test reaches them, and the keys the tests use are made fresh each run. `tests/test_code_shape.py` keeps files under 200 lines, functions under 40 and classes under 120. Lint with `uv run ruff check . && uv run ruff format --check .`.

To try billing against Stripe's test mode locally, forward its events with `stripe listen --forward-to localhost:8080/v1/stripe/webhook` and set the webhook secret it prints.

## Builds

Every push and pull request runs lint and the suite in Docker (`.github/workflows/ci.yml`). Every merge to main then publishes the image to `ghcr.io/glyphh-ai/server`, tagged with the commit and `main`.

## Docs

    uv sync --group docs
    uv run mkdocs serve

Then open http://127.0.0.1:8000/architecture/. The one doc is `docs/architecture.md`; diagrams are Mermaid blocks and reload on save.
