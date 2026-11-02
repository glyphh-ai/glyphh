#!/bin/sh
# Install, start, check and connect a local rrotor: the runtime that hosts your programs and CLIs, in a container
# on this machine, its API on 127.0.0.1 only. Used by the glyphh plugin's rrotor skill; runs by hand too.
#
#   rrotor.sh install [--port 7777] [--image IMAGE|pinned] [--runtime auto|container|orbstack|docker]
#   rrotor.sh connect            # adds rrotor's /mcp to Claude Code (user scope), the token read from its file; then links
#   rrotor.sh link               # links rrotor to Glyphh: the runtime token from the server (this machine's sign-in) handed to rrotor
#   rrotor.sh update             # the rrotor release this plugin pins: pulled, the container made again on its volume, linked
#   rrotor.sh status | start | stop
#   rrotor.sh deploy FOLDER [COMMIT]   # a program's folder at a commit (HEAD), as a git bundle
#   rrotor.sh uninstall [--purge]      # the container; --purge also its volume (every program, run and secret) and the token
#
# Where things are: the container `glyphh-rrotor`, its named volume `glyphh-rrotor-data` (/data), the local token in
# ~/.glyphh/rrotor/token (0600, never printed; the container gets only its SHA-256), and the settings the container
# was made with in ~/.glyphh/rrotor/install.env. Every answer is one JSON line on stdout; exit 1 on a failure, with
# {"ok": false, "error": ...}.
set -eu

PINNED_VERSION="0.3.0"                      # the rrotor release this plugin release was made against (tests/rrotor-pin.test.ts holds it to deploy/)
IMAGE_REPO="ghcr.io/glyphh-ai/rrotor"
NAME="glyphh-rrotor"
VOLUME="glyphh-rrotor-data"
INSIDE=7777
LABEL_TOKEN="ai.glyphh.rrotor.local-token-sha256"
LABEL_IMAGE="ai.glyphh.rrotor.image"
HOME_DIR="${GLYPHH_HOME:-$HOME/.glyphh}/rrotor"
TOKEN_FILE="$HOME_DIR/token"
SETTINGS="$HOME_DIR/install.env"
SERVER="${GLYPHH_SERVER_URL:-https://api.glyphh.ai}"

say() { printf '%s\n' "$1"; }
json_str() { printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g' | tr -d '\n'; }
fail() { say "{\"ok\": false, \"error\": \"$(json_str "$1")\"}"; exit 1; }

# --- settings kept between calls ------------------------------------------------------------------------------------

PORT=7777
IMAGE_OVERRIDE=""                           # a developer's own image (--image); empty: the pinned release
CHOICE="${RROTOR_RUNTIME:-auto}"
if [ -f "$SETTINGS" ]; then
  # shellcheck disable=SC1090
  . "$SETTINGS"
fi
IMAGE=""

keep_settings() {
  mkdir -p "$HOME_DIR"
  umask 077
  printf 'PORT=%s\nIMAGE_OVERRIDE=%s\nCHOICE=%s\n' "$PORT" "$IMAGE_OVERRIDE" "$CHOICE" >"$SETTINGS"
}

# --- which container runtime (Apple's container, then OrbStack, then Docker) -----------------------------------------

KIND=""
CLI=""

apple_container_fits() {
  [ "$(uname -s)" = "Darwin" ] || return 1
  [ "$(uname -m)" = "arm64" ] || return 1
  major="$(sw_vers -productVersion 2>/dev/null | cut -d. -f1)"
  [ -n "$major" ] && [ "$major" -ge 26 ]
}

find_docker() {
  for p in "$(command -v docker 2>/dev/null || true)" /usr/local/bin/docker /opt/homebrew/bin/docker \
    "$HOME/.orbstack/bin/docker" /Applications/Docker.app/Contents/Resources/bin/docker; do
    if [ -n "$p" ] && [ -x "$p" ]; then
      printf '%s' "$p"
      return 0
    fi
  done
  return 1
}

try_container() {
  c="$(command -v container 2>/dev/null || echo /usr/local/bin/container)"
  [ -x "$c" ] && apple_container_fits && "$c" system status >/dev/null 2>&1 || return 1
  KIND=container
  CLI="$c"
}

try_orbstack() {
  d="$(find_docker)" || return 1
  "$d" --context orbstack info --format '{{.ServerVersion}}' >/dev/null 2>&1 || return 1
  KIND=orbstack
  CLI="$d --context orbstack"
}

try_docker() {
  d="$(find_docker)" || return 1
  "$d" info --format '{{.ServerVersion}}' >/dev/null 2>&1 || return 1
  KIND=docker
  CLI="$d"
}

detect() {
  case "$CHOICE" in
    auto) try_container || try_orbstack || try_docker || true ;;
    container) try_container || true ;;
    orbstack) try_orbstack || true ;;
    docker) try_docker || true ;;
    *) fail "--runtime is auto, container, orbstack or docker." ;;
  esac
  [ -n "$KIND" ] && return 0
  if [ "$CHOICE" != auto ]; then
    fail "rrotor would run in $CHOICE, which is not running here. Start it, or use --runtime auto."
  elif apple_container_fits; then
    fail "rrotor needs a container runtime: install Apple's container (its signed installer from github.com/apple/container/releases, then: container system start), or OrbStack (orbstack.dev), or Docker Desktop; then install again."
  else
    fail "rrotor needs a container runtime: install and start Docker (docker.com) or OrbStack (orbstack.dev, on a Mac); then install again."
  fi
}

