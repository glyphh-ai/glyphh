#!/usr/bin/env bash
# Glyphh on this Mac, in one command: the database and server (this repo), the platform (../platform),
# and the ngrok tunnel to the public URL in .env (GLYPHH_PUBLIC_URL). The platform passes the server's paths
# through, so the tunnel points at the platform.
#
#   scripts/local.sh start     build and start everything, then wait until it answers
#   scripts/local.sh stop      stop everything (the database keeps its data)
#   scripts/local.sh restart   stop, then start
#   scripts/local.sh status    what is running, and whether it answers
#   scripts/local.sh logs      follow the server's and the platform's logs
set -euo pipefail

SERVER="$(cd "$(dirname "$0")/.." && pwd)"
PLATFORM="${GLYPHH_PLATFORM_DIR:-$SERVER/../platform}"
NGROK_LOG="${TMPDIR:-/tmp}/ngrok-glyphh.log"

public_url() {
  grep -E '^GLYPHH_PUBLIC_URL=' "$SERVER/.env" 2>/dev/null | head -1 | cut -d= -f2- || true
}

wait_for() {
  local name="$1" url="$2"
  for _ in $(seq 1 60); do
    if curl -sf -o /dev/null --max-time 3 "$url"; then echo "  $name answers ($url)"; return 0; fi
    sleep 2
  done
  echo "  $name did not answer at $url: see 'scripts/local.sh logs'" >&2
  return 1
}

tunnel_up() {
  local url; url="$(public_url)"
  if [[ -z "$url" || "$url" != https://* ]]; then echo "  no tunnel: GLYPHH_PUBLIC_URL in .env is not an https address"; return 0; fi
  if pgrep -f "ngrok http .*--url=$url" >/dev/null; then echo "  tunnel already up: $url"; return 0; fi
  pkill -f "ngrok http" 2>/dev/null || true
  nohup ngrok http 5173 --url="$url" --log="$NGROK_LOG" >/dev/null 2>&1 &
  wait_for "tunnel" "$url/v1/health"
}

start() {
  echo "server and database"
  (cd "$SERVER" && docker compose up -d --build db server)
  echo "platform"
  (cd "$PLATFORM" && docker compose up -d dev)
  wait_for "server" "http://localhost:8080/v1/health"
  wait_for "platform" "http://localhost:5173/sign-in"
  echo "tunnel"
  tunnel_up
}

stop() {
  pkill -f "ngrok http" 2>/dev/null && echo "tunnel stopped" || echo "no tunnel running"
  (cd "$PLATFORM" && docker compose stop dev)
  (cd "$SERVER" && docker compose stop server db)
}

status() {
  docker ps --filter "name=glyphh-" --format '  {{.Names}}\t{{.Status}}\t{{.Ports}}'
  pgrep -fl "ngrok http" | sed 's/^/  /' || echo "  no tunnel"
  for check in "server http://localhost:8080/v1/health" "platform http://localhost:5173/sign-in" "public $(public_url)/v1/health"; do
    set -- $check
    if curl -sf -o /dev/null --max-time 5 "$2"; then echo "  $1 answers"; else echo "  $1 does not answer ($2)"; fi
  done
}

logs() {
  (cd "$SERVER" && docker compose logs -f --tail 50 server) &
  (cd "$PLATFORM" && docker compose logs -f --tail 50 dev)
}

case "${1:-}" in
  start) start ;;
  stop) stop ;;
  restart) stop; start ;;
  status) status ;;
  logs) logs ;;
  *) sed -n '2,13p' "$0" | sed 's/^# \{0,1\}//'; exit 2 ;;
esac
