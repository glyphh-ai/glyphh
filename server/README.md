# server

The Glyphh server: headless, multi-tenant. Every capability is built SDK first, then API, then MCP, with one service function behind all three. Everything runs in Docker.

## Run it

    docker compose up --build

The API is on http://localhost:8080 (`/v1/health`, `/openapi.json`) and MCP on http://localhost:8080/mcp.

## Test it

    docker compose --profile test run --rm --build test

The suite runs against a real Postgres and fails under 100% coverage.

## Builds

Every push and pull request runs lint and the suite in Docker (`.github/workflows/ci.yml`). Every merge to main then publishes the image to `ghcr.io/glyphh-ai/server`, tagged with the commit and `main`. Where that image deploys to is not chosen yet.

## Docs

    uv sync --group docs
    uv run mkdocs serve

Then open http://127.0.0.1:8000. Pages live in `docs/`; diagrams are Mermaid blocks and reload on save.