# --- the local token: made once, kept 0600; the container gets its SHA-256 only --------------------------------------

sha256() {
  if command -v shasum >/dev/null 2>&1; then shasum -a 256 | cut -d' ' -f1; else sha256sum | cut -d' ' -f1; fi
}

token() {
  if [ ! -s "$TOKEN_FILE" ]; then
    mkdir -p "$HOME_DIR"
    chmod 700 "$HOME_DIR"
    umask 077
    if command -v openssl >/dev/null 2>&1; then
      openssl rand -hex 32 >"$TOKEN_FILE"
    else
      od -An -tx1 -N32 /dev/urandom | tr -d ' \n' >"$TOKEN_FILE"
      printf '\n' >>"$TOKEN_FILE"
    fi
    chmod 600 "$TOKEN_FILE"
  fi
  TOKEN_SHA="$(tr -d ' \n' <"$TOKEN_FILE" | sha256)"
}

# --- the container ---------------------------------------------------------------------------------------------------

server_for_container() {
  # this machine's localhost is not the container's: a Glyphh server under test on localhost is the host's
  if [ "$KIND" = container ]; then
    printf '%s' "$SERVER"
  else
    printf '%s' "$SERVER" | sed -E 's#^(https?://)(localhost|127\.0\.0\.1)([:/]|$)#\1host.docker.internal\3#'
  fi
}

found_state() {
  # "running|stopped|missing <token sha> <image>"
  out="$($CLI inspect "$NAME" 2>/dev/null || true)"
  if [ -z "$out" ] || [ "$out" = "[]" ]; then
    echo "missing - -"
    return
  fi
  if [ "$KIND" = container ]; then
    flat="$(printf '%s' "$out" | tr -d '\n ')"
    state=stopped
    printf '%s' "$flat" | grep -q '"status":"running"' && state=running
    sha="$(printf '%s' "$flat" | sed -n "s/.*\"$LABEL_TOKEN\":\"\([0-9a-f]*\)\".*/\1/p")"
    img="$(printf '%s' "$flat" | sed -n "s#.*\"$LABEL_IMAGE\":\"\([^\"]*\)\".*#\1#p")"
  else
    line="$($CLI inspect --format "{{.State.Running}} {{index .Config.Labels \"$LABEL_TOKEN\"}} {{index .Config.Labels \"$LABEL_IMAGE\"}}" "$NAME")"
    state=stopped
    [ "${line%% *}" = true ] && state=running
    rest="${line#* }"
    sha="${rest%% *}"
    img="${rest#* }"
  fi
  echo "$state ${sha:--} ${img:--}"
}

