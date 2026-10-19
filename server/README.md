# server

The Glyphh server, https://api.glyphh.ai: accounts and orgs, installs signed in by device flow, the signed licence,
flat plans and per-second hosting on Stripe, the Glyphh connector (`/mcp`, OAuth 2.1), the hosted runtimes on Fly
and the record of each person's Ada models, runtimes and runs. It renders nothing (every browser step lands on the
platform, `glyphh-ai/platform`) and is never on the data path: a model is called at its runtime's own address.

- [`docs/architecture.md`](docs/architecture.md): the contract. The system, the API, the settings, the data model,
  and what is not built yet.
- [`docs/pricing.md`](docs/pricing.md): the plans and their rules, Stripe's setup and setting up an Enterprise
  customer.

## Run it

    docker compose up --build

Compose runs Postgres, Redis and the server; the API is on http://localhost:8080 (`/v1/health`, `/openapi.json`, the
docs at `/docs`). Before the server starts, the image runs the schema step, `python -m glyphh_server.db.schema`
([starting up](docs/architecture.md#starting-up-and-the-reset-on-deploy)). There are no migrations yet: after a
change to an existing table the server refuses to boot; reset the dev database with `docker compose down -v`.

Settings come from the environment (prefix `GLYPHH_`, or `.env`, never committed): the
[settings table](docs/architecture.md#settings). `GLYPHH_SECRET_KEY` (32+ characters) is required. Make a licence key
or a secrets key with:

    python -c "import base64,os; print(base64.b64encode(os.urandom(32)).decode())"

To try billing against Stripe's test mode, make the products once
([pricing.md](docs/pricing.md#stripe-once-per-account)) and forward its events with
`stripe listen --forward-to localhost:8080/v1/stripe/webhook`, setting the webhook secret it prints.

## Layout

`src/glyphh_server/`, built database first, then the service functions, then thin routes:

- `models/`: the tables mapped for queries, one per module (`db/schema.sql` is the schema;
  `tests/db/test_schema_sql.py` fails when they disagree)
- `db/`: the engine, `schema.sql` and the schema step, the seeds, the drift check, tenancy (row-level security keyed
  on the org) and `signals.py`, the Redis client for live signals
- `ops/`: the service functions, one per capability; `ops/auth/` signing in and tokens, `ops/billing/` Stripe,
  `ops/connector/` the connector's OAuth 2.1 authorization server
- `api/`: the routes, every one with an OpenAPI operation id; `*_pages.py` the browser steps, `oauth.py` and
  `oauth_meta.py` OAuth's endpoints (refusals in OAuth's own shape), `mcp.py` `/mcp`
- `mcp/`: the connector's MCP server: the protocol, the tools (`mcp/tools/`) and the account panel (`mcp/panel/`)
- `obs/`: JSON logs, each line with its trace id

## Test it

    docker compose --profile test run --rm --build test

The suite runs against a real Postgres (its own `glyphh_test` database, fresh each run) and a real Redis, and fails
under 100% line and branch coverage. Google, GitHub, Stripe and Anthropic's routines are faked at the HTTP layer; the
keys the tests use are made fresh each run. `tests/test_code_shape.py` keeps files under 200 lines, functions under 40
and classes under 120. Lint with `uv run ruff check . && uv run ruff format --check .`.

## Builds

Every push and pull request runs lint and the suite in Docker (`.github/workflows/ci.yml`). Every merge to main
publishes the image to `ghcr.io/glyphh-ai/server`, tagged with the commit and `main`, and deploys it to Fly
(`fly.toml`, the app `glyphh-ai-server`).

## Docs

    uv sync --group docs
    uv run mkdocs serve

Then open http://127.0.0.1:8000/architecture/. Diagrams are Mermaid blocks, each with its rendered image in
`docs/img/`.
