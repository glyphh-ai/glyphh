# server

The Glyphh server, https://api.glyphh.ai.

> **Glyphh's products were retired on 2026-11-18** and their code is deleted from this repository. What is left:
> the staff's sign-in through the platform (`glyphh-ai/platform`), the staff view's API (`/v1/admin`), `GET /v1/me`,
> Stripe's webhook (so the old subscriptions' cancellations and last payments are recorded) and the health check.
> Any other address answers `410 E_WOUND_DOWN`. The products' data is removed from the database by a command run by
> hand, once: [`scripts/wind-down/`](scripts/wind-down/).

- [`docs/architecture.md`](docs/architecture.md): what the server does, its routes, settings and data.
- [`scripts/wind-down/README.md`](scripts/wind-down/README.md): every table kept or dropped, the clean-up command
  and the order to follow in production; [`cancel-subscriptions.md`](scripts/wind-down/cancel-subscriptions.md).

## Run it

    docker compose up --build

Compose runs Postgres, Redis and the server; the API is on http://localhost:8080 (`/v1/health`). Every dependency
is public: no build needs a key. Before the server starts, the image runs the schema step,
`python -m glyphh_server.db.schema` ([starting up](docs/architecture.md#starting-up-and-migrations)).

Production keeps its data, so a schema change is two edits: change `src/glyphh_server/db/schema.sql` (always the
latest shape, which a new database is made from) and add `src/glyphh_server/db/migrations/NNNN_name.sql`, the next
number (0015 is the first), which brings an existing database to it, run once and recorded in `schema_migrations`.
A dev database can be made again with `docker compose down -v`, or any database by hand with
`GLYPHH_RESET_DATABASE=1 python -m glyphh_server.db.reset`; nothing resets on deploy.

Settings come from the environment (prefix `GLYPHH_`, or `.env`, never committed): the
[settings table](docs/architecture.md#settings). `GLYPHH_SECRET_KEY` (32+ characters) is required.

## Layout

`src/glyphh_server/`:

- `models/`: the tables mapped for queries (`db/schema.sql` is the schema; `tests/db/test_schema_sql.py` fails when
  they disagree)
- `db/`: the engine, `schema.sql` and the schema step, the by-hand reset, the seeds, the drift check, tenancy
  (row-level security keyed on the org)
- `ops/`: the service functions; `ops/auth/` signing in, `ops/connector/` the OAuth 2.1 authorization server the
  platform signs in through, `ops/billing/` Stripe's webhook, `ops/traffic/` Cloudflare's numbers
- `admin/`: the staff view's queries
- `api/`: the routes; `api/gone.py` answers every address that has none
- `obs/`: JSON logs with trace ids, request metrics, ops events
- `winddown.py`: the clean-up command, never imported by the server

## Test it

    docker compose --profile test run --rm --build test

The suite runs against a real Postgres (its own `glyphh_test` database, fresh each run) and a real Redis, and fails
under 100% line and branch coverage. Google, GitHub, Stripe and Cloudflare are faked at the HTTP layer.
`tests/test_code_shape.py` keeps files under 200 lines, functions under 40 and classes under 120. Lint with
`uv run ruff check . && uv run ruff format --check .`.

## Builds

Every push and pull request runs lint and the suite in Docker (`.github/workflows/ci.yml`). Every merge to main
publishes the image to `ghcr.io/glyphh-ai/server`, tagged with the commit and `main`, and deploys it to Fly
(`fly.toml`, the app `glyphh-ai-server`, one process group).

## Docs

    uv sync --group docs
    uv run mkdocs serve