run_container() {
  envs="-e RROTOR_MODE=local -e RROTOR_SERVER=$(server_for_container) -e RROTOR_HOST_PORT=$PORT -e RROTOR_LOCAL_TOKEN_SHA256=$TOKEN_SHA"
  labels="--label $LABEL_TOKEN=$TOKEN_SHA --label $LABEL_IMAGE=$IMAGE"
  publish="127.0.0.1:$PORT:$INSIDE"
  if [ "$KIND" = container ]; then
    # Apple's container: a VM per container, so none of Docker's sandbox options apply
    # shellcheck disable=SC2086
    $CLI run --detach --name "$NAME" --volume "$VOLUME:/data" --publish "$publish" $envs $labels "$IMAGE" >/dev/null
  else
    # bubblewrap (rrotor's program sandbox) makes namespaces and mounts /proc, which Docker's default seccomp
    # profile, AppArmor profile and masked paths refuse; rrotor's own seccomp filter and Landlock hold each run
    apparmor=""
    [ "$(uname -s)" = Linux ] && apparmor="--security-opt apparmor=unconfined"
    # shellcheck disable=SC2086
    $CLI run --detach --name "$NAME" --restart unless-stopped --read-only --tmpfs /tmp:exec,mode=1777 \
      --volume "$VOLUME:/data" --publish "$publish" \
      --security-opt seccomp=unconfined --security-opt systempaths=unconfined $apparmor \
      $envs $labels "$IMAGE" >/dev/null
  fi
}

remove_container() {
  if [ "$KIND" = container ]; then $CLI delete --force "$NAME" >/dev/null 2>&1 || true; else $CLI rm --force "$NAME" >/dev/null 2>&1 || true; fi
}

url() { printf 'http://127.0.0.1:%s' "$PORT"; }

wait_up() {
  i=0
  while [ "$i" -lt 60 ]; do
    if curl -fsS --max-time 2 "$(url)/healthz" >/dev/null 2>&1; then return 0; fi
    sleep 1
    i=$((i + 1))
  done
  return 1
}

api() {
  # api METHOD PATH [BODY-FILE]: rrotor's answer; the token sent from its file, never on the command line
  method="$1"
  path="$2"
  if [ $# -ge 3 ]; then
    curl -sS --max-time 120 -X "$method" -H "@$HEADER" -H 'content-type: application/json' --data-binary "@$3" "$(url)$path"
  else
    curl -sS --max-time 30 -X "$method" -H "@$HEADER" "$(url)$path"
  fi
}

header_file() {
  HEADER="$(mktemp "${TMPDIR:-/tmp}/rrotor-header.XXXXXX")"
  chmod 600 "$HEADER"
  printf 'Authorization: Bearer %s\n' "$(tr -d ' \n' <"$TOKEN_FILE")" >"$HEADER"
  trap 'rm -f "$HEADER"' EXIT
}

userns_hint() {
  f=/proc/sys/kernel/apparmor_restrict_unprivileged_userns
  if [ -r "$f" ] && [ "$(cat "$f")" = 1 ]; then
    printf '%s' "This Linux host restricts unprivileged user namespaces, so the sandbox cannot start: sudo sysctl -w kernel.apparmor_restrict_unprivileged_userns=0 (and keep it in /etc/sysctl.d/)."
  fi
}

mcp_command() {
  printf "claude mcp add --transport http --scope user rrotor %s/mcp --header \"Authorization: Bearer \$(cat %s)\"" "$(url)" "$TOKEN_FILE"
}

# --- commands --------------------------------------------------------------------------------------------------------

cmd_install() {
  while [ $# -gt 0 ]; do
    case "$1" in
      --port) PORT="$2"; shift 2 ;;
      --image) IMAGE_OVERRIDE="$2"; shift 2 ;; # `--image pinned` goes back to the pinned release
      --runtime) CHOICE="$2"; shift 2 ;;
      *) fail "install takes --port, --image and --runtime." ;;
    esac
  done
  case "$PORT" in '' | *[!0-9]*) fail "--port is a number." ;; esac
  [ "$IMAGE_OVERRIDE" = pinned ] && IMAGE_OVERRIDE=""
  IMAGE="${IMAGE_OVERRIDE:-$IMAGE_REPO:$PINNED_VERSION}"
  command -v curl >/dev/null 2>&1 || fail "curl is needed."
  detect
  token
  keep_settings
  set -- $(found_state)
  state="$1"
  if [ "$state" != missing ] && { [ "$2" != "$TOKEN_SHA" ] || [ "$3" != "$IMAGE" ]; }; then
    remove_container # another token or image: made again; the volume (programs, runs, secrets) stays
    state=missing
  fi
  if [ "$state" = missing ]; then
    if ! $CLI image pull "$IMAGE" >/dev/null 2>&1; then
      fail "Could not pull $IMAGE. If it is private, sign in (docker login ghcr.io) or wait until it is public; a local build can be given with --image."
    fi
    run_container || fail "The container would not start: $($CLI logs "$NAME" 2>&1 | tail -n 3 | tr '\n' ' ')"
  elif [ "$state" = stopped ]; then
    $CLI start "$NAME" >/dev/null
  fi
  wait_up || fail "rrotor did not answer on $(url) within a minute. Its log: $($CLI logs "$NAME" 2>&1 | tail -n 5 | tr '\n' ' ')"
  header_file
  health="$(api GET /v1/health)"
  printf '%s' "$health" | grep -q '"version"' || fail "rrotor answered, but not to its token: $health"
  ready=true
  printf '%s' "$health" | tr -d ' ' | grep -q '"ready":false' && ready=false
  say "{\"ok\": true, \"runtime\": \"$KIND\", \"image\": \"$(json_str "$IMAGE")\", \"url\": \"$(url)\", \"mcp\": \"$(url)/mcp\", \"token_file\": \"$(json_str "$TOKEN_FILE")\", \"sandbox_ready\": $ready, \"hint\": \"$(json_str "$(userns_hint)")\", \"connect\": \"$(json_str "$(mcp_command)")\"}"
}

