# Glyphh

Glyphh as it is built: the [product](#product), the [architecture](#architecture) and the [data model](#data-model), checked against the code. What is not built is in [Not built yet](#not-built-yet) and nowhere else. Plans and prices are in [pricing.md](pricing.md). How rrotor and the server talk, step by step, is in rrotor's `docs/architecture.md`; the platform's pages are in `glyphh-ai/platform`'s README.

> **Retired 2026-11-18.** Glyphh's products are wound down and Glyphh makes games now: with `GLYPHH_PRODUCTS` off, the default, the server answers `410 E_WOUND_DOWN` for everything below but what [Wound down](#wound-down-glyphh_products) lists. The rest of this page describes the products as built, which is what `GLYPHH_PRODUCTS=on` serves.

## Product

**Glyphh is a platform, a server, Ada Cloud and a local runtime.** A person signs in once on the platform (https://platform.glyphh.ai), installs rrotor on their own machine and drives it from Claude; the server grants the licence that runtime runs on.

| Part for the person | What it is | Where |
|---|---|---|
| rrotor | The runtime the person installs and drives from Claude: it hosts spec-driven programs and sandboxed CLIs, all on the person's own machine | Local, or self-hosted at `https://<host>` |
| Ada Cloud | Ada models as an API, from the person's own precedents (built, off by default: `GLYPHH_ADA_CLOUD`) | `https://ada.glyphh.ai` |
| The `glyphh` plugin | For Claude Code: the account panels and sign-in card, the Ada skill, the file ledger | `/plugin marketplace add glyphh-ai/glyphh`, `/plugin install glyphh@glyphh` |
| The SDKs | A runtime's API for an app, with a runtime key | PyPI `glyphh` 3.0.0, npm `@glyphh-ai/glyphh` 3.0.0 |

- **The server only grants licences for rrotor.** It hosts nothing and is on no program's data path: a program runs on the person's runtime and is called there. The server signs the licence and the licence key the runtime runs on, counts its nodes and keeps the runtime keys a self-hosted runtime checks.
- **Never per seat, model or install;** the tiers and the licensing strategy are in [pricing.md](pricing.md).
- **The platform is the one door.** The server renders nothing; every browser step lands on the platform. In Claude, the plugin and the Glyphh connector show the account too.
- **Glyphh has no model in it.** Claude runs on the person's own subscription; Glyphh never holds a Claude login ([Anthropic's terms](#anthropics-terms)).

## Architecture

```mermaid
flowchart TB
    subgraph Machine["The person's machine"]
        subgraph Claude["Claude, desktop or CLI"]
            Base["glyphh plugin"]
        end
        LocalRotor["rrotor, local<br/>programs and CLIs"]
        Local[("~/.glyphh<br/>install, licence")]
        Base --> Local
        Claude --> LocalRotor
    end

    Browser["A browser"]
    Callers["Claude or any app<br/>with a runtime key or a Glyphh sign-in"]
    Stripe["Stripe<br/>Checkout, portal, Billing Meter"]

    subgraph Cloud["Glyphh cloud"]
        Platform["The platform<br/>platform.glyphh.ai<br/>an OAuth client, every browser step"]
        API["The server, api.glyphh.ai<br/>accounts, billing, licences,<br/>the connector /mcp, the minute tick"]
        Ada["Ada Cloud, ada.glyphh.ai<br/>(off by default)"]
        DB[("Postgres<br/>everything kept")]
        Redis[("Redis<br/>live signals, Ada's work in flight")]
        Platform -- "OAuth, /v1" --> API
        API --- DB
        API --- Redis
        Ada --- DB
        Ada --- Redis
    end

    subgraph Own["The person's own infrastructure"]
        Self["rrotor, self-hosted<br/>REST + MCP at https://host"]
    end

    Browser --> Platform
    Base <-- "device flow, licence" --> API
    Claude -- "the Glyphh connector" --> API
    Callers -- "REST or MCP" --> Self
    LocalRotor -- "outbound link: licence and usage" --> API
    Self -- "outbound link, daily heartbeat" --> API
    API <-- "checkout, webhook, meter events" --> Stripe
```

**What a person makes stays theirs:** their programs, precedents and data, in their own rrotor. **Nothing of Glyphh's is on a program's data path:** a call goes from the caller to the person's runtime and back. The server holds who they are, what they pay for, the licence keys it signed and what a runtime says of itself to be licensed (its version, nodes, precedents and its runtime keys' use), never a program, its inputs or its results.

### The parts

| Part | What it is | Repo |
|---|---|---|
| **The platform** | The one web app, https://platform.glyphh.ai: every browser step of every flow, and the account's pages | `glyphh-ai/platform` |
| **The server** | https://api.glyphh.ai: the API and the authorization server; accounts, orgs, installs, plans and billing on Stripe, the signed licence and licence key, the runtime link, the Glyphh connector (`/mcp`), and Ada Cloud behind its own host. Renders nothing | `glyphh-ai/server` |
| **The plugin, the marketplace and the SDKs** | The `glyphh` plugin and its marketplace; the SDKs `glyphh` (PyPI) and `@glyphh-ai/glyphh` (npm), one contract with fixtures | `glyphh-ai/glyphh` (public) |
| **rrotor** | The runtime: one image (`ghcr.io/glyphh-ai/rrotor`, public), programs and sandboxed CLIs | `glyphh-ai/rrotor` |

### The platform

A confidential OAuth client of the server (tokens in a sealed HttpOnly cookie; the browser never holds one) and the pages every browser flow lands on. The server sends a browser to these routes; each reads what it needs and answers with the server call named.

| Platform route | Arrives from | Shows | Answers with |
|---|---|---|---|
| `/device` `?code=` | `GET {server}/v1/device?code=` (the link Claude shows; without a code, a field to type it) | The code to match against Claude's, Continue with each of `GET {server}/auth/providers` → `GET {server}/auth/{provider}/start?code=`; with `sso` true there too, Continue with single sign-on: the work email, then `GET {server}/auth/sso/start?code=&email=` | — |
| `/device/approve` `?consent=` | the provider's callback | `GET {server}/auth/consent?consent=` → `{kind: "device", code, name, surface, email}` | `GET {server}/auth/approve?consent=&decision=approve\|deny` |
| `/device/done` `?result=approved\|denied` | `/auth/approve` | Signed in, go back to Claude; or nothing was signed in | — |
| `/authorize` `?oauth=&client=` | `GET {server}/oauth/authorize` (a client's OAuth request, checked) | "<client> wants to use your Glyphh account", Continue with each provider → `GET {server}/auth/{provider}/start?oauth=` (single sign-on with `&email=`, as on `/device`) | — |
| `/allow` `?consent=` | the provider's callback | `GET {server}/auth/consent?consent=` → `{kind: "oauth", client, returns_to, resource, email}`: Allow or Deny | `GET {server}/auth/oauth/allow?consent=&decision=allow\|deny` (the server sends the browser on to the client) |
| `/account` `?linked=<provider>` | a provider link's callback | The account, with the provider now linked | — |
| `/github` `?installed=<login>` | the GitHub App's callback | The App is installed on that account | — |
| `/billing` `?done=1` | Stripe's checkout and portal | Billing, refreshed | — |
| `/error` `?code=&message=&trace=` | any refusal in a browser flow | The message and the trace id to quote | — |

Signing in through the platform, as any OAuth client does (the device flow takes the same provider steps, to `/device/approve` instead):

![Signing in through the platform](img/sign-in.png)

```mermaid
sequenceDiagram
    participant B as Browser
    participant C as OAuth client (the platform, Claude)
    participant G as Glyphh server
    participant P as The platform's pages
    participant I as Google or GitHub
    C->>B: to GET /oauth/authorize (PKCE S256, state, resource)
    B->>G: GET /oauth/authorize
    G-->>B: 302 to {platform}/authorize?oauth=…&client=…
    B->>P: /authorize: Continue with a provider
    B->>G: GET /auth/{provider}/start?oauth=…
    G-->>B: 302 to the provider, glyphh_signin cookie set (ten minutes)
    B->>I: sign in
    I-->>B: 302 to GET /auth/{provider}/callback
    B->>G: callback: the person found or made
    G-->>B: 302 to {platform}/allow?consent=…
    B->>P: /allow
    P->>G: GET /auth/consent (credentials, CORS for the platform)
    G-->>P: {kind: oauth, client, returns_to, resource, email}
    B->>G: GET /auth/oauth/allow?consent=…&decision=allow
    G-->>B: 302 to the client's redirect URI: code, state, iss
    B->>C: code
    C->>G: POST /oauth/token (code, code_verifier, client secret)
    G-->>C: access token (1 hour), refresh token (30 days)
```

The consent values are signed by the server and tied to the browser that started the flow by the server's short-lived cookie (`glyphh_signin`, ten minutes, on the server's domain), so the answering `GET` must be a top-level navigation from that browser. The platform reads `GET /auth/consent` from the browser itself (`credentials: include`): the server answers it with CORS for the platform's origin only (`GLYPHH_PLATFORM_URL`), with credentials. The cookie is `SameSite=Lax` when the platform and the server share a site (`platform.glyphh.ai` and `api.glyphh.ai`), and `SameSite=None; Secure` when they do not (locally, `localhost` beside a tunnel), so that read still carries it. The server always sends a person through a provider's sign-in before Allow; whether the platform skips its own choice of provider for someone already signed in is the platform's.

The platform's own pages, from the API with the session's token: Runtimes (`GET`/`POST /v1/runtimes/self`, `POST /v1/runtimes/self/{id}/token`, `DELETE /v1/runtimes/self/{id}`, `POST /v1/runtimes/{id}/offline-licence`), Keys (`GET`/`POST /v1/runtime/keys`, `DELETE /v1/runtime/keys/{id}`), Licence (`GET /v1/license/keys`, `GET /v1/license/nodes`), Billing and Usage (`GET /v1/plans`, `/v1/billing`, `POST /v1/billing/*`), Org (`GET /v1/org`, `/members`, `/invites`; Settings → Auth: `GET`/`PUT`/`DELETE /v1/org/sso`), Account (`GET`/`PATCH /v1/me`, `/v1/installs`, `POST /v1/me/identities`), and Ada at the Ada host when Ada Cloud is on.

**Single sign-on** (`ops/sso.py`, Enterprise: the plan's `sso`). An org's admin sets, on the platform's Settings → Auth, an OpenID Connect issuer (Okta, Entra ID, Google Workspace, any: `{issuer}/.well-known/openid-configuration` is read first, and a wrong one is refused with nothing kept), the client id and secret Glyphh is registered as there (the redirect URI `{server}/auth/sso/callback`; the secret sealed at rest under the server's secret key, `ops/auth/sealed.py`, never shown back), the email domains that route a sign-in to the org (a domain is one org's), and whether it is **enforced**: then Google and GitHub are refused for the org's people (`E_FORBIDDEN` `sso_required`), and single sign-on is their one way in. No SAML, no SCIM. The sign-in pages offer it when any org has it (`GET /auth/providers` says `sso`): the person gives their work email, whose domain names the org; `/auth/sso/start` sends them to the org's provider as its client (the org in the signed state), `/auth/sso/callback` exchanges the code with the secret and reads who they are from the provider's userinfo endpoint (an ID token is never parsed: the exchange was over the back channel). They are found by the provider's id (`sso`, `<issuer>#<subject>`), else by email, and either way must be that org's (`E_FORBIDDEN` `other_org` otherwise), or new to Glyphh: then a member of that org, its open invite for them accepted. Nobody is moved between orgs, and nobody gets an org of their own, by single sign-on; the device flow, the connector's Allow and the platform's own sign-in all take it. A self-hosted rrotor sees nothing new: the token it introspects is the same Glyphh sign-in, bound to its address and to its org. Each sign-in also keeps the provider's `groups` claim on the person (`users.groups`, lower-cased, at most 200): their **roles**, beside `admin` or `member` (Google and GitHub give none), and Settings → Auth names the **reviewer groups** (`org_sso.reviewers`) whose members review the org's apps beside its admin.

**Org apps** (`docs/specs/apps.md`; `ops/catalogue.py`, `ops/apps.py`, `ops/app_views.py`). What Claude made in the session (a Claude Code artifact: a page, a dashboard, a document, a diagram, a deck, a design) is published to the org's own rrotor as an **app** (rrotor's `app_publish`), never to the server: the server keeps the **catalogue** only, one row per app per rrotor (`apps`: title, description, type, version, commit, roles, state, who submitted and reviewed it), filled from the rrotor's `deployed` message up the link (its manifest's `kind` `app`; its `type` one of `page`, `dashboard`, `doc`, `diagram`, `deck`, `design`, else `page`; `by` the publisher's Glyphh subject) as a `draft`, and reviewed here: a reviewer (the admin, or a member of a reviewer group) approves, rejects (with a reason) or retires it, each review told down the runtime's link as an `app` message and carried in every welcome, so the rrotor serves only what is approved. A person is listed the approved apps whose `roles` are empty or meet their own (`{role} ∪ groups`); reviewers see every state. The platform's Apps page and the connector's apps panel show the same cards, searched, filtered by type and paged (`GET /v1/apps`), each with Open to `{runtime_url}/apps/{name}/` (a local rrotor's `http://127.0.0.1:7777`, reachable on its own machine only). The introspection a rrotor asks for a sign-in answers `role` and `groups` too, so the rrotor checks the same roles at its door.

### The `glyphh` plugin

Its home is `glyphh-ai/glyphh` (the README there); what touches the server:

- **Sign in** by device flow (`/glyphh signin`): the link lands on the platform's `/device`, where the person signs in with Google or GitHub and approves the install. Asking Claude "sign in to Glyphh" shows a sign-in card from the plugin's own MCP server.
- **Licence:** fetched and checked (Ed25519) at start, refreshed daily ([The license](#the-license)); kept in [`~/.glyphh`](#on-the-machine-glyphh).
- **The local runtime's token:** `POST /v1/runtime/local` for the install that starts rrotor ([rrotor](#rrotor)).
- **Panels:** account, org, plan and billing, a hooks module (`hooks/hooks.json` naming `register.tsx`), behind `CLAUDE_CODE_ENABLE_FUNCTION_HOOKS` while function hooks are early access. The Ada skill and the file ledger need neither the flag nor the server.

### Panels

| Panel | Where | Kind |
|---|---|---|
| Sign in, account, org, plan, billing | The plugin | Hooks module: Claude's own elements, on desktop and CLI |
| The sign-in card, in the chat | The plugin's MCP server | MCP App |
| The account: who, plan, usage, upgrade, billing, installs, grants | The Glyphh connector ([The account panel](#the-connector)) | MCP App |

An MCP App panel is an HTML page an MCP tool returns (`text/html;profile=mcp-app`, at a `ui://` address), framed, the host's theme passed as CSS variables. Claude's frame preflights every POST; tickets stay out of URLs; a panel's `ui://` address carries its version.

### rrotor

**A person's runtimes run on their own machines: a local one per install, and any they run on their own infrastructure.** Both run the same image (`ghcr.io/glyphh-ai/rrotor`, public; `RROTOR_MODE` sets which); rrotor's `docs/architecture.md` is its home. rrotor hosts spec-driven programs and sandboxed CLIs, deploys them, keeps their secrets and runs them; none of that reaches the server.

| | Local | Self-hosted |
|---|---|---|
| Who | Every plan | Every plan, unlimited |
| Where | The person's computer, linked with an install's runtime token (`POST /v1/runtime/local`) | The person's own infrastructure (Compose, Helm or Terraform, in rrotor's `deploy/`), registered by name and address ([Self-hosted runtimes](#self-hosted-runtimes)) |
| Reached at | Its loopback API, driven from Claude | `https://<host>`, a runtime key or a Glyphh sign-in |
| Licensed by | The licence key in its `welcome` (its install's licence comes from the plugin) | The licence key and a licence (`grace_days` 14) in its `welcome` and its daily heartbeat, or an offline licence |
| Precedents | The licence key's `max_precedents` (rrotor's) | The licence key's `max_precedents` (rrotor's; its licence says unlimited) |

Every rrotor is headless, with no sign-in of its own, no Claude login, model or keys in it, one volume (`/data`), and an outbound link to the server ([The runtime link](#the-runtime-link)); a local one's token stops working when its install is signed out.

### Self-hosted runtimes

**A rrotor the person runs themselves, on the same image, linked to Glyphh like any other.** It is registered on the platform (or with the connector's `register_self_runtime`): `POST /v1/runtimes/self {name, public_url}` answers `201 {id, name, public_url, token, env}`, the token shown once and kept only as a hash, and `env` its environment filled in: `RROTOR_MODE=self`, `RROTOR_SERVER`, `RROTOR_RUNTIME_ID`, `RROTOR_RUNTIME_TOKEN`, `RROTOR_PUBLIC_HOST`. `public_url` is `https://<host>` and nothing more (no port, path, query or fragment), stored lowercased; one of Glyphh's own addresses (the server, the platform) is refused, and one person registers an address once (`E_CONFLICT`, `reason: registered`).

- **Managed from the account:** `GET /v1/runtimes/self` (`[{id, name, public_url, state, version, last_seen_at, last_heartbeat_at}]`), `POST /v1/runtimes/self/{id}/token` (a new token, `{token}`, shown once: the old one stops at once, its link is closed `4401` on whichever server process holds it, and the link's sequence numbers start again), `DELETE /v1/runtimes/self/{id}` (204: the record, its keys and nodes go, its link is closed; the runtime's own volume is untouched).
- **Runtime keys** call it at its address: `POST /v1/runtime/keys {name, runtime_id, expires_in_days?}` (or the connector's `create_runtime_key`), `runtime_id` one of the person's self-hosted runtimes (anything else `E_NOT_FOUND`), shown once (`glyphh_rk_…`), kept as a SHA-256. Their hashes reach rrotor in its `welcome` and as `keys` down the link when they change; revoking one (`DELETE /v1/runtime/keys/{id}`) is the same message. A key expires 1 to 365 days from when it is made, or never (`expires_in_days` left out); an expired key leaves the list rrotor holds: the minute tick sends `keys` for any runtime whose key expired since the last. A revoked or expired key stays in the list, dated, until the person deletes it (`DELETE /v1/runtime/keys/{id}/record`); a live key cannot be deleted, only revoked first (`E_CONFLICT`, `reason: live`). `GET /v1/runtime/keys` lists them with `calls` and `last_used_at` from rrotor's `usage`.
- **Reached at its own address:** `https://<host>/mcp` and its REST API, behind TLS its owner terminates; a Glyphh sign-in for it is an OAuth resource of this server's (below, The connector: A runtime as a resource).
- **The heartbeat:** every 24 hours, and at boot, rrotor calls `POST /v1/license/verify` with its runtime token as the bearer and `{machine, licence_id, version, active_runs}`, and from rrotor's clusters on `{node_id, cluster_id, role, precedents}` (below, The licence key): `machine` the SHA-256 (hex) of its runtime id, `:` and its machine id, `licence_id` the licence it holds (or `null`). The answer is `200 {licence, license_key}` (the licence `kind: heartbeat`, 24 hours, `grace_days: 14`; the org's newest licence key or `null`; `Cache-Control: no-store`); a local runtime's token is `E_FORBIDDEN` (`not_self`), a bad one `E_UNAUTHORIZED`, any other field `E_INVALID`. The server keeps only when it beat, the version, the runs, the machine hash, the precedents and the node. **Never kept or logged:** the caller's IP address (the server's access line for this path is dropped), and never sent: prompts, a program's inputs or outputs, anyone's data.
- **Offline, for an air-gapped runtime, on Enterprise only:** `POST /v1/runtimes/{id}/offline-licence {days}` (1 to 365; or the connector's `offline_licence`; on any other plan 403 `E_NOT_IN_PLAN`, `reason: offline`) answers `{token, expires_at}`: the licence (`kind: offline`, `grace_days: 14`) as one string, base64url (padded) of its JSON `{payload, signature}`, for `RROTOR_LICENCE` or `/data/licence.token`. rrotor checks it with the public key and no network request.
- **Grace:** a self-hosted runtime's licence counts as live until `expires_at` plus `grace_days`; rrotor keeps whichever valid licence expires last, and past the grace refuses only what needs a licensed mod.

### On the machine: `~/.glyphh`

What the plugin keeps for the server (its own files are in its README):

| Path | What |
|---|---|
| `install.json` | This install's id and token, mode 0600 |
| `license.json` | The signed licence: plan, limits, features, mods, expiry |

A runtime's own volume, `/data`, is laid out in rrotor's `docs/architecture.md`.

### The server

The `glyphh-ai/server` repo: Python 3.13, FastAPI, Pydantic v2, SQLAlchemy 2 (async) on Postgres, in Docker. Database first, then API; 100% test coverage; errors with stable codes and a trace id; small files.

- **Sign in by device flow (RFC 8628).** An install is a machine: signing in again on it reuses its install.
- **Org:** one per user; the first user is its admin and pays; members by invite.
- **Plans and billing:** flat plans on Stripe, and with Ada Cloud on its reads past a metered month on a Billing Meter ([Billing](#billing)).
- **Licences:** a short-lived signed licence per install or self-hosted runtime ([The license](#the-license)) and the licence key, one per paid period ([The licence key](#the-licence-key)). rrotor enforces the runtime nodes and precedents from its key; the server counts nodes, softly, and refuses nothing.
- **The runtime link:** rrotor's outbound WebSocket, on its own token, protocol 2. Down go the licence key and a self-hosted runtime's licence and keys; up come its node, its runtime keys' use and its precedents ([The runtime link](#the-runtime-link)). Nothing of a program.
- **The Glyphh connector:** a remote MCP server (`/mcp`) for the account, signed in with OAuth ([The connector](#the-connector)).
- **Ada Cloud** behind its own host, off by default ([Ada Cloud](#ada-cloud-built-off-glyphh_ada_cloud)).
- Redis (`GLYPHH_REDIS_URL`) holds only live signals and Ada Cloud's work in flight; Postgres holds everything kept.

### The runtime link

`/v1/runtime/link`, the WebSocket every rrotor, local or self-hosted, holds to the server (`ops/link/`). JSON, one message per frame, each with `type` and `id`; rrotor's side is its `src/rrotord/link/protocol.py`.

- **Its token** in the `Authorization: Bearer` header; one that is not good, or a local runtime's whose install was signed out, is closed `4401` with its reason.
- **`hello` first, of protocol 3,** within 10 seconds: `{type: "hello", id, protocol: 3, version, mode: "local" | "self", runtime_id, node_id?, cluster_id?, role?}`, naming the runtime its token is. A hello of protocol 2 (a 0.2.0 rrotor) is taken too, and the link remembers it: the catalogue's messages go down that link under protocol 2's names, `artifact` for `app` and `artifacts` for `apps`, built in one place (`ops/link/protocol.py`: `NAMES`, read by `AppState.for_protocol` and `Welcome.for_protocol`; a message relayed from another process is published in protocol 3's names and said in the link's own by the process holding it). A hello of any other protocol (1 included: protocol 1 named a program `model`) is closed `4426` (`upgrade_needed`: update the rrotor); anything else, or a hello naming another runtime or mode, `4400`. A `deployed` list rrotor sends with it is the runtime's own business and is not kept. A node it names is kept in `nodes`.
- **`welcome`:** `{type: "welcome", id, accepted: true, licence, license_key, keys, apps, reviewers}`: every runtime gets the org's newest licence key (`null`: none); a local runtime no licence and no keys (its install's licence comes from the plugin); a self-hosted one its live runtime keys' SHA-256s and a licence (`kind: link`, 24 hours, `grace_days: 14`, precedents unlimited); every runtime the catalogue's rows for it (`apps: [{type: "app", id, program, version, state, roles}]`, docs/specs/apps.md) and the org's reviewer groups (`reviewers`). The runtime is then `online` (`last_seen_at` and `image_version` stamped) until the link closes, `offline` after.
- **Down the link, afterwards:** `keys` `{hashes}` when the runtime keys change (made, revoked or expired), `app` `{program, version, state, roles}` after each review of one of the runtime's apps, `ping`, `pong` and `ack`. Nothing else: no call, no deploy, no secret.
- **Up the link:** `usage` `{seq, keys: [{key_sha256, calls, last_used_at}], precedents?}`, each key's calls since the last report and the runtime's total precedents across its Ada models; applied once by its `seq` (one rising counter per runtime; a new token starts it again), so a replay after a reconnect is acked and skipped. `deployed` `{program, version, commit_sha, repo?, manifest?, by?}`: one whose manifest is an app (`kind` `app`) makes or updates its catalogue row as a draft, submitted by the Glyphh subject `by` names when they are the org's; any other deploy is acked and kept nowhere. A `result` or an `event` rrotor still sends is acked and kept nowhere, so rrotor stops owing it. `ping` is answered `pong`.
- **Every message is checked;** an unreadable one is logged and skipped and the link stays. One that cannot be recorded closes the link `1011` unacked, and rrotor replays it after it reconnects. Nothing heard for three pings (every 20 seconds) closes it `4408`; a newer link of the same runtime takes over (`4409`) here or on another process; a stopping server closes its links `1012`.
- **Which process holds which link:** in memory, and a Redis channel per runtime (`runtime:{id}`), so `keys` sent on any process reaches it, and rotating a self-hosted runtime's token or deleting it closes its link wherever it is held.

### Ada Cloud (built, off: `GLYPHH_ADA_CLOUD`)

Ada as an API inside this app, and through the connector (`docs/specs/ada-cloud.md`, its steps 2 to 6). **Off by
default:** off, no request reaches it (no host is routed to it, the connector lists none of its tools, plans show no
cloud limits), the schema step adds only the two `runtime_keys` columns, the plans' cloud columns and two empty
tables below, and the `ada` and `adajobs` process groups idle without touching Postgres or Redis.

- **Its own host.** A request whose `Host` is one of `GLYPHH_ADA_HOSTS` (`ada.glyphh.ai`) goes to the Ada app
  (`glyphh_ada/api/`), with its own paths; every other host reaches the API as before.
- **Callers.** An API key (`glyphh_ak_…`, `runtime_keys` with `scope` `cloud` and a `clearance` from 0 to 1, made by a
  signed-in person at `POST /v1/keys`) or a Glyphh sign-in (full clearance). A request may ask for less clearance,
  never more. A resolved caller is kept 10 s in the process, so a revoked key stops within that. Refusals: `E_AUTH`
  (401), `E_MODEL_MISSING` (404), the server's shape otherwise.
- **Processes and queues.** The `app` process authenticates, bounds the body (1 MB, `record_many` 5 MB, an import
  with its file in the body 5 MB of file; a string
  holding NUL is a 400), puts one message on the Redis stream `ada:sync` and waits on its reply list (10 s for reads,
  30 s for `record_many`, `create`, `delete`; then `504 E_TIMEOUT`; Redis down: `503 E_UNAVAILABLE`). Workers
  (`python -m glyphh_ada.worker --queue sync|jobs`, one single-threaded process per vCPU, numpy's BLAS held to one
  thread) read the streams `ada:sync` and `ada:jobs` as one consumer group: a message a worker took is claimed by
  another once it stops heartbeating (5 s sync, 60 s jobs), one that stopped three workers is answered `E_INTERNAL`,
  and a sync message past its deadline is dropped. Learn and calibrate are jobs: a row in the org's `jobs`, `202`, then
  `GET /v1/jobs/{id}` (its percent and `stage`, what it is doing now); `POST /v1/jobs/{id}/cancel` stops one (not
  started: at once; running: at its next step), failed `E_CANCELLED`. A running job beats in Redis; one whose worker
  is gone is failed `E_JOB_STALLED` when looked at, one that stopped three workers `E_JOB_LOST` (`glyphh_ada/jobstate.py`).
  A sync worker keeps a model read whole until its precedents change (a per-model data counter in Redis) and the
  answers of its last reads of an unchanged model (`glyphh_ada/cache.py`).
- **Storage: a schema per org.** `ada_<org id>`, made with its first model and migrated by every worker at start
  (`glyphh_ada/orgschema.py`, its own version table `ada_schema`): the server's `models`, `spec_versions`, `jobs` and
  `requests`, and the kernel's `precedents` (a partition per model, an HNSW index on its glyphs, `m` 64,
  `ef_construction` 400), `outcomes`, `meta`, `counts` (ada-private's `glyphh_postgres.PostgresStore`). Every table
  there, each partition included, has row-level security forced with a policy that **fails closed**: a row is seen or
  written only by a session whose `glyphh.org_id` is that org, so no org set means no rows (unlike the public tables'
  policies, below). A worker sets the org and a `search_path` of the schema and `public` for each message; every
  statement names the schema.
- **Writes happen once.** A write runs in one transaction with a row in `requests` keyed by the caller's
  `Idempotency-Key` or the message's id, holding its answer: a message taken again after its worker died, or a request
  sent again, is answered and not written again (the same key with another body: `409 E_IDEMPOTENCY`).
- **Reads.** The kernel's own (`glyphh_spec.Model` over the store): a model under 1,000 precedents is read whole; a
  bigger one through a shortlist of its 1,000 nearest glyphs (pgvector), re-ranked exactly. Over 100,000 precedents a
  query giving under half the roles that vote is refused, `422 E_FEW_ROLES`. A worker keeps up to 256 models (spec,
  learned weights, temperatures; never precedents) checked against a version counter in Redis and at most a minute
  old.
- **Jobs.** `learn` (weights, then the temperature) and `calibrate` read at most the newest 50,000 precedents
  (`limits.JOB_SAMPLE`); when learning changes what a stored case carries, every other precedent is restated after.
  A write that takes a model past a multiple of its `refresh_every` (precedents held) starts a `learn` job.
- **In and out.** An import is a job (`glyphh_ada/importer.py`): `POST …/imports` answers it waiting for its file and
  a one-hour signed upload link (`PUT /v1/uploads/{link}`, no key: the link is the credential, HMAC with
  `GLYPHH_SECRET_KEY`), or takes a file of up to 5 MB in its body. The file (JSON Lines; CSV with a header→role
  mapping; a model's export; `ada_sqlite`, a kernel store) is kept in the org's `files` table in 1 MB chunks (no
  volumes, no object storage), up to `GLYPHH_ADA_IMPORT_BYTES`. The job reads it twice: once to check every row and
  count the ids it would add against the org's cap (its plan version's `cloud_precedents`; refused whole unless
  `partial`), then, with the model's HNSW index dropped, recording 1,000 a transaction (bad rows named, the rest in;
  how far it got kept, so a worker that dies leaves the rest to another), then learns once and builds the index again
  (`CREATE INDEX CONCURRENTLY`, so writes go on). An `ada_sqlite` file whose glyphs are the model's goes in by the
  kernel's `Space.merge`; any other is restated. Every record is held to the cap too. An export (`POST
  …/export {format: jsonl|ada_sqlite}`) is a job whose file is fetched by a one-hour download link on the job
  (`GET /v1/downloads/{link}`): a zip of the precedents as stored, every spec version and what was learned, or a
  kernel SQLite store a self-hosted runtime opens; either imported into a model of the same spec answers the same.
- **Versions.** Every spec or settings change is a new row of `spec_versions` (who, why, the backtest it was chosen
  by). One that reads the stored cases as they are is active at once; one that changes what a case carries (seed,
  dimension, roles, declared pairs, learning levers, lexicon) is a `reencode` job writing a store of its own beside
  the live one, learning, then switching under the model's write lock (every write to its cases holds it shared)
  after copying what was written meanwhile; one that reads a role's values differently is refused (`E_SPEC_READING`).
  A version keeps the learned weights and temperatures it had when it stopped being active; making it active again
  restores them, at once or by a job that brings its store up to date. A store no version has read for 7 days is
  dropped (`E_VERSION_GONE`).
- **Ada versions** (`docs/specs/ada-cloud.md`, 12). Customers see the kernel as named versions (`ada-1-0` = kernel
  3.12.2, stable; `ada-1-1-beta` = 3.13.0), listed with their dates and release notes in
  `glyphh_ada/ada_versions.json` (`registry.py`, checked against the support policy at start: at most three kernels,
  one store format). Every version of a model records its Ada version and the exact kernel (`spec_versions.ada`,
  `kernel`; migration 4 gave every earlier one `ada-1-0`, `3.12.2`), and is answered, learned and re-encoded only by
  that kernel: the latest stable's is the venv's, every other one is installed in `/opt/ada/<kernel>`
  (`GLYPHH_ADA_KERNELS_DIR`; the Dockerfile's `scripts/ada-kernels.py`), and each worker group runs processes per
  kernel (`GLYPHH_ADA_KERNEL_WORKERS`, default 1, for the others), each importing only its own copy. Each kernel
  reads its own streams (`ada:sync:<kernel>`, `ada:jobs:<kernel>`); the latest stable's also read the front door
  (`ada:sync`, `ada:jobs`) and pass a message for another kernel's model on, unchanged. A new model gets the latest
  stable unless `ada` names another (`E_ADA_UNKNOWN`, `E_ADA_RETIRED`, `E_ADA_DEPRECATED`, `E_ADA_BETA`,
  `E_ADA_UNAVAILABLE`, each naming the latest stable); `POST …/upgrade {ada?}` is a re-encode on the target's kernel
  (`202`); a backtest candidate may name an `ada`, scored by its kernel's job worker, the job handed from kernel to
  kernel. Every Ada-host answer carries `Glyphh-Contract: 5`, and one about a model `Glyphh-Ada` (and
  `Glyphh-Ada-Notice` on a deprecated, retired or just-moved version). The latest stable's job workers move every
  model of a retired version to the latest stable, hourly (`retirement.py`). `GET /v1/ada` lists them with the org's
  models on each; the connector's `ada_releases` and `ada_upgrade`.
- **Backtests.** A job: the active version and up to ten candidates, each an in-memory model of the model's graded
  precedents minus the held-out ones (the newest `n`, or a seeded fraction), learned and calibrated, scored on the
  held-out: accuracy (decide's and the vote's), log-loss, cost by the output's costs, ask rate and accuracy where it
  did not ask, coverage, calibration error, mistakes, and the change against the active version.
- **Deletion.** A model's every store, version, job and file go at once (`DELETE /v1/models/{name}`); an org's whole
  schema is dropped in the transaction that removes the org. The managed database's backups keep them until they age
  out (Fly Managed Postgres's window).
- **Plans and metering.** Each plan version carries the org's cloud limits (`cloud_precedents`, `cloud_requests` a
  calendar month, `cloud_rps`, `cloud_overage`): Free 1,000 / 5,000 / 5, Basic 10,000 / 50,000 / 10, Pro 100,000 / 1,000,000 / 50, Team
  1,000,000 / 5,000,000 / 200, Enterprise none (by contract); never per seat, model or key. Before a call is
  enqueued (by the API or the connector alike, `glyphh_ada/api/meter.py`) the org's calls a second are held to the
  plan by a token bucket in Redis (`429 E_RATE`, `Retry-After`), and a read (`decide`, `query`, `probabilities`,
  `facts`; a decide once per output; a beam once per hop reached) is counted in Redis (`ada:req:<org>:<month>`).
  Past the month a Free org's
  reads are refused (`403 E_LIMIT` `requests`, with `used`, `max`, `plan`, `upgrade` and `resets_at`); a Pro or Team
  org's go on, and the minute tick adds the month's count to `ada_usage` and reports the reads past it to Stripe's
  `ada_requests` meter ($1 per 10,000, `GLYPHH_STRIPE_PRICE_ADA`, each report written before it is sent;
  `ada_meter_events`), giving a subscription made before it the metered price first. Checkout sells that price beside
  the plan's with Ada Cloud on.
- **A model's days.** For the platform's dashboard, each read is also counted against its model's UTC day by kind,
  in the round trip that counts it against the month, and each decide's answer by its worker once it has replied
  (decided, asked a person, how sure in tenths), each output apart (a named output's metrics end `|<output>`): one
  Redis hash per org (`ada:days:<org>`), taken whole by the minute tick into `ada_model_days` (`glyphh_ada/days.py`).
  The dashboard adds what Redis holds that the tick has not taken yet, so a read shows at once. Every read counts,
  whoever makes it (a key, the platform's sign-in, `/v1/runs`, the connector's tools); a backtest's scoring of the
  model's own held-out precedents is not a read and counts nowhere.
- **The connector.** Its `ada_*` tools (models, spec, settings, versions, activate, record, record_many, grade,
  forget, decide, query, probabilities, facts, beam, learn, calibrate, backtest, import with a one-hour upload link or
  rows inline, export with a download link, job with a wait) and `create_api_key`, `api_keys`, `revoke_api_key` call the
  workers exactly as the API does (`glyphh_ada/api/call.py`), as the person signed in with full clearance. A tool that
  waits on a worker runs after the request's transaction has ended, on short transactions of its own: an open
  transaction would hold back the database's oldest snapshot, which an import's concurrent index build waits out.
- **The kernel is private.** ada-private at a pinned commit (`uv.lock`), read at build time with a read-only deploy
  key (the build secret `ada_deploy_key`: GitHub's `ADA_DEPLOY_KEY` secret, passed to Fly's builder by CI); the image
  is pushed only to private registries.

| Call (at the Ada host) | Does |
|---|---|
| `GET`, `POST /v1/keys`, `DELETE /v1/keys/{id}` | API keys, signed in only: `{name, expires_in_days?, clearance?}`, shown once; `DELETE` revokes |
| `DELETE /v1/keys/{id}/forever` | Deletes a revoked or expired key for good (204); a live key is refused, 409 `E_CONFLICT`: revoke it first |
| `GET`, `POST /v1/models`, `GET /v1/models/{name}`, `DELETE /v1/models/{name}?confirm=<name>` | The org's models: `{name, spec}` (checked by the kernel, then the cloud's bounds: spec 64 KB, `dimension` 8,192, 64 roles, 20 outputs, 200 values, `k` 200) |
| `POST /v1/models/{name}/record`, `/record_many` (1,000 cases, all or none), `/grade`; `DELETE …/precedents/{id}` | Writes, each taking an `Idempotency-Key` |
| `POST /v1/models/{name}/query`, `/probabilities`, `/facts` (`top` 50), `/decide` (`outputs`, `include: ["facts"]`) | The kernel's answers; `clearance` lower than the key's |
| `POST /v1/decide` `{model, data, …}` | `{outcome, probabilities, expected_cost, ask, receipts, model, version}` |
| `POST /v1/beam` `{start, hops: [{model, role, fixed?, output?}], width?, values?, miss?, clearance?}` | Beam search across models, one model's outcome the next one's question, computed over each hop's probabilities (`glyphh_ada/beam.py`): `{outcome, p, ends, paths, lost, hops: [{model, version}], ada}`; 32 hops at most, each one read |
| `POST /v1/models/{name}/learn`, `/calibrate`; `GET /v1/jobs/{id}`; `POST /v1/jobs/{id}/cancel` | Jobs |
| `POST /v1/models/{name}/imports` `{format, mapping?, partial?, learn?, content?, content_base64?}`; `GET …/imports/{id}`; `PUT /v1/uploads/{link}` | An import: the job and its upload link, or the file in the body (5 MB) |
| `POST /v1/models/{name}/export` `{format}`; `GET /v1/downloads/{link}` | An export: the job, then its download link |
| `PUT /v1/models/{name}/spec` `{spec, note?, backtest?}`; `GET`, `PATCH …/settings` `{changes, note?, backtest?}` | A new version: `{version, active, job}` |
| `GET /v1/models/{name}/versions`; `POST …/versions/{n}/activate` | Versions (each with what changed against the one before, the precedents when made, what it had learned, its newest backtest scores and its store: `active`, `kept` with `drop_after`, `making`, `dropped`); making one active again (a rollback) |
| `GET /v1/models/{name}/versions/{n}`; `GET …/versions/{n}/diff?against=`; `PATCH …/versions/{n}` `{note}` | One version with its whole spec and every lever; what making it active would change from another (the active one by default): `{path, from, to, restates}` each; its note written again |
| `POST /v1/models/{name}/backtest` `{candidates, holdout?, output?, clearance?}` | Candidates scored on held-out precedents, as a job |
| `POST /v1/runs` `{model, function, inputs, clearance?}` | rrotor's call shape for SDK 3.0: `record`, `query`, `facts`, `probabilities`, `decide`, `learn` (waits up to 60 s), `settings`, answered as a `done` Result; `GET /v1/runs/{id}` and `…/continue` are `E_RUN_MISSING` |
| `GET /v1/usage` | `{plan, month, resets_at, models, precedents: {used, max}, requests: {used, max, over, overage}, requests_per_second}`: the org's models, the precedents they hold and its reads this month against its plan (`max` null: by contract; `over`: reads past the month, metered when `overage`) |
| `GET /v1/models/{name}/stats?days=` (30; 90 at most) | A model's dashboard: its active version, precedents by outcome (each output's 50 most common, `others` the rest together), precedents by the cases' days, latest jobs, the org's precedents against the plan's, and every one of its last days (UTC; those before it was made empty): reads by kind, decides answered, how many asked, `sure`, the decides by how sure in tenths, and `answers`, the same for each output apart. Past 100,000 precedents the outcomes and days are estimated from a sample (`estimated`), so a look stays cheap. Not a read |
| `GET /v1/models/{name}/map?limit=&layer=` (2,000 at most) | Its 3D view: a sample of its precedents, each `{id, outcome, outcomes, bits}` (the glyph packed, base64; a layer's when `layer`), and `edges` `[i, j, sim]`, each one's 10 nearest in the sample by Jaccard similarity. Not a read |
| `GET /v1/models/{name}/precedents/{id}` | One precedent: its case cut to the caller's clearance, outcomes, author and time. Not a read |
| `GET /v1/health` | As on the API |

**The platform** calls the Ada host server-side with the OAuth access token its session holds (a Glyphh sign-in,
full clearance), as it calls the account API; it shows Ada when the account API's `GET /v1/me` answers `ada_cloud:
true`.

### Wound down (`GLYPHH_PRODUCTS`)

**Glyphh's products were retired on 2026-11-18; Glyphh makes games now.** One setting, `GLYPHH_PRODUCTS`, off by default, so a fresh deploy is wound down; `on` brings everything on this page back as it is described. Nothing is deleted by the switch. Off (`api/wound_down.py`, `config.py`):

- **Every product route answers `410`** `{"error": {"code": "E_WOUND_DOWN", "message": "Glyphh's products were retired on 2026-11-18. Questions: support@glyphh.ai", "trace_id"}}`, on every host (the Ada host included): Ada Cloud, API keys, the device flow, licences and the heartbeat, runtimes and their keys, apps, templates and the memory hook, plans, checkout, the portal, the org and its invites, the connector's discovery and registration, the docs and `/openapi.json`. The answer is the same for every method and whether or not a token was sent.
- **Its own switches go with it:** `GLYPHH_ADA_CLOUD`, `GLYPHH_LLM` and `GLYPHH_RROTOR` read as off whatever they are set to, so the Ada app is not made, its two worker groups idle, and nothing meters or reports a read.
- **`/mcp` tells the truth** (`mcp/retired.py`): no token is asked for, `initialize` and `server/discover` answer with the retirement as their instructions, `tools/list` and `resources/list` are empty, and `tools/call` or `resources/read` is a JSON-RPC error `-32010` whose `data.code` is `E_WOUND_DOWN`. A client connects and sees nothing to call, rather than hanging or looping through a sign-in.
- **A runtime's link** (`/v1/runtime/link`) is accepted and closed `4401`, the code rrotor stops reconnecting on; rrotor then runs on the licence it holds, to its expiry and grace, then as Community.
- **What goes on:** `GET /v1/health`; `POST /v1/stripe/webhook`, so each cancellation and final invoice is still recorded on its org; and the staff's own way in, below.
- **Only Glyphh's staff sign in, and nobody signs up.** The platform's sign-in (`/oauth/authorize`, the Google and GitHub steps, `/auth/consent`, `/auth/oauth/allow`, `/oauth/token`, `/oauth/revoke`) stays for an email in `GLYPHH_STAFF_EMAILS`; anyone else is refused at the provider's callback with `E_WOUND_DOWN`, before an account is found or made. `/oauth/token` issues only to the platform's own client. Behind it: `GET /v1/me` and `/v1/admin/*`. A token from before that is not staff's is answered `410`; single sign-on, the device flow and linking a provider are closed.
- **The minute tick** keeps its heartbeat, the ops events and Glyphh's own sites' traffic; it no longer takes expired runtime keys off runtimes, ends Enterprise grants, flushes or meters Ada Cloud's reads, or pulls the repository's traffic. The server sends no email and never did.
- **The data** is removed by hand, apart from the switch: `scripts/wind-down/` (its README lists every table, kept or dropped), and the subscriptions by `scripts/wind-down/cancel-subscriptions.md`.

### Starting up, and migrations

The image runs the schema step before the server (`python -m glyphh_server.db.schema`), one process at a time (an advisory lock): it brings the database to `db/schema.sql`'s shape (migrations, below), runs `db/schema.sql` as it is (safe to run again), refuses to boot if a table lacks a column the code maps (the fix: the migration that was missed; a dev database can instead be made again with `docker compose down -v`), then seeds the mods (`ada`; a mod no longer seeded is retired, never deleted), the plans and their first versions (`db/seed.py`; a Stripe price a plan's newest version does not sell on becomes a new version) and the platform's OAuth client (`db/seed_clients.py`, [The connector](#the-connector)). The server then refuses to start without a `GLYPHH_SECRET_KEY` of 32 characters or more, or in `prod` without `GLYPHH_LICENSE_SIGNING_KEY`.

**Production keeps its data,** so the schema changes by migrations. `db/schema.sql` is always the latest shape; `db/migrations/NNNN_name.sql`, numbered from `0001` with no gap, each bring a database that has data one step forward, and the schema step runs the ones a database has not had, in order, each once, inside its transaction, recording each in `schema_migrations` (made if missing). A database with no tables yet is made from `db/schema.sql` and every migration recorded without running; one with tables but no record is recorded at the baseline, `tests/db/baseline.sql`, and runs them all. **The rule for a schema change:** change `db/schema.sql` and add the migration that brings an existing database to it (written to run once on real rows); `tests/db/test_migrations.py` makes one database from `db/schema.sql` and one from the baseline plus every migration and requires the same columns, constraints, indexes, policies and row-level security, and the baseline is never edited. `python -m glyphh_server.db.reset` is for development and emergencies only, run by hand with `GLYPHH_RESET_DATABASE=1`: it drops every table the server's role owns and runs the schema step again; nothing runs it on deploy.

### Settings

From the environment (prefix `GLYPHH_`, or `.env`, never committed; `config.py`). In production each is a secret or `[env]` of the Fly app `glyphh-ai-server`; a setting the server does not know is ignored.

| Setting | Default | What |
|---|---|---|
| `GLYPHH_ENV` | `dev` | `dev`, `test` or `prod` |
| `GLYPHH_PRODUCTS` | off | Glyphh's products, retired 2026-11-18 ([Wound down](#wound-down-glyphh_products)): off, every product route answers `410 E_WOUND_DOWN`, Ada Cloud, the hosted models and rrotor's tools are off whatever their own settings say, and only the health check, Stripe's webhook, a truthful `/mcp` and the staff's sign-in go on. `on`: everything as this page describes it |
| `GLYPHH_DATABASE_URL` | `postgresql+asyncpg://glyphh:glyphh@localhost:5432/glyphh` | Postgres; a plain `postgres://…?sslmode=` URL is made asyncpg's |
| `GLYPHH_RESET_DATABASE` | off | Lets `db/reset.py`, run by hand, drop every table and make the schema again (above); never set on deploy |
| `GLYPHH_REDIS_URL` | `redis://localhost:6379/0` | Redis, for live signals and, with Ada Cloud on, its work in flight (never anything kept) |
| `GLYPHH_VERSION` | `dev` | The version the API and the connector report (set by the image build) |
| `GLYPHH_LOG_LEVEL` | `INFO` | The JSON logs' level |
| `GLYPHH_PUBLIC_URL` | `http://localhost:8080` | The server's own address: the issuer, the connector's resource, the provider callbacks |
| `GLYPHH_PLATFORM_URL` | `http://localhost:3000` | The platform: every browser step is sent there; the one origin `GET /auth/consent` answers with CORS |
| `GLYPHH_PLATFORM_CLIENT_ID`, `_SECRET` | none | The platform's own OAuth client (the platform's `PLATFORM_CLIENT_ID` and `_SECRET`), made at every start |
| `GLYPHH_SECRET_KEY` | none (required) | 32+ characters, or the server refuses to start; signs every browser step's value (device sign-in, linking a provider, the connector's Allow, installing the GitHub App) and Ada Cloud's upload and download links |
| `GLYPHH_LICENSE_SIGNING_KEY` | none | Base64 of a raw 32-byte Ed25519 private key; signs every licence and licence key. Required in `prod`; elsewhere one is made at start (licences and keys then don't verify after a restart). `GLYPHH_LICENSE_KEY` is its old name, still read: to rrotor that name is the customer's key string |
| `GLYPHH_GOOGLE_CLIENT_ID`, `_SECRET`, `GLYPHH_GITHUB_CLIENT_ID`, `_SECRET` | none | Sign-in providers; one without both is not offered |
| `GLYPHH_STRIPE_SECRET_KEY`, `GLYPHH_STRIPE_WEBHOOK_SECRET` | none | Billing; without them it answers `E_UNAVAILABLE` `billing_off` |
| `GLYPHH_STRIPE_PRICE_BASIC`, `GLYPHH_STRIPE_PRICE_PRO`, `GLYPHH_STRIPE_PRICE_TEAM` | none | The flat monthly prices Basic, Pro and Team sell on; a price a plan's newest version doesn't sell on becomes a new version at the next boot |
| `GLYPHH_STRIPE_PRICE_ADA`, `GLYPHH_STRIPE_METER_ADA` | none | Ada Cloud's reads past a Basic, Pro or Team month: the metered price ($1 per 10,000) Checkout sells with Ada Cloud on (without it, `E_UNAVAILABLE`), and its meter's event name (`ada_requests`; without it nothing is reported) |
| `GLYPHH_ADA_URL` | `https://ada.glyphh.ai` | The Ada API's address in the links the connector hands out |
| `GLYPHH_GITHUB_APP_ID`, `_PRIVATE_KEY`, `_SLUG` | none | The Glyphh GitHub App: its id, its PEM key (line breaks may be written `\n`) and its slug (install page `https://github.com/apps/<slug>/installations/new`; set the App's Setup URL to `{public_url}/v1/github/callback`); without all three, `E_UNAVAILABLE` `github_off` |
| `GLYPHH_INVITE_URL` | `{public_url}/join` | Where an invite's link points |
| `GLYPHH_MCP_ORIGINS` | `https://claude.ai,https://claude.com` | Browser origins `/mcp` takes besides the server's own, comma-separated; a request with no `Origin` passes |
| `GLYPHH_CLOUDFLARE_API_TOKEN` | none | A read-only Cloudflare token (Zone Analytics) for the staff view's traffic, pulled each hour by the tick; without it the traffic view says it is not connected ([Glyphh's staff view](#glyphhs-staff-view)) |
| `GLYPHH_GITHUB_TRAFFIC_TOKEN` | none | A GitHub token that may read the repositories' traffic (fine-grained: Administration read) for the staff view's GitHub figures, pulled each hour by the tick; without it they say they are not connected |
| `GLYPHH_GITHUB_TRAFFIC_REPOS` | `glyphh-ai/glyphh` | The repositories whose traffic is pulled, owner/name, comma-separated |
| `GLYPHH_ADA_CLOUD` | off | Ada Cloud ([above](#ada-cloud-built-off-glyphh_ada_cloud)); off, nothing of it is reachable and its workers idle |
| `GLYPHH_RROTOR` | on | rrotor in the connector (shelved 2026-11-02, back on 2026-11-17): off, the connector neither lists nor calls its runtime-key, self-hosted-runtime, offline-licence and apps tools, says nothing of them in its instructions and lists no apps panel. The API's routes and the link stay as they are |
| `GLYPHH_ADA_HOSTS` | `ada.glyphh.ai` | The hosts that reach the Ada API, comma-separated (each a certificate on the app) |
| `GLYPHH_ADA_READ_TIMEOUT`, `GLYPHH_ADA_WRITE_TIMEOUT` | `10`, `30` | Seconds the API waits on a worker: a read; `record_many`, making and deleting a model, a new version |
| `GLYPHH_ADA_WORKERS` | `0` | Worker processes per machine of the `ada` and `adajobs` groups for the latest stable Ada version's kernel; 0, one per vCPU |
| `GLYPHH_ADA_KERNEL_WORKERS` | `1` | Worker processes per machine of each group for every other kernel Ada versions list (a beta, a deprecated stable) |
| `GLYPHH_ADA_KERNELS_DIR` | `/opt/ada` | Where every kernel but the latest stable's is installed, one folder per kernel |
| `GLYPHH_ADA_IMPORT_BYTES` | `209715200` | The largest file an import takes (200 MB) |
| `GLYPHH_STAFF_EMAILS` | `support@glyphh.ai` | Glyphh's staff, comma-separated verified sign-in emails: the platform opens the staff view for them ([Glyphh's staff view](#glyphhs-staff-view)) |

### API

JSON over HTTPS under `/v1`, described by `/openapi.json`. Every call but the health check, the device flow's, the plans and mods lists, the bought-once licence, the browser steps (sign-in, GitHub's pages, `/billing/done`), OAuth's own endpoints and Stripe's webhook carries an install's token or an OAuth access token (`Authorization: Bearer`); a runtime's own calls (`POST /v1/license/verify`, `POST /v1/runtime/introspect` and the link) carry its runtime token instead. The platform signs in as an OAuth client, so `/v1` takes either person's token, as the same person and org: a caller by access token has no install: `POST /v1/sign-out` ends its grant instead, no install is `current` in `GET /v1/installs`, and `POST /v1/runtime/local` refuses it (`E_INVALID` `no_install`: a local runtime belongs to an install). The server's root and `/health` answer `E_NOT_FOUND`: the health check is `/v1/health`. `/mcp` takes only an access token. The server renders no page: a browser in a flow is sent to the platform (above, The platform). Refusals are `{"error": {"code", "message", "trace_id"}}`; a limit is `E_LIMIT` with `reason` and `limit`, `used` and `max`; a feature the plan lacks is `E_NOT_IN_PLAN` with its `reason`.

| Area | Calls |
|---|---|
| Health | `GET /v1/health` (open: `{status, version, database, redis}`; Fly's check) |
| Device flow | `POST /v1/device/code` (with the plugin's `machine_id`), `POST /v1/device/token`, `GET /v1/device?code=` (to the platform's `/device`) |
| Browser steps | `GET /auth/providers` (`{providers: [google, github], sso}`), `GET /auth/{provider}/start?code=\|link=\|oauth=` (to the provider; `sso` with `&email=`, the work email whose domain names the org), `GET /auth/{provider}/callback` (to the platform's `/device/approve`, `/allow` or `/account`), `GET /auth/consent?consent=` (what a consent asks), `GET /auth/approve?consent=&decision=`, `GET /auth/oauth/allow?consent=&decision=`, `GET /billing/done` (to the platform's `/billing`); each consent signed, ten minutes, tied to the browser by the `glyphh_signin` cookie; a refusal on any of these but `/auth/providers` and `/auth/consent` (which the platform reads as JSON) goes to the platform's `/error` |
| Apps | `GET /v1/apps?q=&page=&per_page=&state=&type=` (`{apps, page, per_page, total}`: the approved ones the caller's roles allow, newest change first, 24 a page; `draft`, `rejected` and `retired` for reviewers only, `E_FORBIDDEN` `reviewer` otherwise; `type` one of `page`, `dashboard`, `doc`, `diagram`, `deck`, `design` keeps only that type, anything else `422`), `GET /v1/apps/{id}`, `POST /v1/apps/{id}/approve`, `/reject` (`{reason}`), `/retire` (a reviewer's; `E_CONFLICT` when the state does not allow it); each `{id, runtime_id, runtime_name, runtime_url, name, title, description, type, version, commit_sha, roles, state, submitted_by, submitted_at, reviewed_by, reviewed_at, reason, url}` (above, The platform) |
| Templates | `GET /v1/templates?q=`, `GET /v1/templates/{slug}`, `POST`/`DELETE /v1/templates/{slug}/install`, `POST /v1/me/glyphh/context` (`{prompt?}` → `{context}`, the plugin's hooks) ([templates.md](specs/templates.md)) |
| Account | `GET`/`PATCH /v1/me` (the org, the plan and `precedents` as in `GET /v1/billing`; `groups`, the person's roles from single sign-on, and `reviewer`), `POST /v1/me/identities` (a link that adds Google or GitHub), `DELETE /v1/me/identities/{provider}`, `GET /v1/installs`, `DELETE /v1/installs/{id}`, `POST /v1/sign-out` |
| Licences | `GET /v1/license`, `GET /v1/license/key` (below, The license), `GET /v1/license/keys` (the org's licence keys), `GET /v1/license/nodes` (its runtime nodes), `POST /v1/license/verify` (a self-hosted runtime's heartbeat, its runtime token as auth) (below, The licence key) |
| Org | `GET`/`PATCH /v1/org`, `GET /v1/org/members`, `DELETE /v1/org/members/{user_id}`, `GET`/`POST /v1/org/invites`, `DELETE /v1/org/invites/{id}`, `POST /v1/invites/accept`, `GET`/`PUT`/`DELETE /v1/org/sso` (single sign-on, above The platform: `{issuer, client_id, client_secret?, domains, enforced, reviewers?}` in, `{issuer, client_id, domains, enforced, reviewers, callback_url, updated_at}` or null out; the admin's, on Enterprise, `E_NOT_IN_PLAN` `sso` elsewhere, `E_UNAVAILABLE` `discovery` for an issuer that cannot be read, `E_CONFLICT` for a domain another org holds) |
| Mods, plans, billing | `GET /v1/mods` (each mod and the plans that include it: every one), `GET /v1/plans`, `GET /v1/billing`, `POST /v1/billing/checkout`, `/plan`, `/portal`, `POST /v1/stripe/webhook` (below, Billing) |
| Runtimes | `POST /v1/runtime/local` (a local rrotor's runtime token, for this install: made the first time, rotated after, shown once); `/v1/runtime/link` (above, The runtime link); `GET`/`POST /v1/runtimes/self`, `POST /v1/runtimes/self/{id}/token`, `DELETE /v1/runtimes/self/{id}`, `POST /v1/runtimes/{id}/offline-licence`; `GET`/`POST /v1/runtime/keys`, `DELETE /v1/runtime/keys/{id}`, `DELETE /v1/runtime/keys/{id}/record` (above, Self-hosted runtimes) |
| GitHub | `POST /v1/github/install` (a link for the browser, as linking does), `GET /v1/github/install` (to the Glyphh GitHub App's install page), `GET /v1/github/callback` (records the installation, from the browser that started it, when GitHub says it is on the person's own GitHub account), `GET /v1/github/installations` |
| Connector | `GET /.well-known/oauth-protected-resource` (and `/mcp` after it), `GET /.well-known/oauth-authorization-server`, `POST /oauth/register`, `GET /oauth/authorize`, `POST /oauth/token`, `POST /oauth/revoke`, `POST /mcp`; `GET /v1/connector/grants`, `DELETE /v1/connector/grants/{id}`; `POST /v1/runtime/introspect` (a self-hosted runtime asking about a bearer, its runtime token as auth) (below, The connector) |
| Sign-up source | `POST /v1/me/source` (the website's `glyphh_src` campaign tags, sent by the platform as a sign-in finishes: kept on the person, and on the org they made, once, within a day of the account being made; below, Glyphh's staff view) |
| Staff | `/v1/admin/*`, staff only, through the platform's sign-in, every request audited: `GET dashboard?days=`, `infra`, `alerts`, `orgs?q=&plan=&offset=&limit=`, `orgs/{id}`, `POST`/`DELETE orgs/{id}/enterprise`, `POST orgs/{id}/plan`, `POST`/`DELETE orgs/{id}/suspend`, `GET users`, `plans`, `marketing?days=`, `traffic?days=`, `ada-versions`, `audit`, `events`, `POST events/{id}/ack`, `POST events/ack` (below, Glyphh's staff view) |

### The license

`GET /v1/license` answers the caller's license (an install's; for an OAuth caller, the same with `install_id` `null`); `GET /v1/license/key` the public key (`{"alg": "Ed25519", "public_key": "<base64 of the raw 32 bytes>"}`). The plugin verifies it offline: the signature (base64) is Ed25519 over the payload's canonical JSON, the payload's keys sorted at every level, no spaces, ASCII only (Python's `json.dumps(payload, sort_keys=True, separators=(",", ":"))`, UTF-8), and the license holds until `expires_at` (24 hours; the plugin fetches a new one daily).

```json
{
  "payload": {
    "install_id": "6a1d…",
    "user_id": "0f3c…",
    "org_id": "9b2e…",
    "plan": "Pro",
    "limits": {"machines": 3},
    "features": {"sync": true, "ha": false, "offline": false, "sso": false},
    "mods": {
      "ada": {"limits": {"precedents": null}}
    },
    "expires_at": "2026-10-16T09:30:00Z"
  },
  "signature": "q8Zk…=="
}
```

A self-hosted runtime's licence (in its `welcome`, from its heartbeat, or issued offline) has `install_id` `null` and four more signed fields; an install's licence has none of them:

```json
{
  "payload": {
    "install_id": null,
    "user_id": "0f3c…",
    "org_id": "9b2e…",
    "plan": "Pro",
    "limits": {"machines": 3},
    "features": {"sync": true, "ha": false, "offline": false, "sso": false},
    "mods": {
      "ada": {"limits": {"precedents": null}}
    },
    "expires_at": "2026-10-19T09:30:00Z",
    "runtime_id": "3d8f…",
    "licence_id": "c41a…",
    "kind": "link",
    "grace_days": 14
  },
  "signature": "Xn2c…=="
}
```

- `runtime_id` is the runtime it is for; `licence_id` is new with every licence; `kind` is `link` (a welcome), `heartbeat` or `offline` (up to 365 days); `grace_days` is 14: the licence counts as live until `expires_at` plus that many days.
- `mods` names every active mod (every plan includes each); a retired mod is in no license. Ada's one limit, `precedents`, is `null` (unlimited) in every licence: the precedents per node are the licence key's `max_precedents`.
- `limits.machines` is the runtime nodes the org may have, its people's together (`null` unlimited; Free 1, Pro 3, Team 10), the licence key's `max_nodes`.
- `features` are the plan's: `sync`, `ha`, `offline`, `sso`. `offline` (offline licences) and `sso` (single sign-on) are acted on; the others are flags ([Not built yet](#not-built-yet)).

### The licence key

The key rrotor runs on (rrotor's `docs/specs/licensing.md`; [pricing.md](pricing.md#the-key)), beside the licence above. One string, `<base64url payload>.<base64url signature>`, base64url without padding; the payload UTF-8 JSON, the signature Ed25519 over the payload's **exact bytes** (no canonical form: what was signed is what is read), with `GLYPHH_LICENSE_SIGNING_KEY` (`ops/license_keys.py`). The payload, its fields in this order:

```json
{"license_id": "5f0c…", "tier": "pro", "max_nodes": 3, "max_precedents": 50000, "cluster_sync_enabled": true,
 "issued_at": "2026-10-19T14:02:11Z", "expires_at": "2026-11-19T14:02:09Z", "customer_id": "9b2e…"}
```

- **From the plan version the org is on:** `tier` the plan's name in lower case (`pro`, `team`, `enterprise`), `max_nodes` its `max_machines`, `max_precedents` its `precedents` (per node), `cluster_sync_enabled` its `sync`; `null` is unlimited. `customer_id` is the org's id (no name or address); times are RFC 3339 UTC to the second.
- **Issued** on Stripe's `checkout.session.completed` and `invoice.payment_succeeded` (the invoice's subscription on it, or under `parent.subscription_details`), once the subscription is read and synced, when it is the org's own and `active` or `trialing`: a key expiring at the paid period's end (`current_period_end`; a subscription that says none, 31 days). An Enterprise grant issues one through its last day (`plan_until`), and its deal's invoices issue that one again. The same terms to the same expiry already live are that key, not another (a checkout and its first invoice; an event delivered twice). **Free and Basic get none:** rrotor's default with no key is Community, Free's limits (rrotor has no basic tier; Basic is an Ada Cloud plan).
- **Revoked** when the subscription ends (`customer.subscription.deleted`, or any sync that finds it `canceled` or `incomplete_expired`, so a change to Free too) and when a grant is revoked or lapses: every key of the org's is marked `revoked_at` and no longer delivered. A node holding one runs it to its `expires_at` and rrotor's 14 days' grace, then Community.
- **Delivered:** `license_key`, the org's newest live key (not revoked, not expired: the latest `issued_at`, ties to the later `expires_at`, as rrotor picks), or `null`:
  - in **every** runtime's `welcome`, local and self-hosted (above, The runtime link);
  - in the **heartbeat's answer**, `200 {"licence": {…}, "license_key": "<key>" | null}`;
  - to the platform, `GET /v1/license/keys` (any member of the org): `{"license_key": "<key>" | null, "keys": [{"license_id", "tier", "max_nodes", "max_precedents", "cluster_sync_enabled", "issued_at", "expires_at", "revoked_at", "state": "live" | "expired" | "revoked", "key"}]}`, newest first, to show and copy for a node's `GLYPHH_LICENSE_KEY` or `/etc/rrotor/license.key`;
  - by the connector's `plan` and `usage`, **masked** (its first 8 and last 6 characters), with its tier and expiry.
- **The heartbeat's cluster fields** (each optional): `{"machine", "licence_id", "version", "active_runs", "node_id": "rrotor-1", "cluster_id": "<uuid>" | null, "role": "standalone" | "head" | "follower", "precedents": 1200}`; `node_id` 1 to 253 characters with no space, `precedents` ≥ 0. A `hello` may say `node_id`, `cluster_id` and `role` the same way.
- **Nodes:** each node said is kept in `nodes` by its runtime and `node_id` (its cluster, role, store's precedents, version and when it was seen); a heartbeat's `precedents` is the runtime's `precedents` too. `GET /v1/license/nodes` counts the org's runtime nodes: each node seen in the last 48 hours, and a runtime, local or self-hosted, that has said no node as one while it is linked or was heard in those 48 hours: `{"count": 4, "max_nodes": 3, "over": true, "nodes": [{"runtime_id", "runtime", "mode", "node_id", "cluster_id", "role", "precedents", "version", "seen_at"}]}`. **Soft:** shown (the platform, the connector's `usage`: "Runtime nodes: 4 of 3 (over the plan: shown, never stopped)"), never refusing; rrotor enforces `max_nodes` itself, per cluster, at join.

### Billing

A paid plan is one Stripe subscription: the plan's flat price and, with Ada Cloud on and a plan that meters its reads, Ada Cloud's metered reads' price. Writes are the admin's.

- **`GET /v1/plans`** (open): each active plan's newest version, `[{name, version, price_cents, interval, self_serve, limits: {machines, precedents}, features: {sync, ha, offline, sso}, built: {sync, ha, offline, sso}, cloud}]`; `built` says which features work today, the same on every plan (`offline` and `sso`: `BUILT` in `ops/plans.py`), so an unbuilt one is never shown as included; `interval` is `month`, `year` or `null` (Free), `price_cents` `null` for Enterprise (each contract's), `limits.machines` the runtime nodes (Free 1, Basic 1, Pro 3, Team 10, Enterprise `null`), `cloud` Ada Cloud's limits while it is on.
- **`GET /v1/billing`** (anyone in the org): `{plan (as in /v1/plans), billing_status, renews_at, plan_until, precedents: {used, limit}, cloud}`: `used` is the most any one of the org's runtimes last said it holds, `limit` the plan's precedents per node; `cloud` Ada Cloud's use while it is on. `GET /v1/me` carries the same `precedents`.
- **`POST /v1/billing/checkout` `{plan}`**: Stripe Checkout for Basic, Pro or Team (the flat price, quantity 1, and with Ada Cloud on the metered reads' price for a plan that meters them). A plan with no Stripe price here (Free, or a plan before its price is set) is `E_INVALID` `not_sold`, Enterprise `E_INVALID` `not_self_serve` ("talk to us at sales@glyphh.ai"), an unknown plan `E_INVALID`, a subscribed org `E_CONFLICT` `subscribed`, a server without Stripe, or with Ada Cloud on and no reads' price, `E_UNAVAILABLE` `billing_off`.
- **`POST /v1/billing/plan` `{plan}`**: to the newest version of another self-serve plan (a newer version of its own plan too; the same version changes nothing), prorated (the flat item's price changed, a metered item left); to Free, Ada Cloud's reads past the month are reported and the subscription cancelled now (invoiced, prorated). Not subscribed `E_CONFLICT` `not_subscribed`; an org on a plan by contract `E_CONFLICT` `contract`; Enterprise named `E_INVALID` `not_self_serve`. Answers the org.
- **`POST /v1/billing/portal`**: Stripe's portal (card, invoices, cancel); an org that never checked out is `E_CONFLICT` `no_billing`.
- **Stripe's webhook** (signed: a bad or older-than-300-seconds signature is `E_UNAUTHORIZED`) handles `checkout.session.completed`, `invoice.payment_succeeded` and `customer.subscription.created`, `.updated` and `.deleted`, and logs any other. It keeps the org true: the org found by its Stripe customer, else by `metadata.org_id` or `client_reference_id`; on every event it reads the subscription fresh and matches its flat item's price to a plan version, passing over a metered item; a payment issues the org a licence key ([The licence key](#the-licence-key)); a subscription that ended puts the org on Free (an Enterprise deal's too, its grant cleared) and revokes its keys. A subscription that is not the org's current one is passed over, so replays and events out of order change nothing; `renews_at` is empty when the subscription ends at the period's end.

**Enterprise** is granted by staff, never bought (`ops/enterprise.py`, `grant` and `revoke`: [pricing.md](pricing.md#the-control-plane)). The org's `plan_until` and deal subscription are recorded on it and a licence key issued through its last day; revoking it, or the date passing, puts the org back on Free and revokes its keys.

**The minute tick** (`ops/tend.py`), in this order: its heartbeat and the ops events logged since the last tick moved to Postgres; the runtime keys that expired taken off their runtimes (`keys` down the link); Enterprise grants past their date ended; with Ada Cloud on, its reads and its models' days taken from Redis into the database, and with Stripe its reads past a metered month reported to the `ada_requests` meter; with `GLYPHH_CLOUDFLARE_API_TOKEN`, once an hour, the traffic pulled from Cloudflare, and with `GLYPHH_GITHUB_TRAFFIC_TOKEN`, once an hour, the public repositories' traffic from GitHub ([Glyphh's staff view](#glyphhs-staff-view)). Each part runs whatever another does: one that fails is logged by its name (`tick part failed: <part>`), the rest run, and the next minute comes. Every server process runs it, and production runs more than one: each tick takes a transaction-scoped Postgres advisory lock (`pg_try_advisory_xact_lock`, `TICK` in `ops/tend.py`) in a transaction it holds for the tick, so the lock goes when the transaction ends, however it ends, and no two ticks run at once; a process that finds it held skips that minute. Every part is safe to run again.

Stripe's products, prices and meter are made once per account with `scripts/stripe-setup.py` ([pricing.md](pricing.md#the-control-plane)).

### Glyphh's staff view

**Who.** Staff are the people whose verified sign-in email is in `GLYPHH_STAFF_EMAILS` (comma-separated, default `support@glyphh.ai`; every email the server holds was verified by Google or GitHub, `ops/auth/signin.py`). `GET /v1/me` says `staff: true` for them, and the platform opens its Admin area; `/v1/admin/*` takes only the platform's own sign-in (its OAuth client, `GLYPHH_PLATFORM_CLIENT_ID`), never an install's token or a connector's. A refusal there is logged, and so an ops event (`kind` `staff`).

**The one path across orgs** (`api/admin/deps.py`): once the caller is known staff, the request's transaction leaves their org (`db/tenancy.py`), so it sees every org's rows; no other API path does, and tenants' row-level security is untouched. Every request on it is written to `admin_audit` first (who, the route's operation, path and query, which org, the outcome; an action adds what it changed), in its own transaction; one refused or failed is written apart with its code. An org's Ada schema is read by setting each org in turn (`admin/adascan.py`): model names, active versions and their Ada version and kernel, precedent counts, and jobs' kinds, states and times, never a spec, a case, a job's arguments or a file; the whole scan is kept 60 seconds in Redis. `admin_audit` and `ops_events` have a policy that shows them to no session acting for an org.

**Dashboard** (`admin/dashboard.py`, `admin/money.py`): each day's people and orgs signed up, orgs that read Ada and their reads (`ada_model_days`), models made, paid conversions (`orgs.first_paid_at`, set when a subscription is first `active`, by Stripe's webhook or an Enterprise grant); totals; MRR (paying orgs' versions' prices a month, a year's over twelve; an Enterprise contract's price is not held, so those orgs are counted apart) and the plan mix, from the database alone, never Stripe.

**Infrastructure** (`admin/infra.py`, `admin/health.py`): each Ada stream's length, what its group holds unanswered (`pending`) and not yet taken (`lag`), its group's consumers as Redis lists them (Upstash, production's Redis, lists none), and its workers alive (each worker process puts its name, scored with the time, in `ada:alive:<stream>` every 10 s, busy or not, and takes it out when it stops; alive is seen within 30 s, and the no-worker alert counts these), each kernel's stream beside the front doors; latency (`obs/metrics.py`): every request's route, status and time counted in the process and added to Redis every 5 s, per minute (kept 7 days) and per hour (8), Ada reads apart from the rest of the API, read back as p50/p95/p99 over 5 minutes, the hour and hour by hour; requests and 4xx/5xx by route; Ada jobs of the last week by kind (failures, p50/p95 seconds); Postgres's size, Ada's schemas' size, connections by state against `max_connections`, the largest tables; Redis's memory; the tick's last beat.

**Ops events** (`obs/events.py`, `obs/events_store.py`): every warning or worse a `glyphh.*` logger writes, in the API (a crash, a 5xx, a Stripe call or webhook that failed), the Ada workers (a failure, a worker that died, a job refused: `job refused: import`) and the tick (`tick part failed`), is put on a Redis list as it is logged (cut at 10,000); the tick moves it into `ops_events`, alike ones of a drain folded into one row with a count, kept 30 days. Staff list, filter and acknowledge them.

**Alerts** (`admin/alerts.py`, worked out as staff look): 5xx over 5% of the last 5 minutes' requests (20 or more), a backlog of 100 on `sync` or 20 on `jobs`, no worker alive on a front door with Ada Cloud on, the tick not begun in 5 minutes, Ada reads' p95 over 2 s, and open error events in the last hour (critical from 25).

**Staff actions**, each audited: Enterprise granted and revoked (`ops/enterprise.py`, as its command line does); a plan version changed where billing can't disagree (within the plan an org pays for, or with no subscription to a self-serve plan's; never to or from Enterprise); an org suspended (its people's tokens and the platform answer `E_FORBIDDEN` `suspended`, its connector and API keys are refused; nothing of its data changes) and lifted.

**Sign-up source** (`ops/attribution.py`): the website keeps a visitor's campaign tags (utm_*, an ad's click id, the landing page) 90 days in its first-party `glyphh_src` cookie on `.glyphh.ai`; the platform reads it as a sign-in finishes and sends it to `POST /v1/me/source`, which keeps it on a person made within the last day, and on the org they made. `GET /v1/admin/marketing` counts sign-ups, paid conversions and paying orgs by source, medium and campaign.

**Traffic** (`ops/cloudflare.py`, `ops/traffic/`, `admin/traffic.py`): with `GLYPHH_CLOUDFLARE_API_TOKEN`, the tick pulls Cloudflare's analytics once an hour (a Redis key, `traffic:pulled`, held an hour, across every process) for every zone the token sees: the last 60 days' daily totals and countries (`httpRequests1dGroups`: requests, page views, daily unique visitors, bytes, threats, cached requests); what the zone's plan lets the adaptive dataset give (`httpRequestsAdaptiveGroups`, as far back and in windows as long as its `settings` node allows: each hostname's requests and visits, its pages, its referrers, by day); and the account's Web Analytics pages and referrers when the token may read them (`rumPageloadEventsAdaptiveGroups`). Only proxied hostnames appear. What a plan or the token doesn't allow is kept on the zone (`available`, in Cloudflare's words) and shown; Cloudflare unreachable, the token refused or its rate limit stop the pull with a warning (an ops event), as does a zone's daily totals refused. Daily totals replace what was kept; the adaptive numbers keep the larger, so a day seen whole stays whole after the plan's window has passed it. `GET /v1/admin/traffic?days=` reads the tables, never Cloudflare: each zone's and hostname's days, its tops (the account's own sites left out of referrers), what its plan allowed, when it was pulled, and the last 7 and 30 days' visitors (daily uniques added up) and page views against the period before, with the people who signed up in them for a visitor-to-sign-up rate.

**GitHub traffic** (`ops/github_traffic.py`, `ops/traffic/github.py`, `admin/github_traffic.py`): with `GLYPHH_GITHUB_TRAFFIC_TOKEN`, the tick pulls each repository in `GLYPHH_GITHUB_TRAFFIC_REPOS` from GitHub's traffic API once an hour (a Redis key, `traffic:github:pulled`, held an hour): its views and clones by day (`traffic/views` and `traffic/clones`, `per=day`: count, unique visitors or cloners) and its popular referrers and paths (`traffic/popular/referrers`, `traffic/popular/paths`, 14-day totals). GitHub keeps only the last 14 days; each day is kept beyond them, replaced while GitHub still reports it, and the popular lists are kept under the day they were pulled (a later pull that day replaces them). GitHub's own 14-day totals are kept on the repository. A repository whose pull fails (GitHub unreachable, the token refused, its rate limit) is a warning (an ops event) and nothing of it is written; the others go on. `GET /v1/admin/traffic` carries it as `github`: each repository's last 14 days (GitHub's unique visitors and cloners), the same added up day by day since tracking began, its days since then (at most a year), and the latest pull's referrers and paths.

### The connector

A remote MCP server at `{public_url}/mcp`, its own OAuth 2.1 authorization server, following MCP's authorization spec (revision 2026-07-28). Through it a person manages their Glyphh account from Claude or any MCP client.

**Discovery.**

- `GET /.well-known/oauth-protected-resource` and `/.well-known/oauth-protected-resource/mcp` (RFC 9728): `resource` `{public_url}/mcp`, `authorization_servers` `[{public_url}]`, `scopes_supported` `["account"]`, `bearer_methods_supported` `["header"]`, `resource_name` `Glyphh`.
- `GET /.well-known/oauth-authorization-server` (RFC 8414): the issuer `{public_url}` and its endpoints; `response_types_supported` `["code"]`, `grant_types_supported` `["authorization_code", "refresh_token"]`, `code_challenge_methods_supported` `["S256"]`, `token_endpoint_auth_methods_supported` `["none", "client_secret_post", "client_secret_basic"]`, `scopes_supported` `["account"]`, `revocation_endpoint_auth_methods_supported` the same three, `authorization_response_iss_parameter_supported` `true` (RFC 9207).
- `/mcp` without a good token answers 401 with `WWW-Authenticate: Bearer resource_metadata="{public_url}/.well-known/oauth-protected-resource/mcp", scope="account"` (and `error="invalid_token"` when an `Authorization` header was sent); the body is the API's `E_UNAUTHORIZED`.

**A runtime as a resource.** A registered self-hosted runtime is a protected resource of its own: `resource` on `/oauth/authorize` and `/oauth/token` may be its `public_url` or that `/mcp`, looked up across every org, and the token is bound to `https://<its host>/mcp` and is no good on this server's `/mcp`. Any other address is `invalid_target`. rrotor cannot read the token: it asks `POST /v1/runtime/introspect` (`{token}`, its own runtime token as the bearer) and gets RFC 7662's shape, `{active, sub, org, scope, exp}` (`sub` the person's user id, the subject rrotor's audit log names), `active` only when the token was issued for that runtime's own address to a person of the runtime's org; `Cache-Control: no-store`, and rrotor keeps the answer a minute. A local runtime is always told `active: false`. So Claude adds a self-hosted runtime as a connector with one Allow click and no key.

**Registration.** `POST /oauth/register` (RFC 7591): `redirect_uris` (1 to 10; each `https`, or `http` on `localhost`, `127.0.0.1` or `[::1]`; a host, no fragment, up to 2,000 characters), `client_name` (up to 100 characters; left out, the first redirect URI's host), `token_endpoint_auth_method` (`none` for a public client; `client_secret_basic`, RFC 7591's default, or `client_secret_post` get a `client_secret`, shown once and kept hashed), `grant_types` within `authorization_code` and `refresh_token` (both when left out), `response_types` `["code"]`; any other metadata is ignored. It answers `201` with the `client_id` and `client_id_issued_at` (and the secret, with `client_secret_expires_at` 0). Refusals are `invalid_redirect_uri` or `invalid_client_metadata`.

**The platform's own client** is not registered: it is made at every start (`db/seed_clients.py`, in the schema step) from `GLYPHH_PLATFORM_CLIENT_ID` (a UUID: the platform's `PLATFORM_CLIENT_ID`; any other value stops the start) and `GLYPHH_PLATFORM_CLIENT_SECRET`, so a reset of the database never loses it. It is confidential (`client_secret_basic`, its secret kept hashed), named `Glyphh`, with both grant types and one redirect URI, `{GLYPHH_PLATFORM_URL}/auth/callback`; a changed secret or address takes at the next start. Without both settings, none is made. The flow treats it as any other client.

**Authorization.** `GET /oauth/authorize` with `response_type=code`, `client_id`, `redirect_uri` (exactly as registered), `state` (required), `code_challenge` and `code_challenge_method=S256` (required), `scope` (`account`, the default) and `resource` (`{public_url}/mcp` or `{public_url}`, the token bound to `{public_url}/mcp`; or a registered self-hosted runtime's address, above). An unknown client or redirect URI is `E_INVALID` and never a redirect; any other refusal goes back to the redirect URI as `error` (`unsupported_response_type`, `unauthorized_client`, `invalid_request`, `invalid_scope` or `invalid_target`), `error_description`, `state` and `iss`. The server renders nothing: a good request goes on to the platform's `/authorize?oauth=&client=` (Continue with Google or GitHub, through the same provider steps as the device sign-in, tied to the browser by the same cookie, ten minutes); the provider's callback sends the browser to the platform's `/allow?consent=`, which reads `GET /auth/consent` (`{kind: "oauth", client, returns_to, resource, email}`: the client, the redirect URI's host, the resource and the email signed in) and answers `GET /auth/oauth/allow?consent=&decision=allow|deny`. Allow redirects to the client with a `code` (single use, 2 minutes), `state` and `iss`; any other answer with `error=access_denied`.

**Tokens.** `POST /oauth/token` (form-encoded):

- Every grant: `client_id`, and the client's secret when it has one (HTTP Basic or `client_secret`, compared in constant time); an unknown client or a bad secret is `invalid_client` (401).
- `grant_type=authorization_code`: `code`, `redirect_uri`, `code_verifier` (PKCE S256, compared in constant time), and optionally `resource`, which must be one this server issues for (else `invalid_target`); the token is bound to the resource the authorization named. A code used twice revokes its grant and every token the grant holds.
- `grant_type=refresh_token`: `refresh_token`, and optionally `scope`, never wider (`invalid_scope`). The refresh token rotates on every use; a used one presented again revokes the whole grant.
- Answers `access_token` (opaque, 1 hour), `token_type` `Bearer`, `expires_in`, `refresh_token` (30 days) and `scope`, with `Cache-Control: no-store` and `Pragma: no-cache` (refusals too). Every token and code is random and kept only as a SHA-256 hash.
- `POST /oauth/revoke` (RFC 7009), the client authenticated as at the token endpoint: a refresh token revokes its grant, an access token itself; any token, unknown or another client's included, answers 200.
- These endpoints answer refusals in OAuth's own shape (`{"error": "invalid_grant", "error_description": …}`, RFC 6749 section 5.2 and RFC 7591 section 3.2.2), not the API's: OAuth clients read that shape.

The server has no rate limiting ([Not built yet](#not-built-yet)).

**Grants.** One live per person and client: allowing the same client again reuses its grant, now for the scope and resource last asked, so tokens for an earlier resource stop working. `GET /v1/connector/grants` lists the person's grants (id, client, scope, when allowed, last used to the minute, and `current` for the one calling); `DELETE /v1/connector/grants/{id}` revokes one and every token it holds (`204`; another person's is `E_NOT_FOUND`); the connector's own `revoke_grant` does the same.

**`/mcp`.** Streamable HTTP, stateless: `POST` only (`GET` and `DELETE` answer 405), each request answered with one JSON object; no sessions. It speaks MCP 2026-07-28 (each request's `_meta` carries `io.modelcontextprotocol/protocolVersion` and `clientCapabilities`, mirrored in the `MCP-Protocol-Version` and `Mcp-Method` headers, and `Mcp-Name` for `tools/call` and `resources/read`, checked against the body: a mismatch is JSON-RPC `-32020`, a version not supported `-32022` with the versions supported) and the earlier `initialize` revisions 2025-11-25, 2025-06-18 and 2025-03-26; a request naming no version is read as 2025-03-26. Its methods: `initialize` (the earlier revisions only), `ping`, `server/discover`, `tools/list`, `tools/call`, `resources/list`, `resources/templates/list` (empty) and `resources/read`; a notification answers 202. An `Origin` header other than the server's own or `GLYPHH_MCP_ORIGINS` (by default `https://claude.ai,https://claude.com`) is refused (403) before the token is read; a request with no `Origin` passes. The access token must be one the authorization server issued for `{public_url}/mcp`, its grant not revoked; the request then runs as that person, in their org (row-level security).

| Tool | Does | Who |
|---|---|---|
| `whoami` | The account, its org and role | Everyone |
| `plan` | The plan: its price, runtime nodes, precedents per node and features, billing status, when it renews, and its licence key masked | Everyone |
| `usage` | The org's runtime nodes against the plan's (soft), the precedents on its fullest runtime against the plan's per node, and its licence key masked; with Ada Cloud on, its cloud reads and precedents | Everyone |
| `plans` | What each plan costs and includes: runtime nodes, precedents per node, features | Everyone |
| `upgrade` | `plan`: Stripe Checkout's address when not subscribed; when subscribed, changes plan (prorated; Free cancels) | Admin |
| `billing_portal` | Stripe's portal address: card, invoices, cancel | Admin |
| `installs`, `sign_out_install` | The person's installs; sign one out (`install_id`) | Everyone |
| `members`, `invite` | The org's members and open invites; invite by `email` (the link, shown once) | Everyone; `invite` the admin |
| `connector_grants`, `revoke_grant` | The connector's grants; revoke one (`grant_id`) | Everyone |
| `self_runtimes`, `register_self_runtime`, `offline_licence` | The person's self-hosted runtimes (address, state, version, last heartbeat, and for Claude `mcp_url`, the address it connects to that rrotor at, `graph`, whether its release keeps the graph and the secrets form (rrotor 0.4.0 on; null while it has said no version), and `connect`: a rrotor is its own connector, so its programs, pipelines, graph and secrets form are its own tools and never go through this server); register one (`name`, `public_url`, a plain `https://<host>`; its token and environment shown once); an offline licence for one (`runtime_id`, `days` 1 to 365) | Everyone; `offline_licence` on Enterprise only |
| `runtime_keys`, `create_runtime_key`, `revoke_runtime_key` | The keys that call the person's self-hosted runtimes at their addresses; make one (`name`, `runtime_id`; `expires_in_days` 1 to 365, or never; shown once); revoke one (`key_id`) | Everyone |
| `apps`, `app_approve`, `app_reject`, `app_retire` | The org's apps as cards (`q`, `page`, `per_page`, `state`, `type`: the approved ones the caller's roles allow; drafts, rejected and retired for reviewers), shown by the apps panel; approve, reject (`reason`) or retire one (`app_id`) | Everyone; the reviews a reviewer |
| `ada_*`, `create_api_key`, `api_keys`, `revoke_api_key` | Ada Cloud's, with it on ([Ada Cloud](#ada-cloud-built-off-glyphh_ada_cloud)) | Everyone |
| `templates`, `template`, `template_install`, `template_remove`, and each installed template's `glyphh_*` | The template library and the tools a person's installed templates add to their own connector, with Ada Cloud on ([templates.md](specs/templates.md)) | Everyone |

Each result is a short text and the same as structured content; a refusal is a tool result with `isError` and the API's error (`{"error": {"code", "message", "trace_id", …}}`) as structured content, bad arguments `E_INVALID`. An unknown tool is a JSON-RPC error (`-32602`). Each call runs in a savepoint, so a refusal leaves nothing half done. Calling a program is the runtime's own MCP, never the connector's.

**The account panel.** One MCP App resource, `ui://glyphh/account/4` (`text/html;profile=mcp-app`, MCP Apps 2026-01-26), listed by `resources/list` and read by `resources/read`; `whoami`, `plan` and `usage` name it in `_meta.ui.resourceUri`. It shows who you are, the plan with its runtime nodes, precedents per node and features, the usage (the precedents on the fullest runtime), Upgrade (opens Checkout, or changes plan), Manage billing, the installs (sign one out) and the grants (revoke one); every action is a call of the connector's own tools through the host. The server advertises nothing for it, as MCP Apps says: on 2026-07-28 requests the tools carry the link only when the request's `clientCapabilities` name the `io.modelcontextprotocol/ui` extension with that mime type; on the stateless earlier revisions, where a request carries no capabilities, they always carry it, and a client without panels ignores it. Its address carries its version: a new panel is a new address. Generic styling, with the host's theme variables.

**The apps panel.** A second MCP App resource, `ui://glyphh/apps/1`, listed and read the same way; `apps`, `app_approve`, `app_reject` and `app_retire` name it. It shows the org's apps as cards (title, a type chip: Page, Dashboard, Doc, Diagram, Deck or Design; description, the rrotor's name, the version, who published it and when, the roles as chips or Everyone) with a search box, a type filter (All types and the six, sent as `type`), Previous and Next, and Open (the app's `url`, opened by the host); for a reviewer (`whoami` says `reviewer`) three tabs, Published, Awaiting review and Rejected, with Approve and Reject (a reason asked) on a draft and Retire on a published one, each a call of the connector's own tools through the host.

### Anthropic's terms

From Claude Code's legal page and the Consumer Terms (checked 2026-10-14):

- Third-party developers may not offer Claude.ai login in their apps, route requests through someone's subscription, or "collect, store, or intermediate Claude.ai credentials or session tokens"; nor pay for or resell Claude usage on their users' behalf.
- **Glyphh never touches a Claude login:** Claude runs on the person's own subscription in Anthropic's own products and calls Glyphh's tools. rrotor has no Claude in it.

## Data model

### In the cloud

```mermaid
erDiagram
    PLANS ||--|{ PLAN_VERSIONS : "has versions"
    PLAN_VERSIONS ||--o{ ORGS : "pinned by"
    ORGS ||--|{ USERS : "members"
    ORGS |o--o| USERS : "admin"
    ORGS ||--o{ INVITES : "sends"
    ORGS ||--o{ LICENSES : "issued keys"
    ORGS ||--o{ ADA_USAGE : "read, by month"
    ORGS ||--o{ ADA_MODEL_DAYS : "read, by day"
    ORGS ||--o{ ADA_METER_EVENTS : "reported"
    USERS ||--|{ IDENTITIES : "signs in with"
    USERS ||--o{ INSTALLS : "has"
    INSTALLS ||--o{ TOKENS : "holds"
    INSTALLS ||--o{ DEVICE_CODES : "approved by"
    USERS ||--o{ RROTORS : "has: one local per install, any self-hosted"
    INSTALLS ||--o| RROTORS : "local runtime"
    RROTORS ||--o{ NODES : "seen as"
    USERS ||--o{ RUNTIME_KEYS : "made"
    RROTORS |o--o{ RUNTIME_KEYS : "named by"
    USERS ||--o| GITHUB_INSTALLATIONS : "installed the App"
    USERS ||--o{ CONNECTOR_GRANTS : "allows"
    OAUTH_CLIENTS ||--o{ CONNECTOR_GRANTS : "granted to"
    OAUTH_CLIENTS ||--o{ OAUTH_CODES : "asked for"
    USERS ||--o{ OAUTH_CODES : "allowed"
    CONNECTOR_GRANTS |o--o{ OAUTH_CODES : "redeemed into"
    CONNECTOR_GRANTS ||--o{ CONNECTOR_TOKENS : "holds"
    PLAN_VERSIONS {
        uuid id PK
        uuid plan_id FK
        int version "unique per plan"
        text stripe_price_id UK
        int price_cents "null: per contract"
        text billing_interval "month, year or null"
        bool self_serve
        int max_machines "runtime nodes"
        int precedents "per node, across its models"
        bool sync
        bool ha
        bool offline
        bool sso
        int cloud_precedents
        int cloud_requests
        int cloud_rps
        bool cloud_overage
        timestamp created_at
    }
    ORGS {
        uuid id PK
        text name
        uuid plan_version_id FK
        uuid admin_user_id FK
        text stripe_customer_id UK
        text stripe_subscription_id UK
        text billing_status
        timestamp renews_at
        timestamp plan_until "an Enterprise grant's end"
        timestamp suspended_at
        text suspended_reason
        jsonb source
        timestamp first_paid_at
        timestamp created_at
    }
    RROTORS {
        uuid id PK
        uuid user_id FK
        text mode "local or self"
        uuid install_id FK "local: unique"
        text image_version
        text state
        text token_hash UK
        timestamp last_seen_at
        bigint seq "last usage applied from its link"
        text name "self"
        text public_url "self: https://host"
        timestamp last_heartbeat_at "self"
        text machine_hash "self"
        int active_runs "self"
        bigint precedents "its total, as it last said"
        timestamp precedents_at
        timestamp created_at
    }
    RUNTIME_KEYS {
        uuid id PK
        uuid rrotor_id FK "the self-hosted runtime; null for an Ada Cloud key"
        uuid user_id FK
        text name
        text key_hash UK
        timestamp created_at
        timestamp expires_at "null: never"
        timestamp revoked_at
        bigint calls
        timestamp last_used_at
        text scope "runtime or cloud"
        numeric clearance "cloud: 0 to 1"
    }
    LICENSES {
        uuid id PK "the key's license_id"
        uuid org_id FK
        text tier "free, pro, team or enterprise"
        int max_nodes "null: unlimited"
        int max_precedents "per node; null: unlimited"
        bool cluster_sync_enabled
        timestamp issued_at
        timestamp expires_at "the paid period's end"
        text customer_id "the org's id"
        timestamp revoked_at "no longer delivered"
        text key "the whole signed string"
    }
    NODES {
        uuid rrotor_id PK
        text node_id PK "the operator's own name"
        uuid cluster_id
        text role "standalone, head or follower"
        bigint precedents "its store's, as it last said"
        text version
        timestamp seen_at
    }
```

`db/schema.sql` has 30 tables; the diagram draws the account, licensing and connector ones and the columns that matter to them, and the rest are below. Timestamps carry the time zone; ids are made by the database.

- **Plan versions never change their price or limits.** Changing either adds a version with its own Stripe price; an org stays on the version it subscribed to. A change of only a plan's Ada Cloud limits is a new version too, at the same price, that takes over the version before it's Stripe price and its orgs (`db/seed.py`).
- **Mods:** every plan includes every active mod; a retired mod (`active` false) is in no license.
- **A limit left empty is unlimited.** `max_machines` is the runtime nodes the org may have, its people's together (counted, softly, in `GET /v1/license/nodes`); `precedents` what one node may hold across its Ada models (Free 5,000, Pro 50,000, Team 500,000 TBD, Enterprise unlimited). Both are signed into the licence key as `max_nodes` and `max_precedents`, `sync` as `cluster_sync_enabled`.
- **Runtimes** (`rrotors`): one local per install that started one (`mode: local`, keyed by its install), and any self-hosted ones (`mode: self`, each with its `name` and `public_url`, one per address per person, and from its heartbeat `last_heartbeat_at`, `image_version`, `active_runs` and `machine_hash`, never an address of its caller's); each its own token. `state` is `stopped` until its first link, `online` while its link is up, `offline` after; `seq` is the last `usage` sequence number applied from its link, so a replay is applied once (a new token starts it again). `precedents` is the total across its Ada models it last reported.
- **Runtime keys** (`runtime_keys`): each key the person made for one of their self-hosted runtimes (`rrotor_id`), by its SHA-256 only; `expires_at` empty for never; `calls` and `last_used_at` from rrotor's `usage`; a revoked or expired one kept, dated, until its record is deleted. A key of `scope` `cloud` is an Ada Cloud API key instead, never sent to a runtime.
- **Licences** (`licenses`): each licence key the server signed for an org, its terms as signed and the whole key string, one per paid period or Enterprise grant, never on Free; `revoked_at` once its subscription or grant ended. Row-level secure on the org.
- **Nodes** (`nodes`): each node a runtime's heartbeat or `hello` named, by its `node_id` within the runtime, as it last said; counted, never refused. Row-level secure through its runtime.
- **Installs are machines:** `INSTALLS.machine_id` is the id the plugin sends (a hash of the hardware UUID, or a random id it keeps; 16 to 128 of `A-Za-z0-9_-`), unique per user among installs not revoked. `DEVICE_CODES.machine_id` carries it to approval, which reuses that machine's install (its old tokens revoked) or makes a new one: installs are never limited.
- **One org per user;** people found by the provider's own id; installs and tokens hashed; tenant isolation by row-level security on the org.
- **GitHub installations:** the person's Glyphh GitHub App installation, recorded only when GitHub says it is on the person's own GitHub account; the server can mint a short-lived token for one of their repos from it, and keeps no long-lived GitHub key.
- **OAuth clients:** the MCP clients that registered (RFC 7591), each with its exact redirect URIs; a confidential one's secret only as a hash. They belong to no org.
- **OAuth codes:** an authorization the person allowed, until its code is redeemed (once, within 2 minutes), with its PKCE challenge and the resource it is for; `grant_id` names the grant it went into, so a second use revokes it.
- **Connector grants:** each client (the desktop, claude.ai, the platform) the person allowed to call the Glyphh connector, one live per client, revocable one by one. **Connector tokens:** its access tokens (1 hour) and refresh tokens (30 days, rotated on use; a rotated one used again revokes the grant), kept only as hashes.
- **Ada Cloud's** (`ada_usage`: an org's reads by calendar month, added by the minute tick from Redis; `ada_meter_events`: each report of reads past a metered month to Stripe, written before it is sent, `sent_at` once Stripe took it; `ada_model_days`: a model's counts by UTC day for the platform's dashboard). Row-level secure on the org.
- **Orgs:** `renews_at` is when the subscription renews, from Stripe; empty when it isn't subscribed or ends at the period's end. `plan_until` is an Enterprise grant's end. `suspended_at` and `suspended_reason` are set by staff; `source` is the sign-up's campaign tags (on `users` too); `first_paid_at` when its subscription was first active ([Glyphh's staff view](#glyphhs-staff-view)).
- **Staff** (`admin_audit`, `ops_events`): every staff request, and the server's own warnings and errors folded with a count, kept 30 days. No foreign key (an org's rows outlive it there); a session acting for an org sees none of them.
- **Traffic** (`traffic_zones`, `traffic_days`, `traffic_tops`): Glyphh's own sites' traffic from Cloudflare, pulled each hour: each zone, its plan, when it was pulled and what its plan allowed; each day's numbers by zone and hostname (`host` '' the whole zone); each day's countries, pages and referrers. Staff only.
- **GitHub traffic** (`github_traffic_repos`, `github_traffic_days`, `github_traffic_tops`): Glyphh's public repositories' traffic from GitHub, pulled each hour: each repository's last 14 days as last pulled; each day's views and clones with their unique visitors and cloners, kept beyond GitHub's 14 days; each day's pull of its popular referrers and paths. Staff only.

### Keys, checks, indexes and row-level security

Every constraint and index in `db/schema.sql`, table by table. An `ix_<table>_<column>` index is a plain index on that one column. Ids are `gen_random_uuid()`; `created_at` (and `at`, `updated_at`) default to `now()`.

| Table | Keys and checks | Foreign keys (on delete) | Indexes | Row-level security |
|---|---|---|---|---|
| `mods` | PK `slug`; `active` true, `sort` 0 by default | none | none | none |
| `plans` | PK `id`; `name` unique; `active` true, `sort` 0 by default | none | none | none |
| `plan_versions` | PK `id`; `plan_versions_version` unique (`plan_id`, `version`); `stripe_price_id` unique; `plan_versions_price` `price_cents` ≥ 0; `plan_versions_interval` `billing_interval` in `month`, `year` (or null); `plan_versions_limits` `max_machines` and `precedents` ≥ 0; `plan_versions_cloud` `cloud_precedents`, `cloud_requests` ≥ 0 and `cloud_rps` > 0 (each null: unlimited); `self_serve` true, `sync`, `ha`, `offline`, `sso`, `cloud_overage` false by default | `plan_id` → `plans` (restrict) | `ix_plan_versions_plan_id` | none |
| `orgs` | PK `id`; `stripe_customer_id` and `stripe_subscription_id` unique; `orgs_billing_status` `billing_status` in `none` (the default), `active`, `trialing`, `past_due`, `unpaid`, `canceled`, `incomplete`, `incomplete_expired`, `paused` | `plan_version_id` → `plan_versions` (restrict); `admin_user_id` → `users` (set null; `orgs_admin_user_id_fkey`, added once both tables exist) | `ix_orgs_plan_version_id` | `id` is the org |
| `users` | PK `id`; `users_role` `role` in `admin`, `member`; `groups` empty by default | `org_id` → `orgs` (restrict) | `users_email` unique on `lower(email)`; `ix_users_org_id` | `org_id` is the org |
| `identities` | PK (`provider`, `provider_user_id`); `identities_provider` `provider` in `google`, `github`, `sso` | `user_id` → `users` (cascade) | `ix_identities_user_id` | its user is visible |
| `org_sso` | PK `org_id`; `reviewers` empty by default | `org_id` → `orgs` (cascade) | none | `org_id` is the org |
| `sso_domains` | PK `domain` | `org_id` → `org_sso` (cascade) | `ix_sso_domains_org_id` | `org_id` is the org |
| `invites` | PK `id`; `token_hash` unique | `org_id` → `orgs` (cascade) | `invites_one_open` unique on (`org_id`, `lower(email)`) where `accepted_at` is null; `ix_invites_org_id` | `org_id` is the org |
| `installs` | PK `id`; `installs_surface` `surface` in `desktop`, `cli` | `user_id` → `users` (cascade) | `installs_user_machine` unique on (`user_id`, `machine_id`) where `revoked_at` is null; `ix_installs_user_id` | its user is visible |
| `tokens` | PK `id`; `token_hash` unique | `install_id` → `installs` (cascade) | `ix_tokens_install_id` | its install is visible |
| `device_codes` | PK `device_code_hash`; `user_code` unique; `device_codes_surface` `surface` in `desktop`, `cli`; `device_codes_one_answer` not both `approved_at` and `denied_at`; `interval` 5 by default | `install_id` → `installs` (cascade) | none | none: read before anyone is signed in |
| `rrotors` | PK `id`; `install_id` unique; `token_hash` unique; `rrotors_mode` `mode` in `local`, `self`; `rrotors_local_install` an install exactly when `local`; `rrotors_self_address` `public_url` and `name` exactly when `self`; `seq` 0 by default | `user_id` → `users` (cascade); `install_id` → `installs` (cascade) | `rrotors_self_url` unique on (`user_id`, `public_url`) where self; `rrotors_self_host` on `public_url` where self; `ix_rrotors_user_id` | its user is visible |
| `apps` | PK `id`; `apps_state` `state` in `draft`, `approved`, `rejected`, `retired` (`draft` by default); `apps_type` `type` in `page`, `dashboard`, `doc`, `diagram`, `deck`, `design` (`page` by default); `roles` empty by default | `org_id` → `orgs` (cascade); `runtime_id` → `rrotors` (cascade); `submitted_by`, `reviewed_by` → `users` (set null) | `apps_one_per_app` unique on (`runtime_id`, `name`); `ix_apps_org_id` | `org_id` is the org |
| `templates` | PK `slug`; `active` true, `sort` 0 by default; `body` the whole template (jsonb) | | | None: the library is everyone's |
| `template_installs` | PK `id`; `made` (the models its `make` op made) empty by default | `org_id` → `orgs` (cascade); `user_id` → `users` (cascade); `slug` → `templates` (cascade) | `template_installs_one_per_person` unique on (`user_id`, `slug`); `ix_template_installs_org_id` | `org_id` is the org |
| `runtime_keys` | PK `id`; `key_hash` unique; `calls` 0 by default; `runtime_keys_scope` `scope` in `runtime` (the default), `cloud` (an Ada Cloud API key, never sent to a runtime); `runtime_keys_clearance` `clearance` from 0 to 1 (numeric 4, 3; 1 by default) | `rrotor_id` → `rrotors` (cascade); `user_id` → `users` (cascade) | `ix_runtime_keys_rrotor_id`; `ix_runtime_keys_user_id` | its user is visible |
| `licenses` | PK `id` (the key's `license_id`); `licenses_tier` `tier` in `free`, `pro`, `team`, `enterprise`; `licenses_limits` `max_nodes` ≥ 1 and `max_precedents` ≥ 0 (or null) | `org_id` → `orgs` (cascade) | `licenses_newest` on (`org_id`, `issued_at`) | `org_id` is the org |
| `nodes` | PK (`rrotor_id`, `node_id`); `nodes_role` `role` in `standalone`, `head`, `follower` (or null) | `rrotor_id` → `rrotors` (cascade) | none beyond the key | its runtime is visible |
| `ada_usage` | PK (`org_id`, `period`); `ada_usage_requests` `requests` ≥ 0 (0 by default) | `org_id` → `orgs` (cascade) | none beyond the key | `org_id` is the org |
| `ada_model_days` | PK (`org_id`, `model`, `day`, `metric`); `n` 0 by default | `org_id` → `orgs` (cascade) | none beyond the key | `org_id` is the org |
| `ada_meter_events` | PK `id`; `ada_meter_events_requests` `requests` > 0 | `org_id` → `orgs` (cascade) | `ix_ada_meter_events_org_id` | `org_id` is the org |
| `github_installations` | PK `id`; `user_id` unique; `installation_id` unique | `user_id` → `users` (cascade) | none beyond the unique ones | its user is visible |
| `oauth_clients` | PK `id`; `oauth_clients_auth_method` `auth_method` in `none`, `client_secret_post`, `client_secret_basic`; `oauth_clients_secret` a `secret_hash` exactly when not `none`; `oauth_clients_redirect_uris` at least one | none | none | none: a client is no org's |
| `oauth_codes` | PK `code_hash` | `client_id` → `oauth_clients` (cascade); `user_id` → `users` (cascade); `grant_id` → `connector_grants` (cascade) | `ix_oauth_codes_client_id`; `ix_oauth_codes_user_id` | its user is visible |
| `connector_grants` | PK `id` | `user_id` → `users` (cascade); `client_id` → `oauth_clients` (cascade) | `connector_grants_user_client` unique on (`user_id`, `client_id`) where `revoked_at` is null; `ix_connector_grants_client_id`; `ix_connector_grants_user_id` | its user is visible |
| `connector_tokens` | PK `id`; `token_hash` unique; `connector_tokens_kind` `kind` in `access`, `refresh` | `grant_id` → `connector_grants` (cascade) | `ix_connector_tokens_grant_id` | its grant is visible |
| `admin_audit` | PK `id`; `detail` `{}` and `outcome` `ok` by default | none | `admin_audit_at` on `at`; `admin_audit_org` on (`org_id`, `at`) | `staff`: no org set only |
| `ops_events` | PK `id`; `ops_events_severity` `severity` in `warning`, `error`, `critical`; `ops_events_count` `count` > 0 (1 by default) | none | `ops_events_last` on `last_at` | `staff`: no org set only |
| `traffic_zones` | PK `name`; `available` `{}` by default | none | none beyond the key | `staff`: no org set only |
| `traffic_days` | PK (`zone`, `host`, `day`, `metric`); `n` 0 by default | none | none beyond the key | `staff`: no org set only |
| `traffic_tops` | PK (`zone`, `host`, `day`, `kind`, `key`); `n` 0 by default | none | none beyond the key | `staff`: no org set only |
| `github_traffic_repos` | PK `repo`; counts 0 by default | none | none beyond the key | `staff`: no org set only |
| `github_traffic_days` | PK (`repo`, `day`); counts 0 by default | none | none beyond the key | `staff`: no org set only |
| `github_traffic_tops` | PK (`repo`, `pulled_on`, `kind`, `key`); counts 0 by default | none | none beyond the key | `staff`: no org set only |

**Row-level security.** Each of the 17 tables marked with an org above has row-level security enabled and forced (so it binds the server's own role, which is no superuser), and one policy, `tenant`. A request made with an install's token or an OAuth access token, and a runtime's own link, heartbeat and introspection, run in their org: `glyphh.org_id` is set for the transaction (`db/tenancy.py`). With it set, `tenant` shows only that org's rows: the org itself, rows whose `org_id` is it, and rows reached through a visible parent (a user, an install, a grant or a runtime). With it unset (sign-in, the connector's OAuth endpoints, Stripe's webhook, the schema step, the minute tick's sweeps and the few operations that cross orgs on purpose, such as joining another org) every row is seen. The tables marked none (`mods`, `plans`, `plan_versions`, `device_codes`, `oauth_clients`) belong to no org; the 8 marked `staff` are seen only with no org set.

**Ada Cloud's org schemas** (`ada_<org id>`, with the flag on) are outside `db/schema.sql`: made and migrated by
the workers, every table fenced by a `tenant` policy that fails closed ([Ada Cloud](#ada-cloud-built-off-glyphh_ada_cloud)).
`tests/ada/test_isolation.py` proves two orgs see none of each other's rows through their keys, a worker's message or
the database itself (no org set, another org set, an org that is no one).

## Not built yet

Nothing in this section works today.

| Area | What |
|---|---|
| What the paid tiers are sold on | Centralised precedent-store sync across instances (`sync`), multi-node HA (`ha`), SAML and SCIM (single sign-on by OpenID Connect is built: above, The platform), RBAC, audit logs: only the licence's flags ship |
| The licensing engine | rrotor's side of the key (its start, its three enforcement modules) and the key in Stripe's receipt email; the server signs, issues, revokes and delivers keys (above, The licence key). How the rest differs is [pricing.md](pricing.md#against-what-is-built) |
| The local runtime from the plugin | The server issues its token (`POST /v1/runtime/local`) and takes its link, and the plugin links it (`/glyphh link`, the Account section's **link**, the rrotor skill's `connect` and `start`: the token handed to rrotor's `PUT /v1/runtime/token`); the rrotor skill installs and starts it on macOS and Linux with Docker or OrbStack. Not built: Windows (WSL2) and Podman |
| Air-gapped sign-in | An air-gapped runtime takes runtime keys only (`RROTOR_KEYS_SHA256`); no Glyphh sign-in without the link |
| Rate limiting | None anywhere, the OAuth endpoints included |
| OAuth client ID metadata documents | Registration is RFC 7591 only |
| Ada Cloud past its step 6 | Behind the flag, not built: an org-wide export, a page to delete an org's Ada data alone, Enterprise's cloud numbers per contract (its plan has none: unlimited); `docs/specs/ada-cloud.md` section 10 |

**Open**

- Team's precedents per node (500,000): a placeholder marked TBD in `db/seed.py`.
