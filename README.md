# Glyphh

The official ways in to Glyphh:

- `sdk/typescript`: the TypeScript SDK (`@glyphh-ai/sdk`)
- `sdk/python`: the Python SDK (`glyphh`)
- `plugin`: the Glyphh plugin for agent hosts (Claude Code, Claude Desktop, Cursor and others), which connects them to Glyphh over MCP

## How the SDKs are made

Every server capability is an SDK method first. Each SDK is two layers:

- a generated client, from the server's OpenAPI spec in `openapi/glyphh.json` (`src/gen`, `src/glyphh/_gen`; never edit these by hand), and
- a small hand-designed surface on top: `new Glyphh().health()` in TypeScript, `Glyphh().health()` / `await AsyncGlyphh().health()` in Python.

When the server changes:

    ./scripts/openapi.sh                         # refresh openapi/glyphh.json from ../server
    (cd sdk/typescript && npx openapi-ts)        # regenerate the TypeScript client
    (cd sdk/python && uvx openapi-python-client generate --path ../../openapi/glyphh.json --meta none --output-path src/glyphh/_gen --overwrite)

## Test

Both suites run in Docker against the real server, built from the sibling `../server` checkout, and fail under 100% coverage of the hand-written code:

    docker compose run --rm test-typescript
    docker compose run --rm test-python
    docker compose down -v