cmd_connect() {
  [ -s "$TOKEN_FILE" ] || fail "No local token yet: install first."
  command -v claude >/dev/null 2>&1 || fail "The claude command is not on PATH. Run this yourself: $(mcp_command)"
  claude mcp remove --scope user rrotor >/dev/null 2>&1 || true
  claude mcp add --transport http --scope user rrotor "$(url)/mcp" \
    --header "Authorization: Bearer $(tr -d ' \n' <"$TOKEN_FILE")" >/dev/null 2>&1 \
    || fail "claude mcp add refused. Run this yourself: $(mcp_command)"
  link=skipped
  if [ -s "$INSTALL_FILE" ] && curl -fsS --max-time 2 "$(url)/healthz" >/dev/null 2>&1; then
    header_file
    link_state
    if [ "$LINK_STATE" = no_token ]; then do_link; link="$LINK_RESULT"; else link="${LINK_STATE:-unknown}"; fi
  fi
  say "{\"ok\": true, \"mcp\": \"rrotor\", \"url\": \"$(url)/mcp\", \"scope\": \"user\", \"link\": \"$(json_str "$link")\", \"next\": \"Restart Claude Code (or run /mcp) to load rrotor's tools.\"}"
}

# --- the link to Glyphh: the runtime token the server issues to this machine's sign-in, handed to rrotor ----------------

INSTALL_FILE="${GLYPHH_HOME:-$HOME/.glyphh}/install.json"

json_field() { sed -n "s/.*\"$1\": *\"\([^\"]*\)\".*/\1/p" | head -n 1; }

