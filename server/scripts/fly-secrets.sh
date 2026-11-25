#!/bin/sh
# One-time setup of glyphh-ai-server's own secrets (run once, by hand):
#   GLYPHH_SECRET_KEY   48 random bytes; staged straight into Fly, never printed
#   GLYPHH_DATABASE_URL the fresh `glyphh` database on glyphh-ai-server-db (fly mpg attach)
set -eu
cd "$(dirname "$0")/.."
APP=glyphh-ai-server
CLUSTER=82ylg01v1k70zx19

uv run python - "$APP" <<'EOF'
import base64, os, subprocess, sys

secret = base64.urlsafe_b64encode(os.urandom(48)).decode().rstrip("=")
env = f"GLYPHH_SECRET_KEY={secret}\n"
subprocess.run(["fly", "secrets", "import", "--stage", "-a", sys.argv[1]], input=env.encode(), check=True,
               stdout=subprocess.DEVNULL)
EOF

fly mpg attach "$CLUSTER" -a "$APP" --database glyphh --variable-name GLYPHH_DATABASE_URL
fly secrets list -a "$APP" | grep GLYPHH_
