# rrotor with Docker

rrotor is the runtime that hosts your programs (a `glyphh.json` manifest and `program.py`, run in a sandbox, with a
local secrets vault, cron schedules, a SQLite database and approvals) and your CLIs (a kind of program, run one
command at a time in the same sandbox). Glyphh's server only grants it a licence; with none it runs as Community,
and nothing a licence does refuses a run.

The image is `ghcr.io/glyphh-ai/rrotor`. Until a glyphh-ai organisation admin makes the package public (GitHub,
the organisation's Packages, `rrotor`, Package settings, Change visibility: Public), pulling it needs `docker login
ghcr.io` with access to it. Fetch the files you need from this folder (nothing needs cloning):

```sh
curl -fsSLO https://raw.githubusercontent.com/glyphh-ai/glyphh/main/deploy/compose/<file>
```

## On your own computer

`docker-compose.local.yml`: rrotor for Claude Code on this machine, its API on `127.0.0.1:7777` only, a local token
you keep (rrotor holds only its SHA-256), the volume `glyphh-rrotor-data`. The top of the file has the four lines
that make the token, start it and add it to Claude Code. Simpler still: the glyphh plugin's `rrotor` skill does all
of it from Claude (*"install rrotor"*).

## Self-hosted, one machine

rrotor, and Caddy in front of it for HTTPS (`docker-compose.yml`, `Caddyfile`).

1. Register the runtime on the platform (https://platform.glyphh.ai, Runtimes): it gives the runtime id and token,
   shown once.
2. Point the public host's DNS at this machine, with ports 80 and 443 open to it.
3. `cp .env.example .env`, fill in `RROTOR_RUNTIME_ID`, `RROTOR_RUNTIME_TOKEN` and `RROTOR_PUBLIC_HOST`
   (`.env.example` lists every setting), and start it:

```sh
docker compose up -d
```

The runtime's connector is then at `https://<public host>/mcp`; apps call it with a runtime key. Linux hosts on
Ubuntu 23.10 or later first need `sudo sysctl -w kernel.apparmor_restrict_unprivileged_userns=0` (kept in
`/etc/sysctl.d/`), or the sandbox cannot start.

**HTTPS already in front** (your own load balancer or proxy, sending the public host to port 7777): the image alone,

```sh
docker run -d --name rrotor --restart unless-stopped \
  --security-opt seccomp=unconfined --security-opt apparmor=unconfined --security-opt systempaths=unconfined \
  --read-only --tmpfs /tmp:exec,mode=1777 -v rrotor-data:/data -p 7777:7777 \
  -e RROTOR_MODE=self -e RROTOR_RUNTIME_ID=<id> -e RROTOR_RUNTIME_TOKEN=<token> -e RROTOR_PUBLIC_HOST=rrotor.acme.com \
  ghcr.io/glyphh-ai/rrotor:0.1.0
```

**Air-gapped:** fetch `docker-compose.airgap.yml` and `Caddyfile.airgap`; put the licence key in `.env` as
`GLYPHH_LICENSE_KEY`, your certificate and key in `certs/tls.crt` and `certs/tls.key`, and start with the overlay,
which turns the link off:

```sh
docker compose -f docker-compose.yml -f docker-compose.airgap.yml up -d
```

**A cluster** (a licence key with cluster sync; `RROTOR_CLUSTER_SECRET` in `.env`, `openssl rand -base64 32`): to
try one, fetch `docker-compose.cluster.yml` and `Caddyfile.cluster`, for three nodes and Caddy balancing over them on
this machine,

```sh
docker compose -f docker-compose.cluster.yml up -d
```

For high availability, fetch `docker-compose.node.yml` on each of several machines and run it with `-f`, with
`RROTOR_NODE_ID`, `RROTOR_CLUSTER_ADVERTISE` and `RROTOR_CLUSTER_PEERS` in each `.env`, port 7778 open between them
only and your load balancer in front of port 7777.