link_state() {
  # The link's state and runtime id as rrotor reports them (GET /v1/health); empty when it cannot be asked.
  health="$(api GET /v1/health 2>/dev/null || true)"
  LINK_STATE="$(printf '%s' "$health" | sed -n 's/.*"link": *{[^}]*"state": *"\([^"]*\)".*/\1/p' | head -n 1)"
  LINK_RUNTIME="$(printf '%s' "$health" | json_field runtime_id)"
}

do_link() {
  # Links rrotor to Glyphh; sets LINK_RESULT (linked | connecting | <state>) and LINK_RUNTIME. Fails on a refusal.
  [ -s "$INSTALL_FILE" ] || fail "This machine is not signed in to Glyphh: run /glyphh signin (or ask Claude to sign in to Glyphh), then link again."
  install_token="$(json_field token <"$INSTALL_FILE")"
  [ -n "$install_token" ] || fail "No sign-in token in $INSTALL_FILE: sign in to Glyphh again."
  auth="$(mktemp "${TMPDIR:-/tmp}/glyphh-auth.XXXXXX")"
  chmod 600 "$auth"
  printf 'Authorization: Bearer %s\n' "$install_token" >"$auth"
  issued="$(curl -sS --max-time 30 -X POST -H "@$auth" -H 'content-type: application/json' "$SERVER/v1/runtime/local" 2>&1)"
  rm -f "$auth"
  runtime_id="$(printf '%s' "$issued" | json_field runtime_id)"
  runtime_token="$(printf '%s' "$issued" | json_field token)"
  if [ -z "$runtime_id" ] || [ -z "$runtime_token" ]; then
    message="$(printf '%s' "$issued" | json_field message)"
    fail "The server issued no runtime token: ${message:-$issued}"
  fi
  body="$(mktemp "${TMPDIR:-/tmp}/rrotor-link.XXXXXX")"
  chmod 600 "$body"
  printf '{"runtime_id": "%s", "token": "%s"}' "$runtime_id" "$runtime_token" >"$body"
  handed="$(api PUT /v1/runtime/token "$body")"
  rm -f "$body"
  printf '%s' "$handed" | grep -q '"error"' && fail "rrotor refused the token: $(printf '%s' "$handed" | json_field message)"
  i=0
  LINK_RESULT=connecting
  while [ "$i" -lt 20 ]; do
    link_state
    case "$LINK_STATE" in
      online) LINK_RESULT=linked; break ;;
      connecting | backoff | no_token | follower | "") ;;
      *) LINK_RESULT="$LINK_STATE"; break ;;
    esac
    sleep 1
    i=$((i + 1))
  done
  LINK_RUNTIME="$runtime_id"
}

cmd_link() {
  [ -s "$TOKEN_FILE" ] || fail "No local token yet: install first."
  curl -fsS --max-time 2 "$(url)/healthz" >/dev/null 2>&1 || fail "rrotor is not answering at $(url): start it first."
  header_file
  do_link
  say "{\"ok\": true, \"link\": \"$(json_str "$LINK_RESULT")\", \"runtime_id\": \"$(json_str "$LINK_RUNTIME")\", \"shows\": \"the platform's Runtimes page, its apps in the organisation's catalogue, the organisation's licence key\"}"
}

cmd_status() {
  detect
  set -- $(found_state)
  up=false
  curl -fsS --max-time 2 "$(url)/healthz" >/dev/null 2>&1 && up=true
  version=""
  LINK_STATE=""
  LINK_RUNTIME=""
  if [ "$up" = true ] && [ -s "$TOKEN_FILE" ]; then
    header_file
    version="$(api GET /v1/health | json_field version)"
    link_state
  fi
  behind=false
  [ -n "$version" ] && [ "$version" != "$PINNED_VERSION" ] && [ "$(printf '%s\n%s\n' "$version" "$PINNED_VERSION" | sort -t. -k1,1n -k2,2n -k3,3n | head -n 1)" = "$version" ] && behind=true
  say "{\"ok\": true, \"runtime\": \"$KIND\", \"container\": \"$1\", \"answering\": $up, \"version\": \"$(json_str "$version")\", \"pinned\": \"$PINNED_VERSION\", \"update_available\": $behind, \"image\": \"$(json_str "$3")\", \"url\": \"$(url)\", \"link\": \"$(json_str "${LINK_STATE:-unknown}")\", \"runtime_id\": \"$(json_str "$LINK_RUNTIME")\"}"
}

