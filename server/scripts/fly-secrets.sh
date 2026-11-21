#!/bin/sh
# One-time setup of glyphh-ai-server's own secrets (run once, by hand):
#   GLYPHH_LICENSE_KEY  a new Ed25519 private key; staged straight into Fly, never printed
#   GLYPHH_SECRET_KEY   48 random bytes
#   GLYPHH_DATABASE_URL the fresh `glyphh` database on glyphh-ai-server-db (fly mpg attach)
# Prints only the licence public key, as unpadded base64url: it goes into mods/release.json PUBLIC_KEY.
set -eu
cd "$(dirname "$0")/.."
APP=glyphh-ai-server
CLUSTER=82ylg01v1k70zx19

uv run python - "$APP" <<'EOF'
import base64, os, subprocess, sys
from cryptography.hazmat.primitives import serialization as s
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

key = Ed25519PrivateKey.generate()
private = key.private_bytes(s.Encoding.Raw, s.PrivateFormat.Raw, s.NoEncryption())
public = key.public_key().public_bytes(s.Encoding.Raw, s.PublicFormat.Raw)
secret = base64.urlsafe_b64encode(os.urandom(48)).decode().rstrip("=")
env = f"GLYPHH_LICENSE_KEY={base64.b64encode(private).decode()}\nGLYPHH_SECRET_KEY={secret}\n"
subprocess.run(["fly", "secrets", "import", "--stage", "-a", sys.argv[1]], input=env.encode(), check=True,
               stdout=subprocess.DEVNULL)
print("PUBLIC_KEY", base64.urlsafe_b64encode(public).decode().rstrip("="))
EOF

fly mpg attach "$CLUSTER" -a "$APP" --database glyphh --variable-name GLYPHH_DATABASE_URL
fly secrets list -a "$APP" | grep GLYPHH_
