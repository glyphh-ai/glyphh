#!/bin/sh
# Refresh the server's OpenAPI spec, the contract both SDKs are generated from.
set -eu
here="$(cd "$(dirname "$0")/.." && pwd)"
server="${GLYPHH_SERVER_DIR:-$here/../server}"
(cd "$server" && uv run --quiet python scripts/openapi.py) > "$here/openapi/glyphh.json"
echo "openapi/glyphh.json refreshed from $server"