# The pinned release, pulled and run on the same volume, port and token: what `install` does once the pin moved,
# with a developer's `--image` override dropped (an update is to the release). Then the link, as `start` makes it.
cmd_update() {
  detect
  set -- $(found_state)
  before=""
  if [ "$1" = running ] && [ -s "$TOKEN_FILE" ]; then
    header_file
    before="$(api GET /v1/health | json_field version)"
  fi
  IMAGE_OVERRIDE=""
  out="$(cmd_install --image pinned)" || { say "$out"; exit 1; }
  header_file
  after="$(api GET /v1/health | json_field version)"
  link=skipped
  if [ -s "$INSTALL_FILE" ]; then
    link_state
    if [ "$LINK_STATE" = no_token ]; then do_link; link="$LINK_RESULT"; else link="${LINK_STATE:-unknown}"; fi
  fi
  say "{\"ok\": true, \"from\": \"$(json_str "$before")\", \"to\": \"$(json_str "$after")\", \"image\": \"$IMAGE_REPO:$PINNED_VERSION\", \"url\": \"$(url)\", \"link\": \"$(json_str "$link")\", \"note\": \"Claude Code loads rrotor's tools again at /mcp or its next start.\"}"
}

cmd_start() {
  detect
  $CLI start "$NAME" >/dev/null 2>&1 || fail "No container $NAME: install first."
  wait_up || fail "rrotor did not answer within a minute."
  link=skipped
  if [ -s "$INSTALL_FILE" ] && [ -s "$TOKEN_FILE" ]; then
    header_file
    link_state
    if [ "$LINK_STATE" = no_token ]; then do_link; link="$LINK_RESULT"; else link="${LINK_STATE:-unknown}"; fi
  fi
  say "{\"ok\": true, \"container\": \"running\", \"url\": \"$(url)\", \"link\": \"$(json_str "$link")\"}"
}

cmd_stop() {
  detect
  $CLI stop "$NAME" >/dev/null 2>&1 || fail "No running container $NAME."
  say "{\"ok\": true, \"container\": \"stopped\"}"
}

cmd_uninstall() {
  detect
  remove_container
  purged=false
  if [ "${1:-}" = --purge ]; then
    if [ "$KIND" = container ]; then $CLI volume delete "$VOLUME" >/dev/null 2>&1 || true; else $CLI volume rm "$VOLUME" >/dev/null 2>&1 || true; fi
    rm -f "$TOKEN_FILE" "$SETTINGS"
    purged=true
  fi
  command -v claude >/dev/null 2>&1 && claude mcp remove --scope user rrotor >/dev/null 2>&1 || true
  say "{\"ok\": true, \"container\": \"removed\", \"purged\": $purged}"
}

cmd_deploy() {
  folder="${1:-}"
  commit="${2:-HEAD}"
  [ -n "$folder" ] || fail "deploy FOLDER [COMMIT]"
  [ -s "$TOKEN_FILE" ] || fail "No local token: install first."
  sha="$(git -C "$folder" rev-parse --verify "$commit^{commit}" 2>/dev/null)" || fail "$commit is not a commit in $folder: commit the program first."
  git -C "$folder" cat-file -e "$sha:glyphh.json" 2>/dev/null || fail "The commit has no glyphh.json at the folder's root."
  ref=HEAD
  git -C "$folder" merge-base --is-ancestor "$sha" HEAD 2>/dev/null || ref=--all
  work="$(mktemp -d "${TMPDIR:-/tmp}/rrotor-deploy.XXXXXX")"
  git -C "$folder" bundle create "$work/program.bundle" "$ref" >/dev/null 2>&1 || fail "git could not bundle the commit."
  { printf '{"commit": "%s", "bundle": "' "$sha"; base64 <"$work/program.bundle" | tr -d '\n'; printf '"}'; } >"$work/body.json"
  header_file
  answer="$(api POST /v1/programs/deploy "$work/body.json")"
  rm -rf "$work"
  printf '%s' "$answer" | grep -q '"error"' && fail "$answer"
  say "$answer"
}

case "${1:-}" in
  install) shift; cmd_install "$@" ;;
  connect) cmd_connect ;;
  link) cmd_link ;;
  status) cmd_status ;;
  update) cmd_update ;;
  start) cmd_start ;;
  stop) cmd_stop ;;
  uninstall) shift; cmd_uninstall "$@" ;;
  deploy) shift; cmd_deploy "$@" ;;
  mcp-command) mcp_command; printf '\n' ;;
  *) say "usage: rrotor.sh install|connect|link|update|status|start|stop|uninstall [--purge]|deploy FOLDER [COMMIT]|mcp-command"; exit 2 ;;
esac
