#!/bin/sh
# Builds dist/server.mjs (dependencies pinned by package-lock.json, so every build is the same), one file with its dependencies inside, so the plugin
# runs it with plain `node` and no install step. The sources are copied to a
# folder outside the plugin (it is live-loaded) and built there, with the
# one mod module the server shares (hooks/glyphh/machine.ts):
# $GLYPHH_MCP_BUILD, else a temporary folder.
set -eu
HERE=$(cd "$(dirname "$0")" && pwd)
WORK=${GLYPHH_MCP_BUILD:-$(mktemp -d)}
mkdir -p "$WORK"
cp "$HERE/package.json" "$HERE/package-lock.json" "$WORK/"
rm -rf "$WORK/src" "$WORK/mcp" "$WORK/hooks" && mkdir -p "$WORK/mcp" "$WORK/hooks/glyphh"
cp -R "$HERE/src" "$WORK/mcp/src" && cp "$HERE/../hooks/glyphh/machine.ts" "$WORK/hooks/glyphh/"
(cd "$WORK" && npm ci --silent --no-audit --no-fund)
cat > "$WORK/tsconfig.json" <<JSON
{ "compilerOptions": { "target": "es2023", "lib": ["es2023"], "module": "esnext", "moduleResolution": "bundler",
  "strict": true, "noEmit": true, "skipLibCheck": true, "types": ["node"] },
  "include": ["mcp/src", "hooks"] }
JSON
(cd "$WORK" && node_modules/.bin/tsc -p tsconfig.json)
(cd "$WORK" && node_modules/.bin/esbuild mcp/src/server.ts \
  --bundle --platform=node --format=esm --target=node20 --log-level=warning \
  --banner:js="// Built by mcp/build.sh from mcp/src: edit those and rebuild." \
  --outfile="$HERE/dist/server.mjs")
echo "built $HERE/dist/server.mjs"
