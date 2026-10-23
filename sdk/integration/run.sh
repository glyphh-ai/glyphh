#!/bin/sh
# Both SDKs against a real Ada Cloud on this machine: glyphh-ai/server (the Ada API and its sync and jobs workers),
# Postgres with pgvector and Redis, on a Docker network of their own with no port published to the host. The tests
# run in containers on that network too, so nothing listens on the host.
#
#   ADA_SERVER_IMAGE=<image> sh sdk/integration/run.sh
#
# ADA_SERVER_IMAGE is an image of glyphh-ai/server at the commit under test, its branch ada-versions (contract 5:
# Ada versions, each kernel the registry lists installed) or later (its Dockerfile's `runtime` or `test` target),
# which needs the read-only deploy key of the private kernel to build:
#
#   docker build --target runtime --secret id=ada_deploy_key,src=$HOME/.ssh/glyphh_ada_deploy_key \
#     -t glyphh-server:ada <server checkout at ada-versions>
#
# It makes two people, their orgs and an API key each straight in that throwaway database (setup_key.py; the first
# org on Basic, as the whole way holds more than Free's 1,000 precedents; the second on Free, its month of requests
# already used), then runs test_cloud.py (Python) and cloud.test.mjs (TypeScript):
# create a model, import, learn, decide, backtest, activate, export; the Ada versions (the list, a model's Ada, a
# backtest on the beta, an upgrade to it, a rollback, E_NO_CHANGE and E_ADA_UNKNOWN, Glyphh-Contract on every
# answer); the usage, past the plan's calls a second (429 E_RATE) and past its month (403 E_LIMIT requests), every
# answer checked against contract/contract.json. Never against production.
#
# Each worker container starts a fixed 2 worker processes (GLYPHH_ADA_WORKERS, which the server reads as it reads
# --processes), and every container is capped in CPUs and memory, so a laptop is not taken over.
set -eu

IMAGE="${ADA_SERVER_IMAGE:?set ADA_SERVER_IMAGE to an image of glyphh-ai/server (see the top of this file)}"
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
RUN="glyphh-sdk-it-$$"
NET="$RUN"
ENVS="-e GLYPHH_DATABASE_URL=postgresql+asyncpg://glyphh:glyphh@db:5432/glyphh -e GLYPHH_REDIS_URL=redis://redis:6379/0
  -e GLYPHH_ADA_CLOUD=true -e GLYPHH_ADA_HOSTS=ada -e GLYPHH_SECRET_KEY=sdk-integration-secret-key-0123456789abcdef
  -e GLYPHH_PUBLIC_URL=http://ada:8080 -e GLYPHH_ADA_WORKERS=2"
# Each container's share of the machine: the database and a worker group a CPU and a GiB each, Redis less.
SMALL="--cpus 0.5 --memory 256m"
ONE="--cpus 1 --memory 1g"
TWO="--cpus 2 --memory 2g"

cleanup() {
  docker rm -f "$RUN-db" "$RUN-redis" "$RUN-api" "$RUN-sync" "$RUN-sync2" "$RUN-jobs" >/dev/null 2>&1 || true
  docker network rm "$NET" >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

docker network create "$NET" >/dev/null
# shellcheck disable=SC2086
docker run -d --name "$RUN-db" --network "$NET" --network-alias db $ONE \
  -e POSTGRES_USER=glyphh -e POSTGRES_PASSWORD=glyphh -e POSTGRES_DB=glyphh pgvector/pgvector:pg17 >/dev/null
# shellcheck disable=SC2086
docker run -d --name "$RUN-redis" --network "$NET" --network-alias redis $SMALL redis:8-alpine \
  redis-server --save "" --appendonly no >/dev/null
until docker exec "$RUN-db" pg_isready -U glyphh -d glyphh >/dev/null 2>&1; do sleep 1; done
sleep 2
# pgvector, made by the database's superuser (production: the cluster's Extensions page)
docker exec "$RUN-db" psql -q -U glyphh -d glyphh -c "CREATE EXTENSION IF NOT EXISTS vector" >/dev/null

# shellcheck disable=SC2086
docker run -d --name "$RUN-api" --network "$NET" --network-alias ada $ONE $ENVS -v "$HERE:/work:ro" "$IMAGE" \
  sh -c "python -m glyphh_server.db.schema && exec uvicorn glyphh_server.main:app --host 0.0.0.0 --port 8080" >/dev/null
tries=0
until docker exec "$RUN-api" python -c "import urllib.request; urllib.request.urlopen('http://ada:8080/v1/health')" >/dev/null 2>&1; do
  tries=$((tries + 1))
  if [ "$tries" -gt 120 ] || ! docker inspect -f '{{.State.Running}}' "$RUN-api" | grep -q true; then
    docker logs --tail 80 "$RUN-api" 2>&1
    exit 1
  fi
  sleep 1
done
# Two machines of the sync group and one of jobs, each with GLYPHH_ADA_WORKERS=2 processes.
# shellcheck disable=SC2086
docker run -d --name "$RUN-sync" --network "$NET" $ONE $ENVS "$IMAGE" python -m glyphh_ada.worker --queue sync >/dev/null
# shellcheck disable=SC2086
docker run -d --name "$RUN-sync2" --network "$NET" $ONE $ENVS "$IMAGE" python -m glyphh_ada.worker --queue sync >/dev/null
# shellcheck disable=SC2086
docker run -d --name "$RUN-jobs" --network "$NET" $ONE $ENVS "$IMAGE" python -m glyphh_ada.worker --queue jobs >/dev/null

KEYS="$(docker exec "$RUN-api" python /work/setup_key.py)"
KEY="$(echo "$KEYS" | sed -n 1p)"
FULL="$(echo "$KEYS" | sed -n 2p)"
TESTS="-e GLYPHH_API_KEY=$KEY -e ADA_FULL_KEY=$FULL -e GLYPHH_ADA_URL=http://ada:8080 -v $REPO/sdk:/sdk:ro -v $REPO/contract:/contract:ro $TWO"
# ADA_LIVE_DIR=<dir>: the live exchange behind each fixture written there, to refresh contract/fixtures.json from
if [ -n "${ADA_LIVE_DIR:-}" ]; then TESTS="$TESTS -e ADA_LIVE_DIR=/live -v $ADA_LIVE_DIR:/live"; fi

status=0
echo "== Python: glyphh"
# shellcheck disable=SC2086
docker run --rm --network "$NET" $TESTS -e PYTHONPATH=/sdk/python/src -e PYTHONDONTWRITEBYTECODE=1 python:3.13-slim \
  sh -c "pip install -q --root-user-action=ignore pytest 'jsonschema>=4.18' && python -m pytest -q -p no:cacheprovider /sdk/integration/test_cloud.py" \
  || status=1
echo "== TypeScript: @glyphh-ai/glyphh"
# shellcheck disable=SC2086
docker run --rm --network "$NET" $TESTS node:22-slim \
  sh -c "cp -R /sdk/typescript /tmp/ts && cd /tmp/ts && rm -rf node_modules dist && npm ci --silent && npx tsc -p . && SDK=/tmp/ts/dist/index.js node --test /sdk/integration/cloud.test.mjs" \
  || status=1
if [ "$status" != 0 ]; then
  for c in api sync sync2 jobs; do echo "== $c's logs"; docker logs --tail 60 "$RUN-$c" 2>&1; done
fi
exit "$status"
