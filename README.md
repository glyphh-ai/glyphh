# Glyphh

The official ways in to Glyphh:

- `sdk/typescript`: the TypeScript SDK (`@glyphh-ai/sdk`)
- `sdk/python`: the Python SDK (`glyphh`)
- The component library (`@glyphh-ai/ui`) lives with the platform, in `glyphh-ai/platform` (`ui/`)
- `design`: the brief, the brand assets and how the design agent and the code agent work together
- `plugins/glyphh`: the Glyphh plugin for Claude and Codex: Glyphh's MCP server (signed in with Google or GitHub) and a skill that teaches the agent Glyphh. One folder, two manifests (`.claude-plugin/`, `.codex-plugin/`).

## Install the plugin

- **Claude Code:** `/plugin marketplace add glyphh-ai/glyphh`, then `/plugin install glyphh@glyphh`, then `/mcp` → glyphh → Authenticate.
- **Codex:** `codex plugin marketplace add glyphh-ai/glyphh`, then `codex plugin add glyphh@glyphh`, then `codex mcp login glyphh`.
- **Claude Desktop, claude.ai, ChatGPT:** add a custom connector with the server's `/mcp` URL (until Glyphh is listed in their directories).

The repo is private for now: from a local checkout, use its folder in place of `glyphh-ai/glyphh`. The server URL in the plugin is the development tunnel until launch, then `https://api.glyphh.ai/mcp`.

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
