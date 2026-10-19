# Glyphh

Glyphh as it is built: the [product](#product), the [architecture](#architecture) and the [data model](#data-model), checked against the code. What is not built is in [Not built yet](#not-built-yet) and nowhere else. Plans and prices are in [pricing.md](pricing.md). How rrotor and the server talk, step by step, is in rrotor's `docs/architecture.md`; the platform's pages are in `glyphh-ai/platform`'s README.

## Product

**Glyphh is a platform, a server and runtimes.** A person signs in once on the platform (https://platform.glyphh.ai), has runtimes where their Ada models live and run, and connects Claude to a runtime once.

| Part for the person | What it is | Where |
|---|---|---|
| Ada | Ada models: a typed spec and a precedent store, deployed by commit, run in the person's own runtime (**rrotor**), called by Claude and by any app at the runtime's address | Self-hosted at `https://<host>` (every plan), or hosted at `https://<machine>.glyphh.app` (Pro, Team, Enterprise; off by default: `GLYPHH_HOSTING`) |
| The `glyphh` plugin | For Claude Code: the account panels and sign-in card, the Ada skill, the file ledger | `/plugin marketplace add glyphh-ai/glyphh`, `/plugin install glyphh@glyphh` |
| The SDKs | A runtime's API for an app, with a runtime key | PyPI `glyphh` 3.0.0, npm `@glyphh-ai/glyphh` 3.0.0 |

- **Ada is in every plan.** Never per seat, model or install; the tiers and the licensing strategy are in [pricing.md](pricing.md). Glyphh-run hosting is built and switched off (`GLYPHH_HOSTING`, below, [Machines](#machines)).
- **The platform is the one door.** The server renders nothing; every browser step lands on the platform. In Claude, the plugin and the Glyphh connector show the account too.
- **Glyphh has no model in it.** Claude runs on the person's own subscription; Glyphh never holds a Claude login ([Anthropic's terms](#anthropics-terms)).

## Architecture

![The whole system](img/architecture.png)

```mermaid
flowchart TB
    subgraph Machine["The person's machine"]
        subgraph Claude["Claude, desktop or CLI"]
            Base["glyphh plugin"]
        end
        LocalRotor["rrotor, local<br/>loopback API"]
        Local[("~/.glyphh<br/>install, licence")]
        Base --> Local
    end

    Browser["A browser"]
    Callers["Claude, routines or any app<br/>with a runtime key or a Glyphh sign-in"]
    Stripe["Stripe<br/>Checkout, portal, Billing Meter"]

    subgraph Cloud["Glyphh cloud"]
        Platform["The platform<br/>platform.glyphh.ai<br/>an OAuth client, every browser step"]
        API["The server, api.glyphh.ai<br/>accounts, licences, billing,<br/>the connector /mcp, provisioning,<br/>the record, the minute tick"]
        DB[("Postgres<br/>everything kept")]
        Redis[("Redis<br/>live signals")]
        Platform -- "OAuth, /v1" --> API
        API --- DB
        API --- Redis
    end

    subgraph Fly["Fly: the runtimes app, *.glyphh.app"]
        Door["doorman<br/>replays by Host"]
        Rotor["the org's rrotor machines<br/>REST + MCP"]
        Door -. "fly-replay: instance" .-> Rotor
    end

    subgraph Own["The person's own infrastructure"]
        Self["rrotor, self-hosted<br/>REST + MCP at https://host"]
    end

    Browser --> Platform
    Base <-- "device flow, licence" --> API
    Claude -- "the Glyphh connector" --> API
    Callers -- "REST or MCP" --> Fly
    Callers -- "REST or MCP" --> Self
    Rotor -- "outbound link" --> API
    LocalRotor -- "outbound link" --> API
    Self -- "outbound link, daily heartbeat" --> API
    API -- "Machines API" --> Fly
    API <-- "checkout, webhook, meter events" --> Stripe
```

**What a person makes stays theirs:** their models, precedents and data, in their own rrotor. **Nothing of Glyphh's is on the data path:** a call goes from the caller to the person's machine over Fly's proxy and back. The server holds who they are, what they pay for, and the record of their models and runs (status and seconds), never content or a result's data.

### The parts

| Part | What it is | Repo |
|---|---|---|
| **The platform** | The one web app, https://platform.glyphh.ai: every browser step of every flow, and the account's pages | `glyphh-ai/platform` |
| **The server** | https://api.glyphh.ai: the API and the authorization server; accounts, orgs, installs, the signed licence, plans and metered hosting on Stripe, the Glyphh connector (`/mcp`), provisioning, the runtime link, approvals. Renders nothing | `glyphh-ai/server` |
| **The plugin, the marketplace and the SDKs** | The `glyphh` plugin and its marketplace; the SDKs `glyphh` (PyPI) and `@glyphh-ai/glyphh` (npm), one contract with fixtures | `glyphh-ai/glyphh` (public) |
| **rrotor** | The runtime: one image (`ghcr.io/glyphh-ai/rrotor`, public), the model sandbox and runner, the Ada part | `glyphh-ai/rrotor` |

### The platform

A confidential OAuth client of the server (tokens in a sealed HttpOnly cookie; the browser never holds one) and the pages every browser flow lands on. The server sends a browser to these routes; each reads what it needs and answers with the server call named.

| Platform route | Arrives from | Shows | Answers with |
|---|---|---|---|
| `/device` `?code=` | `GET {server}/v1/device?code=` (the link Claude shows; without a code, a field to type it) | The code to match against Claude's, Continue with each of `GET {server}/auth/providers` → `GET {server}/auth/{provider}/start?code=` | — |
| `/device/approve` `?consent=` | the provider's callback | `GET {server}/auth/consent?consent=` → `{kind: "device", code, name, surface, email}` | `GET {server}/auth/approve?consent=&decision=approve\|deny` |
| `/device/done` `?result=approved\|denied` | `/auth/approve` | Signed in, go back to Claude; or nothing was signed in | — |
| `/authorize` `?oauth=&client=` | `GET {server}/oauth/authorize` (a client's OAuth request, checked) | "<client> wants to use your Glyphh account", Continue with each provider → `GET {server}/auth/{provider}/start?oauth=` | — |
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

The platform's own pages, from the API with the session's token: Home (the first machine: `GET /v1/runtime`, its address, state, time online this month; `POST /v1/runtime/start`, `/stop`), Machines (`GET`/`POST /v1/runtimes`, `POST /v1/runtimes/{id}/start`, `/stop`, `/restart`, `DELETE /v1/runtimes/{id}?confirm=<name>`), Keys (`GET`/`POST /v1/runtime/keys`, `DELETE /v1/runtime/keys/{id}`), Models (`GET /v1/models`, `DELETE /v1/models/{id}`), Billing and Usage (`GET /v1/plans`, `/v1/rates`, `/v1/billing`, `POST /v1/billing/*`), Org (`GET /v1/org`, `/members`, `/invites`), Account (`GET`/`PATCH /v1/me`, `/v1/installs`, `POST /v1/me/identities`).

### The `glyphh` plugin

Its home is `glyphh-ai/glyphh` (the README there); what touches the server:

- **Sign in** by device flow (`/glyphh signin`): the link lands on the platform's `/device`, where the person signs in with Google or GitHub and approves the install. Asking Claude "sign in to Glyphh" shows a sign-in card from the plugin's own MCP server.
- **Licence:** fetched and checked (Ed25519) at start, refreshed daily ([The license](#the-license)); kept in [`~/.glyphh`](#on-the-machine-glyphh).
- **Panels:** account, org, plan and billing, a hooks module (`hooks/hooks.json` naming `register.tsx`), behind `CLAUDE_CODE_ENABLE_FUNCTION_HOOKS` while function hooks are early access. The Ada skill and the file ledger need neither the flag nor the server.

### Panels

| Panel | Where | Kind |
|---|---|---|
| Sign in, account, org, plan, billing | The plugin | Hooks module: Claude's own elements, on desktop and CLI |
| The sign-in card, in the chat | The plugin's MCP server | MCP App |
| The account: who, plan, usage, upgrade, billing, installs, grants | The Glyphh connector ([The account panel](#the-connector)) | MCP App |

An MCP App panel is an HTML page an MCP tool returns (`text/html;profile=mcp-app`, at a `ui://` address), framed, the host's theme passed as CSS variables. Claude's frame preflights every POST; tickets stay out of URLs; a panel's `ui://` address carries its version.

### Ada models

**An Ada model is a typed spec and a precedent store; rrotor runs it; Claude or an app calls it.** Ada is a library (`glyphh_kernel.py`, `glyphh_spec.py`, `glyphh_nsm.py`; numpy only): a model is `spec.json` and a small `model.py` whose functions call the kernel (`record`, `query`, `facts`, `probabilities`, `decide`). Nothing is trained; the model learns from the precedents it records. To rrotor it is a Python package with a manifest, deployed by commit, run in the sandbox, answering with a `Result`. Nothing calls a model through the server.

**A model**, as rrotor runs one:

```python
from rrotor import Ctx, Result


def load(ctx: Ctx) -> None: ...  # once per run: read config, open the store
def start(ctx: Ctx, inputs: dict) -> Result: ...  # the main job
def decide(ctx: Ctx, case: dict) -> Result: ...  # custom functions, each callable on its own
def end(ctx: Ctx) -> None: ...  # always runs: close up, keep results
```

- **Every call returns a `Result`:** a status and data. The status tells the caller what is next:

| `status` | Means | Claude does |
|---|---|---|
| `done` | Here is the result: data, a file, a link | Uses it, or finishes |
| `needs_input` | A value is missing, or a choice: "pick A, B or C" | Answers, then `continue` |
| `needs_approval` | About to act: "record this" | Asks the person; unattended, leaves it waiting for them |
| `failed` | Which step and why | Retries, tries another way, or reports |

- **`ctx` is what the model was granted**, nothing else (`ctx.http` only to the hosts its manifest declares, none for an Ada model; its own databases, secrets, files, log and checkpoints); it sees only its own folders. The manifest declares its functions, hosts, secrets, databases, parts and the steps that need approval. Details: rrotor's `docs/architecture.md`.
- **A model lives in the runtime and in git:** each is a repo in the person's own GitHub account; a version is a commit. The server keeps only an index (name, repo, versions as commit SHAs, where each is deployed) and the run records. Glyphh's cloud never keeps a copy of the code or the precedents.
- **Git is required for hosted models:** the person installs the Glyphh GitHub App on their account (built); deploying pins a commit, and the hosted rrotor fetches exactly that commit with a short-lived token the App issues for that repo. Local-only use needs no GitHub.
- **A redeploy that changes the encoding** (the spec's `seed`, `dim`, `encoding` or `spec_id`) re-encodes the store from its recorded facts before the new version is active, or refuses the deploy (`E_ADA_ENCODING`) when the old facts cannot be read by the new spec.
- **`clearance`** comes from the caller's Glyphh identity (the run's caller, the person's plan and org role), passed in the call and never from the inputs, so a model's facts are filtered by who asks.
- **Secrets are never committed:** they stay in rrotor's vault.

**Calling it.** Claude adds the runtime as a connector (`https://<machine>.glyphh.app/mcp` or `https://<host>/mcp`, with one Allow click or a runtime key) and, guided by the plugin's Ada skill, writes the spec and functions, deploys by commit and calls the model (`model_call`, then `model_continue` as needed). Any app does the same over REST (`POST /v1/runs` at the runtime's address) with a runtime key. Machines and keys are made on the platform or with the connector's `create_runtime`, `start_runtime` and `create_runtime_key`.

A step that `needs_approval` waits for the person; the first answer to `POST /v1/approvals/{id}` wins.

### rrotor

**A person's runtimes: hosted machines up to the org's plan's, any they run themselves, and a local one per install.** All run the same image (`ghcr.io/glyphh-ai/rrotor`, public; `RROTOR_MODE` sets which); rrotor's `docs/architecture.md` is its home.

| | Hosted | Self-hosted | Local |
|---|---|---|---|
| Who | Pro, Team, Enterprise, up to the plan's machines, with hosting on (off by default) | Every plan, unlimited | Every plan |
| Where | A Fly machine and its volume each, named and of a size ([Machines](#machines)) | The person's own infrastructure (Compose, Helm or Terraform, in rrotor's `deploy/`), registered by name and address ([Self-hosted runtimes](#self-hosted-runtimes)) | The person's computer, linked with an install's runtime token (`POST /v1/runtime/local`) |
| Up | Stopped after `GLYPHH_RUNTIME_IDLE_MINUTES` (10) with no run in progress or recent, and by Fly's proxy when no request comes; woken by a request to its address, or by the server for a deploy or an approval's answer | While its owner runs it; the server never starts or stops it | While the computer runs it |
| Reached at | `https://<machine>.glyphh.app`, a runtime key or a Glyphh sign-in | `https://<host>`, a runtime key or a Glyphh sign-in | Its loopback API only |
| Precedents | The plan's managed bucket | Unlimited | Unlimited |
| Billed | Per second ([Billing and hosting](#billing-and-hosting)) | Never | Never |

Every rrotor is headless, with no sign-in of its own, no Claude login, model or keys in it, one volume (`/data`), each run sandboxed (bubblewrap, Landlock, seccomp; network only to the hosts its manifest declares), and an outbound link to the server ([The server](#the-server)); a local one's token stops working when its install is signed out.

### Machines

**Hosting is off by default** (`GLYPHH_HOSTING`; `on` brings it back): no machine is made, started or restarted (`POST /v1/runtimes`, `/start`, `/restart`, `POST /v1/runtime/start`, the connector's `create_runtime`, `start_runtime` and `restart_runtime` are `E_UNAVAILABLE` `hosting_off`), no doorman is made, nothing is woken, the minute tick meters and stops nothing, and every plan shows no hosted machines. A machine made before can still be listed, stopped and deleted. What follows is the design with hosting on.

**Each hosted runtime is a machine, named and of one size.** The sizes are one table (`SIZES`, `models/rrotor.py`) that makes each machine's Fly guest and volume:

| Size | Fly guest | Memory | Volume |
|---|---|---|---|
| `small` | shared, 1 CPU | 1024 MB | 3 GB |
| `medium` | shared, 2 CPUs | 4096 MB | 10 GB |
| `large` | performance, 2 CPUs | 8192 MB | 20 GB |

- **Made and run from the account:** `GET /v1/runtimes` lists the person's machines, oldest first: `[{id, name, size, state, address, month_seconds, created_at}]` (`address` `https://<machine>.glyphh.app`, `month_seconds` its online time this month). `POST /v1/runtimes {name, size}` makes one and starts it (the app's doorman made with the first) and answers `201` the machine; past the plan's machines, the org's together, `E_LIMIT` (`reason: machines`; on Free, any), a name the person has given another `E_CONFLICT` (`reason: name`). `GET /v1/runtimes/{id}`, `POST /v1/runtimes/{id}/start`, `/stop` and `/restart` (Fly's `POST /machines/{id}/restart`; `stopped` until it links again) answer the machine. Each acts only on the caller's own machines: anyone else's is `E_NOT_FOUND`.
- **Deleting one is not undone:** `DELETE /v1/runtimes/{id}?confirm=<its name>` answers `204` and destroys the machine and its volume: every model, version, precedent and file on it. A `confirm` that is not its name is `E_INVALID` (`reason: confirm`). Nothing is backed up past Fly's daily snapshots of the volume (5 days).
- **The single-runtime routes act on the first machine** (the oldest): `GET /v1/runtime`, `POST /v1/runtime/start` (with no machine, one made: `default`, small), `/stop`, `DELETE /v1/runtime`. A deploy with no runtime named, and no local one, goes to the first machine too.
- **Keys:** a runtime key names one machine (or a self-hosted runtime) with `runtime_id`, or none: then every hosted machine of the person's holds it, those made later too, and none of their self-hosted ones.
- **Metered** per second while started, its volume always; held when past the plan ([Billing and hosting](#billing-and-hosting)).

### Reaching a runtime

**Every hosted runtime has a public address, `https://<machine>.glyphh.app`, and nothing of Glyphh's is between the caller and it.**

![Reaching a runtime](img/reach-runtime.png)

```mermaid
sequenceDiagram
    participant C as Claude or an app
    participant F as Fly proxy (*.glyphh.app)
    participant D as doorman machine
    participant R as the person's rrotor
    participant G as Glyphh server
    C->>F: POST https://3d8f….glyphh.app/v1/runs (Bearer)
    F->>D: any started machine in the app
    D-->>F: fly-replay#58; instance=3d8f… (Host says which)
    F->>R: the same request (the machine started if stopped)
    alt a runtime key
        R->>R: its SHA-256 among the keys held
    else a Glyphh sign-in
        R->>G: POST /v1/runtime/introspect {token} (its runtime token)
        G-->>R: {active, sub, org, scope, exp}, kept a minute
    end
    R-->>C: the Result, with its data
    R-)G: link#58; online, deployed, usage per key and precedents, events, each run's status (never its data)
```

- **One Fly app (`GLYPHH_FLY_APP`; in production `glyphh-ai-runtime`), a wildcard certificate `*.glyphh.app` and a wildcard DNS record.** The hostname *is* the machine id, so no lookup anywhere: a machine that gets a request for another `Host` answers `fly-replay: instance=<id>` and Fly's proxy replays it there, starting that machine if it is stopped. One small always-on **doorman** machine takes the first hop, so nobody's machine is woken to bounce someone else's request. `fly-replay` carries bodies up to 1 MB: calls, continues and MCP; a deploy goes by git through the link.
- **Auth is rrotor's:** a request carries a **runtime key** (`Authorization: Bearer`), checked against the SHA-256s rrotor holds, **or a Glyphh sign-in**: the runtime is an OAuth protected resource whose authorization server is this server (below, The connector: A runtime as a resource), and rrotor asks `POST /v1/runtime/introspect` whether the bearer is live for its own address. Keys are made from the account (`POST /v1/runtime/keys {name, expires_in_days, runtime_id}`, `runtime_id` one runtime or left out for every hosted machine of the person's; or the connector's `create_runtime_key`), shown once, and their hashes reach rrotor in its `welcome` and as `keys` down the link when they change; revoking one is the same message. **A key expires** 1 to 365 days from when it is made, or never (`expires_in_days` left out): the platform warns before making one that never expires. An expired key leaves the list rrotor holds: the server's minute tick sends `keys` for any runtime whose key expired since the last, and a `welcome` never carries one. A revoked or expired key stays in the account's list, dated, until the person deletes it (`DELETE /v1/runtime/keys/{id}/record`); a live key cannot be deleted, only revoked first (`E_CONFLICT`, `reason: live`).
- **What rrotor reports, and never more:** every minute it has calls to report, rrotor sends `usage` up the link: for each runtime key that let a request in since the last report, its SHA-256, the number of calls and when it was last used (numbered, kept in rrotor's outbox until acknowledged, so each report counts once; calls in the minute before a crash are lost). The server adds them to that key's `calls` and `last_used_at`, shown with the key (`GET /v1/runtime/keys`). `usage` also carries `precedents`, the runtime's total across its Ada models (left out until rrotor has read it; it may come with no keys): the server keeps the newest (`rrotors.precedents`, `precedents_at`), and an org's hosted runtimes' together are shown as what it uses of its plan's managed bucket; each hosted runtime's licence carries the whole bucket as its own cap. After **every** deploy, however it was asked for (the server's `deploy`, rrotor's own `POST /v1/models/deploy` or its MCP `model_deploy`), rrotor sends `deployed` with the model, version, commit, and the repo and manifest when it has them; a model or version the server has not seen is recorded then, in the person's org, so `GET /v1/models` shows every model on the runtime. Each `hello` lists the versions active on the runtime, and the server records them the same way (without repo or manifest), so models deployed before the link last went down are never missed. Never a call's inputs, outputs or the key itself.
- **The API on the machine is rrotor's own** (rrotor's `docs/architecture.md`, section 7): `POST /v1/runs` answers the first `Result` with its data, `/continue`, `/cancel`, `GET /v1/runs/{id}`, `/log`, `/approvals`, `GET /v1/models`, `POST /v1/models/deploy`. **MCP too:** `https://<machine>.glyphh.app/mcp` (Streamable HTTP, a Glyphh sign-in or the runtime key as the bearer) with `models_list`, `model_deploy`, `model_call`, `model_continue`, `run_status`, so Claude adds the runtime as a connector and talks to it directly.
- **The precedent cap is the licence's:** in `welcome` for a hosted runtime (the plan's managed precedents; rrotor refuses a `record` past the runtime's total) and a self-hosted one (unlimited); a local one's `welcome` carries no licence or keys.
- **The server's part:** provisioning (the doorman with the first runtime; each machine and its volume, of its size, its token and the public domain in its environment), keys, metering, the licence, the record of versions (`/v1/models`, by commit) and what rrotor reports up the link. Down the link go only the licence and keys (in `welcome` and as `keys`), a deploy, activate or remove of one version, and an approval's answer (`continue`); no call. Up it comes each run's `result` (the server keeps its status and seconds, never its data; a `needs_approval` becomes an approval), events, `deployed` and `usage`. For a deploy or an answer to a hosted machine that is stopped, the server starts it and waits up to 45 seconds for its link. Calling a model is the runtime's own MCP, never the [connector](#the-connector)'s.
- **Provisioning, on Fly's Machines API** (`ops/hosted.py`, `ops/fly.py`): the first machine makes the app's **doorman** (named `doorman`, `RROTOR_MODE=doorman`, a shared CPU and 256 MB, no volume, never stopped, restarted always). Each machine is a volume of its size (`data_<id>`, mounted at `/data`) and a machine (`rt-<id>`) of its size's guest, made stopped (`skip_launch`) in `GLYPHH_FLY_REGION`, then started; its environment is `RROTOR_MODE=hosted`, `RROTOR_SERVER`, `RROTOR_RUNTIME_ID`, `RROTOR_RUNTIME_TOKEN` and `RROTOR_PUBLIC_DOMAIN`, its service port 7777 behind 443 and 80, started by Fly's proxy on a request and stopped by it when idle (`autostop: stop`). A runtime's `state` is `stopped` until its first `hello`, `online` while linked, `offline` after. With hosting off, making, starting and restarting are `E_UNAVAILABLE` `hosting_off`; without Fly set up (below), every one of these routes is; a failure at Fly is `E_UNAVAILABLE` `fly_failed`, never a 500.
- **One-time on Fly:** the runtimes app, `fly certs add "*.glyphh.app"` on it, a wildcard DNS record `*.glyphh.app` to the app's IPs (DNS only in Cloudflare, not proxied), and the hosted image in Fly's registry (`registry.fly.io/<app>`, pushed by rrotor's CI). The server's `GLYPHH_FLY_*` settings name them.
- **Why no proxy of ours:** the server on the data path would couple every customer's throughput to it and make "we never see your data" a promise instead of a fact. Fly's replay routes by `Host` with no lookup, and TLS ends on Fly's proxy and nowhere else.

### Self-hosted runtimes

**A rrotor the person runs themselves, on the same image, linked to Glyphh like any other.** It is registered on the platform (or with the connector's `register_self_runtime`): `POST /v1/runtimes/self {name, public_url}` answers `201 {id, name, public_url, token, env}`, the token shown once and kept only as a hash, and `env` its environment filled in: `RROTOR_MODE=self`, `RROTOR_SERVER`, `RROTOR_RUNTIME_ID`, `RROTOR_RUNTIME_TOKEN`, `RROTOR_PUBLIC_HOST`. `public_url` is `https://<host>` and nothing more (no port, path, query or fragment), stored lowercased; one of Glyphh's own addresses (`*.glyphh.app`, the server, the platform) is refused, and one person registers an address once (`E_CONFLICT`, `reason: registered`).

- **Managed from the account:** `GET /v1/runtimes/self` (`[{id, name, public_url, state, version, last_seen_at, last_heartbeat_at}]`), `POST /v1/runtimes/self/{id}/token` (a new token, `{token}`, shown once: the old one stops at once, its link is closed `4401` on whichever server process holds it, and the link's sequence numbers start again), `DELETE /v1/runtimes/self/{id}` (204: the record, its keys, deployments and runs go, its link is closed; the runtime's own volume is untouched). A runtime key for it is `POST /v1/runtime/keys` with its `runtime_id`.
- **Linked like the others:** its `hello` says `mode: self`; its `welcome` carries its keys and a licence (`kind: link`, 24 hours, `grace_days: 14`, precedents unlimited). It is never tallied, metered, provisioned, woken or stopped: a deploy or an approval's answer for it while it is not linked is `E_UNAVAILABLE` (`runtime_offline`, with when it was last seen).
- **Reached at its own address:** `https://<host>/mcp` and its REST API, behind TLS its owner terminates; a Glyphh sign-in for it is an OAuth resource of this server's (below, The connector: A runtime as a resource).
- **The heartbeat:** every 24 hours, and at boot, rrotor calls `POST /v1/license/verify` with its runtime token as the bearer and exactly `{machine, licence_id, version, active_runs}`: `machine` the SHA-256 (hex) of its runtime id, `:` and its machine id, `licence_id` the licence it holds (or `null`). The answer is `200 {licence}` (`kind: heartbeat`, 24 hours, `grace_days: 14`, `Cache-Control: no-store`); a hosted or local runtime's token is `E_FORBIDDEN` (`not_self`), a bad one `E_UNAUTHORIZED`, any other field `E_INVALID`. The server keeps only when it beat, the version, the runs and the machine hash. **Never kept or logged:** the caller's IP address (the server's access line for this path is dropped), and never sent: prompts, a model's inputs or outputs, anyone's data.
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
- **Plans, billing and the licence:** flat plans on Stripe, hosted machines metered per second to a Billing Meter ([Billing and hosting](#billing-and-hosting)); a short-lived signed licence per install or runtime ([The license](#the-license)). The server enforces the hosted machines; rrotor enforces the managed precedents from its licence.
- **The Glyphh connector:** a remote MCP server (`/mcp`) for the account and the runtimes, signed in with OAuth ([The connector](#the-connector)).
- **The runtime link:** rrotor's outbound WebSocket, on its own token. Up come online, `deployed`, events, `usage` and each run's status and seconds; down go only the licence, keys, a deploy and an approval's answer. Never a call.
- **Approvals:** a `needs_approval` is a row in `approvals` and a signal on Redis pub/sub to whichever server process holds the person's `/v1/approvals/stream`. Redis (`GLYPHH_REDIS_URL`) holds only live signals; Postgres holds everything kept.
- **Models:** the record of each Ada model, its versions, deployments and runs, never their content (`/v1/models`).
- **Hosting** (off by default, `GLYPHH_HOSTING`): each machine and volume made in Glyphh's one Fly app, stopped when idle, metered every minute ([Reaching a runtime](#reaching-a-runtime)).

### Starting up, and the reset on deploy

The image runs the schema step before the server (`python -m glyphh_server.db.schema`), one process at a time (an advisory lock): it runs `db/schema.sql` as it is (safe to run again), refuses to boot if a table lacks a column the code maps (there are no migrations yet: reset the dev database with `docker compose down -v`), then seeds the mods (`ada`; a mod no longer seeded is retired, never deleted), the plans and their first versions (`db/seed.py`; a Stripe price a plan's newest version does not sell on becomes a new version), Fly's rates (`db/seed_rates.py`; a row there is never changed) and the platform's OAuth client (`db/seed_clients.py`, [The connector](#the-connector)). The server then refuses to start without a `GLYPHH_SECRET_KEY` of 32 characters or more, or in `prod` without `GLYPHH_LICENSE_KEY`.

**In production the database is made clean on every deploy**, while nothing in it is kept: Fly's release command, `python -m glyphh_server.db.reset`, runs once before the new machines start and, only while `fly.toml` sets `GLYPHH_RESET_DATABASE=1`, drops every table the server's role owns and runs the schema step again. Every org, subscription record and grant goes with it; subscriptions in Stripe outlive it. Without the setting it keeps the data and says so.

### Settings

From the environment (prefix `GLYPHH_`, or `.env`, never committed; `config.py`). In production each is a secret or `[env]` of the Fly app `glyphh-ai-server`:

| Setting | Default | What |
|---|---|---|
| `GLYPHH_ENV` | `dev` | `dev`, `test` or `prod` |
| `GLYPHH_DATABASE_URL` | `postgresql+asyncpg://glyphh:glyphh@localhost:5432/glyphh` | Postgres; a plain `postgres://…?sslmode=` URL is made asyncpg's |
| `GLYPHH_RESET_DATABASE` | off | The reset on deploy (above) |
| `GLYPHH_REDIS_URL` | `redis://localhost:6379/0` | Redis, for live signals only; in production on the server's own Fly machine |
| `GLYPHH_VERSION` | `dev` | The version the API and the connector report (set by the image build) |
| `GLYPHH_LOG_LEVEL` | `INFO` | The JSON logs' level |
| `GLYPHH_PUBLIC_URL` | `http://localhost:8080` | The server's own address: the issuer, the connector's resource, the provider callbacks |
| `GLYPHH_PLATFORM_URL` | `http://localhost:3000` | The platform: every browser step is sent there; the one origin `GET /auth/consent` answers with CORS |
| `GLYPHH_PLATFORM_CLIENT_ID`, `_SECRET` | none | The platform's own OAuth client (the platform's `PLATFORM_CLIENT_ID` and `_SECRET`), made at every start |
| `GLYPHH_SECRET_KEY` | none (required) | 32+ characters, or the server refuses to start; signs every browser step's value (device sign-in, linking a provider, the connector's Allow, installing the GitHub App) |
| `GLYPHH_LICENSE_KEY` | none | Base64 of a raw 32-byte Ed25519 private key; signs every licence. Required in `prod`; elsewhere one is made at start (licences then don't survive a restart) |
| `GLYPHH_GOOGLE_CLIENT_ID`, `_SECRET`, `GLYPHH_GITHUB_CLIENT_ID`, `_SECRET` | none | Sign-in providers; one without both is not offered |
| `GLYPHH_STRIPE_SECRET_KEY`, `GLYPHH_STRIPE_WEBHOOK_SECRET` | none | Billing; without them it answers `E_UNAVAILABLE` `billing_off` |
| `GLYPHH_STRIPE_PRICE_PRO`, `GLYPHH_STRIPE_PRICE_TEAM` | none | The flat monthly prices Pro and Team sell on; a price a plan's newest version doesn't sell on becomes a new version at the next boot |
| `GLYPHH_STRIPE_PRICE_HOSTING` | none | The metered hosting price (a cent a unit), with hosting on the second item on every paid subscription; without it, with hosting on, Checkout is `billing_off` |
| `GLYPHH_STRIPE_METER_HOSTING` | none | The meter's event name (`glyphh_hosting`); without it nothing is reported |
| `GLYPHH_GITHUB_APP_ID`, `_PRIVATE_KEY`, `_SLUG` | none | The Glyphh GitHub App: its id, its PEM key (line breaks may be written `\n`) and its slug (install page `https://github.com/apps/<slug>/installations/new`; set the App's Setup URL to `{public_url}/v1/github/callback`); without all three, `E_UNAVAILABLE` `github_off` |
| `GLYPHH_SECRETS_KEY` | none | Base64 of 32 bytes; encrypts routine trigger tokens (AES-256-GCM); without it routine triggers are `E_UNAVAILABLE` `secrets_off`; changing it makes the stored tokens unreadable |
| `GLYPHH_INVITE_URL` | `{public_url}/join` | Where an invite's link points |
| `GLYPHH_MCP_ORIGINS` | `https://claude.ai,https://claude.com` | Browser origins `/mcp` takes besides the server's own, comma-separated; a request with no `Origin` passes |
| `GLYPHH_HOSTING` | off | Glyphh's managed cloud, `on` or `off` ([Machines](#machines)); off, Checkout sells no hosting and `GET /v1/rates` is `E_UNAVAILABLE` `hosting_off` |
| `GLYPHH_FLY_API_TOKEN`, `GLYPHH_FLY_APP`, `GLYPHH_FLY_IMAGE` | none | Hosting: a deploy token, the one app the machines live in (`glyphh-ai-runtime` in production) and the hosted image (`registry.fly.io/<app>:<version>`); without all three it is off (`hosting_off`) |
| `GLYPHH_FLY_REGION` | `iad` | Where machines are made, and the rates `/v1/rates` shows |
| `GLYPHH_FLY_PUBLIC_DOMAIN` | `glyphh.app` | Each runtime is `https://<machine>.<domain>` |
| `GLYPHH_RUNTIME_IDLE_MINUTES` | `10` | A hosted machine idle this long is stopped |

### API

JSON over HTTPS under `/v1`, described by `/openapi.json`. Every call but the health check, the device flow's, the plans, rates and mods lists, the bought-once licence, the browser steps (sign-in, GitHub's pages, `/billing/done`), OAuth's own endpoints and Stripe's webhook carries an install's token or an OAuth access token (`Authorization: Bearer`); a runtime's own calls (`POST /v1/license/verify`, `POST /v1/runtime/introspect` and the link) carry its runtime token instead. The platform signs in as an OAuth client, so `/v1` takes either person's token, as the same person and org: a caller by access token has no install: `POST /v1/sign-out` ends its grant instead, no install is `current` in `GET /v1/installs`, and `POST /v1/runtime/local` refuses it (`E_INVALID` `no_install`: a local runtime belongs to an install). The server's root and `/health` answer `E_NOT_FOUND`: the health check is `/v1/health`. `/mcp` takes only an access token. The server renders no page: a browser in a flow is sent to the platform (above, The platform). Refusals are `{"error": {"code", "message", "trace_id"}}`; a limit is `E_LIMIT` with `reason` and `limit` (both the limit's name), `used`, `max` and the `plan` that lifts it; a feature the plan lacks is `E_NOT_IN_PLAN` with its `reason`.

| Area | Calls |
|---|---|
| Health | `GET /v1/health` (open: `{status, version, database, redis}`; Fly's check) |
| Device flow | `POST /v1/device/code` (with the plugin's `machine_id`), `POST /v1/device/token`, `GET /v1/device?code=` (to the platform's `/device`) |
| Browser steps | `GET /auth/providers` (`{providers: [google, github]}`), `GET /auth/{provider}/start?code=\|link=\|oauth=` (to the provider), `GET /auth/{provider}/callback` (to the platform's `/device/approve`, `/allow` or `/account`), `GET /auth/consent?consent=` (what a consent asks), `GET /auth/approve?consent=&decision=`, `GET /auth/oauth/allow?consent=&decision=`, `GET /billing/done` (to the platform's `/billing`); each consent signed, ten minutes, tied to the browser by the `glyphh_signin` cookie; a refusal on any of these but `/auth/providers` and `/auth/consent` (which the platform reads as JSON) goes to the platform's `/error` |
| Account | `GET`/`PATCH /v1/me` (the org, the plan, `precedents` and `hosting` as in `GET /v1/billing`), `POST /v1/me/identities` (a link that adds Google or GitHub), `DELETE /v1/me/identities/{provider}`, `GET /v1/installs`, `DELETE /v1/installs/{id}`, `POST /v1/sign-out`, `GET /v1/license`, `GET /v1/license/key`, `POST /v1/license/verify` (a self-hosted runtime's heartbeat, its runtime token as auth) |
| Org | `GET`/`PATCH /v1/org`, `GET /v1/org/members`, `DELETE /v1/org/members/{user_id}`, `GET`/`POST /v1/org/invites`, `DELETE /v1/org/invites/{id}`, `POST /v1/invites/accept` |
| Mods, plans, billing | `GET /v1/mods` (each mod and the plans that include it: every one), `GET /v1/plans`, `GET /v1/rates`, `GET /v1/billing`, `POST /v1/billing/checkout`, `/plan`, `/portal`, `POST /v1/stripe/webhook` (below, Billing and hosting) |
| Runtime | `POST /v1/runtime/local` (a local rrotor's runtime token, for this install: made the first time, rotated after, shown once); `/v1/runtime/link`, the runtime's outbound WebSocket, hosted, local or self-hosted (protocol 1, as rrotor's `docs/architecture.md` section 6: the token in the `Authorization` header, a local runtime refused once its install is signed out, `hello` then `welcome`, the runtime `online` until it closes; results and events acked and applied once by their sequence number; a newer link of the same runtime takes over). Which server process holds which link: in memory, and a Redis channel per runtime, so a message sent on any process reaches it. The service functions other code calls: `send_continue` (an approval's answer) and `send_deploy`; calls never go down the link. A hosted runtime no process holds is woken first (its machine started) and the message waits up to 45 s for its link (with hosting off, `E_UNAVAILABLE` `hosting_off`); a runtime still not linked answers `E_UNAVAILABLE` `runtime_offline` with `last_seen_at`, in words for its kind (`AWAY` in `ops/link/calls.py`: a hosted machine that was started but did not connect in time, a local runtime to start from Claude, a self-hosted one to check). `GET /v1/runtime` (the first machine: `{runtime_id, address, state, region, image_version, last_seen_at, seconds_used}`, `state` `none` with no machine), `POST /v1/runtime/start` (made the first time, within the plan's machines; `E_UNAVAILABLE` `hosting_off` or `fly_failed`), `POST /v1/runtime/stop`, `DELETE /v1/runtime` (the machine, the volume and every model's data on it); `GET`/`POST /v1/runtimes`, `GET /v1/runtimes/{id}`, `POST /v1/runtimes/{id}/start`, `/stop`, `/restart`, `DELETE /v1/runtimes/{id}?confirm=<name>` (above, Machines); `GET`/`POST /v1/runtime/keys` (a key shown once, `glyphh_rk_…`, for the machine or self-hosted runtime `runtime_id` names, or every hosted machine of the person's; its hash to rrotor at once when linked, else in its next welcome), `DELETE /v1/runtime/keys/{id}` (revoked: answers the key, named in the list, dated, no longer taken), `DELETE /v1/runtime/keys/{id}/record` (204: a revoked or expired key's record gone; a live one `E_CONFLICT` `live`); `GET`/`POST /v1/runtimes/self`, `POST /v1/runtimes/self/{id}/token`, `DELETE /v1/runtimes/self/{id}`, `POST /v1/runtimes/{id}/offline-licence` (above, Self-hosted runtimes) |
| GitHub | `POST /v1/github/install` (a link for the browser, as linking does), `GET /v1/github/install` (to the Glyphh GitHub App's install page), `GET /v1/github/callback` (records the installation, from the browser that started it, when GitHub says it is on the person's own GitHub account), `GET /v1/github/installations`; the Cloud mints a repo-scoped installation token per deploy |
| Routine triggers | `GET`/`POST /v1/routine-triggers` (name, fire URL, token, optional model; the token is never shown again), `DELETE /v1/routine-triggers/{id}`; the Cloud fires them (`POST …/fire`) on a model's events |
| Connector | `GET /.well-known/oauth-protected-resource` (and `/mcp` after it), `GET /.well-known/oauth-authorization-server`, `POST /oauth/register`, `GET /oauth/authorize`, `POST /oauth/token`, `POST /oauth/revoke`, `POST /mcp`; `GET /v1/connector/grants`, `DELETE /v1/connector/grants/{id}`; `POST /v1/runtime/introspect` (a hosted or self-hosted runtime asking about a bearer, its runtime token as auth) (below, The connector) |
| Models | `GET`/`POST /v1/models` (never limited; a name once per person), `GET`/`DELETE /v1/models/{id}` (the record, its versions, deployments and runs; the rrotor keeps its copy until a `remove` deploy), `POST /v1/models/{id}/versions` (a commit's SHA and its manifest: the next version; `E_CONFLICT` `commit_known`), `POST /v1/models/{id}/deploy` (`version`, `action` deploy \| activate \| remove, `runtime_id` or the caller's own: the install's local runtime, else the person's first hosted machine, else `E_NOT_FOUND` `no_runtime`; the rrotor answers `deployed` on its link and only then is the version active there) |
| Runs | None here: a model is called on the runtime itself (above, Reaching a runtime). The server keeps the run record it hears over the link (status, times, seconds), never inputs or outputs |
| Approvals | `GET /v1/approvals` (waiting, newest first), `GET /v1/approvals/stream` (server-sent events: `approval`, `answered`; the waiting ones replayed first, a heartbeat every 20 s), `POST /v1/approvals/{id}` `{answer: approve \| decline}` (first answer wins); a run's `needs_approval` enters through the link; the answer goes down it as `continue` (a runtime not connected answers `E_UNAVAILABLE` and the step keeps waiting) |

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

(A Pro org's install: an install's licence carries no precedent limit.)

A runtime's licence (in a hosted or self-hosted runtime's `welcome`, from a self-hosted one's heartbeat, or issued offline) has `install_id` `null` and three more signed fields, four on a self-hosted one's (`grace_days`); an install's licence has none of them. A hosted runtime's carries the plan's managed precedents:

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
      "ada": {"limits": {"precedents": 100000}}
    },
    "expires_at": "2026-10-19T09:30:00Z",
    "runtime_id": "3d8f…",
    "licence_id": "c41a…",
    "kind": "link"
  },
  "signature": "Xn2c…=="
}
```

- `runtime_id` is the runtime it is for; `licence_id` is new with every licence; `kind` is `link` (a welcome), `heartbeat` or `offline` (up to 365 days).
- `grace_days` is 14 on a self-hosted runtime's licence and absent (0) on a hosted one's: the licence counts as live until `expires_at` plus that many days.

- `mods` names every active mod (every plan includes each); a retired mod is in no license. Ada's one limit is `precedents`, the runtime's total across its Ada models: the plan's managed bucket on a hosted runtime (Pro 100,000, Team 1,000,000, Enterprise `null`), `null` (unlimited) on a local or self-hosted one and in an install's licence.
- `limits` at the top holds `machines`, the hosted machines the org may have, its people's together (`null` unlimited).
- `features` are the plan's: `sync`, `ha`, `offline`, `sso`. Only `offline` is acted on (offline licences); the others are flags ([Not built yet](#not-built-yet)).

### Billing and hosting

A paid plan is one Stripe subscription: the plan's flat price and, with hosting on, the shared metered hosting price. Writes are the admin's.

- **`GET /v1/plans`** (open): each active plan's newest version, `[{name, version, price_cents, interval, self_serve, limits: {machines, precedents}, features: {sync, ha, offline, sso}, markup_hidden: true}]`; `interval` is `month`, `year` or `null` (Free), `price_cents` `null` for Enterprise (each contract's), `limits.machines` 0 on every plan while hosting is off. Never the markup.
- **`GET /v1/rates`** (open): `{effective_from, region, sizes: [{size, cpu_kind, cpus, memory_mb, volume_gb}], plans: {"Pro": {sizes: [{size, cpu_kind, cpus, memory_mb, volume_gb, usd_per_month, usd_per_second}], volume_usd_per_gb_month}, "Team": …}}`: each size's machine, and each plan's whose newest version has a markup (Pro and Team), Fly's × (1 + its markup), to the cent a month and per second (a size's `usd_per_month` is a 30-day month started; its volume is apart, billed always). Never Fly's own rates, their source or the markup, from which the markup could be worked out; Enterprise's are its contract's. The region is `GLYPHH_FLY_REGION`, `effective_from` the newest date among the rates in force. A region with no rates is `E_UNAVAILABLE` `no_rates`; with hosting off, any request is `E_UNAVAILABLE` `hosting_off`.
- **`GET /v1/billing`** (anyone in the org): `{plan (as in `/v1/plans`), billing_status, renews_at, plan_until, precedents: {used, limit}, hosting: {month, month_to_date_cents, machines: [{id, name, size, cents}]}}`: `used` is what the org's hosted runtimes last said they hold, `limit` the plan's bucket; `hosting` the month so far, all in, each machine's own (a deleted one too), in whole cents (each floored on its own, so the machines may sum to a cent or so less than the total). `GET /v1/me` carries the same `precedents` and `hosting`.
- **`POST /v1/billing/checkout` `{plan}`**: Stripe Checkout for Pro or Team (the flat price, quantity 1, and with hosting on the metered hosting price). A plan with no Stripe price here (Free, or Pro and Team before their prices are set) is `E_INVALID` `not_sold`, Enterprise `E_INVALID` `not_self_serve` ("talk to us at sales@glyphh.ai"), an unknown plan `E_INVALID`, a subscribed org `E_CONFLICT` `subscribed`, a server without Stripe, or with hosting on and no hosting price, `E_UNAVAILABLE` `billing_off`.
- **`POST /v1/billing/plan` `{plan}`**: to the newest version of Pro or Team (a newer version of its own plan too; the same version changes nothing), prorated (the flat item's price changed, the metered item left); to Free, the hosting due is reported and the subscription cancelled now (invoiced, prorated). Either is refused while the org holds more hosted machines than the new plan allows, all its people's together (`E_CONFLICT` `machines`, with `held` and `max`: "Delete your hosted machines first." on Free, "Delete your hosted machines first. Pro allows 3 hosted machines." otherwise). Not subscribed `E_CONFLICT` `not_subscribed`; an org on a plan by contract `E_CONFLICT` `contract`; Enterprise named `E_INVALID` `not_self_serve`. Answers the org.
- **`POST /v1/billing/portal`**: Stripe's portal (card, invoices, cancel); an org that never checked out is `E_CONFLICT` `no_billing`.
- **Stripe's webhook** (signed: a bad or older-than-300-seconds signature is `E_UNAUTHORIZED`) handles `checkout.session.completed`, `customer.subscription.created`, `.updated` and `.deleted`, and `charge.refunded`, and logs any other. It keeps the org true: the org found by its Stripe customer, else by `metadata.org_id` or `client_reference_id`; on every subscription event it reads the subscription fresh and matches its flat item's price to a plan version, passing over a metered item; a subscription that ended puts the org on Free (an Enterprise deal's too, its grant cleared). The hosting due is reported first, and with hosting on, machines the org now holds past its plan are stopped at once (below, Held past the plan). A subscription that is not the org's current one is passed over, so replays and events out of order change nothing; `renews_at` is empty when the subscription ends at the period's end.

How hosting becomes a charge:

![Metering and the meter](img/billing.png)

```mermaid
sequenceDiagram
    participant T as Minute tick (one process at a time)
    participant DB as Postgres
    participant F as Fly
    participant S as Stripe
    participant W as The webhook (POST /v1/stripe/webhook)
    T->>DB: advisory lock taken (held elsewhere: this minute skipped)
    T->>DB: each hosted machine's month: seconds since metered_at × its size's rate online, its volume always
    T->>DB: machine_months cost, and charge = cost × (1 + markup)
    T->>DB: expired keys taken off, Enterprise grants past their date ended (hosting due reported first)
    opt hosting on
        T->>F: stop idle machines, then those held past the plan
    end
    opt Stripe and the meter set
        T->>DB: due = charged, to the cent, less reported (org row locked): a meter_events row
        T->>S: meter event glyphh_hosting (cents, its id the identifier)
        S-->>T: taken: sent_at set (refused: sent again next tick)
    end
    Note over T,S: once a day, and ten minutes before renews_at
    S->>W: a subscription event, signed
    W->>S: the org's hosting due reported first
    W->>DB: the org synced to its plan version (Free when it ended)
    W->>F: machines past the new plan stopped (hosting on)
```

**Metering.** Fly's rates are the `fly_rates` table: each size's and a GB of volume's, per region, a 30-day month's worth, dated (`effective_from`) with their source; the rate in force is the newest that has come, a second is a 2,592,000th of it (seeded for `iad`, read 2026-10-18: small $6.70, medium $25.39, large $90.00, volume $0.15 a GB). Every minute each hosted machine's month (`machine_months`) adds the whole seconds since it was last metered (`rrotors.metered_at`; its `created_at` the first time), and `metered_at` moves on by exactly those seconds, the fraction carried, the machine's row locked: its size's rate for those seconds when its link is online at the tick and its volume's GB for all of them, online or not: the cost, and the charge (the cost × (1 + the markup): the org's own `markup_pct` when set, else its plan's; nothing on a plan with no hosting, Free, where only the cost of held machines' disks is kept), both in micro-dollars. A machine with no region is metered in the server's (`GLYPHH_FLY_REGION`); one in a region with no rates is logged and costs nothing for those seconds. The seconds go to the month of the tick. A tick late, missed, run twice or in two server processes, or the server restarting, meters each second once.

**The meter.** The hosting price is on the Stripe Billing Meter `glyphh_hosting` (`GLYPHH_STRIPE_METER_HOSTING`; a unit is a US cent, summed, the customer by its id). With Stripe set up, every minute each subscribed org's hosting due (all it has charged, across every month, to the cent, less all it has reported; the rest carried) is reported once a day (the first as soon as a cent is due) and as its period ends (ten minutes before `renews_at`); the webhook reports it too, before every subscription event it applies, and so does a change to Free. Each report is a `meter_events` row written before it is sent, its id the event's identifier, worked out with the org's row locked, so two servers report it once; one Stripe refused is sent again with the same identifier at the next tick.

**Enterprise** is granted by staff, never bought (`ops/enterprise.py`, `grant` and `revoke`: [pricing.md](pricing.md#the-control-plane)). The org's `plan_until`, deal subscription and, with hosting on, `markup_pct` (`--markup`, optional) are recorded on it; its hosting goes to that subscription, and before a grant is revoked or lapses the hosting due is reported there first, as the webhook does.

**Held past the plan.** A plan's machines are the org's, its oldest first. An org on a plan that allows fewer hosted machines than it holds (a subscription cancelled in the portal or ended, an Enterprise grant revoked or lapsed; the server's own plan changes refuse to get there) keeps its oldest machines up to the plan's running and has its newest beyond them stopped: from the webhook and `revoke` at once, and at every minute's tick, which also stops any a request woke on Fly's proxy since. Starting, restarting or waking one (`POST /v1/runtimes/{id}/start`, `/restart`, `/v1/runtime/start`, a deploy or an approval's answer that would wake it) is `E_LIMIT` `machines` (`used` the org's) until the org is on a plan that allows them or deletes enough: they keep their disks and may be deleted, and deleting one lets the next oldest start. A request at a held machine's own address is woken by Fly's proxy, and the next tick stops it again.

**The minute tick** (`ops/tend.py`) runs whether or not hosting is on, in this order: with hosting on, each hosted machine's month tallied and metered (the diagram above is the tick with hosting on); the keys that expired taken off their runtimes; Enterprise grants past their date ended (their hosting due reported first); with hosting on, the idle machines stopped, then those held past the plan; with `GLYPHH_STRIPE_SECRET_KEY` and `GLYPHH_STRIPE_METER_HOSTING`, the meter reported. A failed tick is logged and the next minute comes. Every server process runs it, and production runs more than one: each tick takes a Postgres advisory lock (`pg_try_advisory_lock`, `TICK` in `ops/tend.py`) on a connection it holds for the tick and lets go after, so no two ticks run at once; a process that finds it held skips that minute. Ticks one after another in different processes may both run within a minute, and every part is safe to run again: metering counts the time since each machine was last metered, never a fixed minute.

Stripe's products, prices and meter are made once per account with `scripts/stripe-setup.py` ([pricing.md](pricing.md#the-control-plane)).

### The connector

A remote MCP server at `{public_url}/mcp`, its own OAuth 2.1 authorization server, following MCP's authorization spec (revision 2026-07-28). Through it a person manages their Glyphh account from Claude or any MCP client.

**Discovery.**

- `GET /.well-known/oauth-protected-resource` and `/.well-known/oauth-protected-resource/mcp` (RFC 9728): `resource` `{public_url}/mcp`, `authorization_servers` `[{public_url}]`, `scopes_supported` `["account"]`, `bearer_methods_supported` `["header"]`, `resource_name` `Glyphh`.
- `GET /.well-known/oauth-authorization-server` (RFC 8414): the issuer `{public_url}` and its endpoints; `response_types_supported` `["code"]`, `grant_types_supported` `["authorization_code", "refresh_token"]`, `code_challenge_methods_supported` `["S256"]`, `token_endpoint_auth_methods_supported` `["none", "client_secret_post", "client_secret_basic"]`, `scopes_supported` `["account"]`, `revocation_endpoint_auth_methods_supported` the same three, `authorization_response_iss_parameter_supported` `true` (RFC 9207).
- `/mcp` without a good token answers 401 with `WWW-Authenticate: Bearer resource_metadata="{public_url}/.well-known/oauth-protected-resource/mcp", scope="account"` (and `error="invalid_token"` when an `Authorization` header was sent); the body is the API's `E_UNAUTHORIZED`.

**A runtime as a resource.** A hosted runtime is a protected resource of its own: its `GET https://<machine>.glyphh.app/.well-known/oauth-protected-resource` names this server as its authorization server, and `resource` on `/oauth/authorize` and `/oauth/token` may be `https://<machine>.glyphh.app` or that `/mcp` (the machine label 6 to 32 of `0-9a-z`, the domain `GLYPHH_FLY_PUBLIC_DOMAIN`); the token is bound to `https://<machine>.glyphh.app/mcp` and is no good on this server's `/mcp`. A registered self-hosted runtime's `public_url` (or its `/mcp`) is a resource the same way, looked up across every org, and the token is bound to `https://<its host>/mcp`. rrotor cannot read the token: it asks `POST /v1/runtime/introspect` (`{token}`, its own runtime token as the bearer) and gets RFC 7662's shape, `{active, sub, org, scope, exp}`, `active` only when the token was issued for that runtime's own address (its machine's, or its `public_url`'s) to a person of the runtime's org; `Cache-Control: no-store`, and rrotor keeps the answer a minute. A local runtime, or one without a machine yet, is always told `active: false`. So Claude adds a runtime as a connector with one Allow click and no key.

**Registration.** `POST /oauth/register` (RFC 7591): `redirect_uris` (1 to 10; each `https`, or `http` on `localhost`, `127.0.0.1` or `[::1]`; a host, no fragment, up to 2,000 characters), `client_name` (up to 100 characters; left out, the first redirect URI's host), `token_endpoint_auth_method` (`none` for a public client; `client_secret_basic`, RFC 7591's default, or `client_secret_post` get a `client_secret`, shown once and kept hashed), `grant_types` within `authorization_code` and `refresh_token` (both when left out), `response_types` `["code"]`; any other metadata is ignored. It answers `201` with the `client_id` and `client_id_issued_at` (and the secret, with `client_secret_expires_at` 0). Refusals are `invalid_redirect_uri` or `invalid_client_metadata`.

**The platform's own client** is not registered: it is made at every start (`db/seed_clients.py`, in the schema step) from `GLYPHH_PLATFORM_CLIENT_ID` (a UUID: the platform's `PLATFORM_CLIENT_ID`; any other value stops the start) and `GLYPHH_PLATFORM_CLIENT_SECRET`, so the database's reset on deploy never loses it. It is confidential (`client_secret_basic`, its secret kept hashed), named `Glyphh`, with both grant types and one redirect URI, `{GLYPHH_PLATFORM_URL}/auth/callback`; a changed secret or address takes at the next start. Without both settings, none is made. The flow treats it as any other client.

**Authorization.** `GET /oauth/authorize` with `response_type=code`, `client_id`, `redirect_uri` (exactly as registered), `state` (required), `code_challenge` and `code_challenge_method=S256` (required), `scope` (`account`, the default) and `resource` (`{public_url}/mcp` or `{public_url}`, the token bound to `{public_url}/mcp`; or a runtime's address, hosted or self-hosted, below). An unknown client or redirect URI is `E_INVALID` and never a redirect; any other refusal goes back to the redirect URI as `error` (`unsupported_response_type`, `unauthorized_client`, `invalid_request`, `invalid_scope` or `invalid_target`), `error_description`, `state` and `iss`. The server renders nothing: a good request goes on to the platform's `/authorize?oauth=&client=` (Continue with Google or GitHub, through the same provider steps as the device sign-in, tied to the browser by the same cookie, ten minutes); the provider's callback sends the browser to the platform's `/allow?consent=`, which reads `GET /auth/consent` (`{kind: "oauth", client, returns_to, resource, email}`: the client, the redirect URI's host, the resource and the email signed in) and answers `GET /auth/oauth/allow?consent=&decision=allow|deny`. Allow redirects to the client with a `code` (single use, 2 minutes), `state` and `iss`; any other answer with `error=access_denied`.

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
| `plan` | The plan: its price, hosted machines, managed precedents and features, billing status and when it renews | Everyone |
| `usage` | The precedents the org's hosted runtimes hold of the managed bucket, and hosting this month so far, machine by machine | Everyone |
| `plans` | What each plan costs and includes: hosted machines, managed precedents, features | Everyone |
| `upgrade` | `plan`: Stripe Checkout's address when not subscribed; when subscribed, changes plan (prorated; Free cancels), refused while the org holds more hosted machines than the new plan allows | Admin |
| `billing_portal` | Stripe's portal address: card, invoices, cancel | Admin |
| `installs`, `sign_out_install` | The person's installs; sign one out (`install_id`) | Everyone |
| `members`, `invite` | The org's members and open invites; invite by `email` (the link, shown once) | Everyone; `invite` the admin |
| `connector_grants`, `revoke_grant` | The connector's grants; revoke one (`grant_id`) | Everyone |
| `runtime`, `start_runtime`, `stop_runtime` | The person's first machine: its address, state and the month's online time; start a machine (`id`, or the first, made the first time); stop one (`id`, or the first) | Everyone |
| `runtimes`, `create_runtime`, `restart_runtime`, `delete_runtime` | The person's machines; make one (`name`, `size`: small, medium or large; up to the plan's machines) and start it; restart one (`id`); delete one (`id`, and `confirm`, its name as the person typed it). With hosting off, making, starting and restarting are `E_UNAVAILABLE` `hosting_off` | Everyone |
| `runtime_keys`, `create_runtime_key`, `revoke_runtime_key` | The keys that call the runtimes at their addresses; make one (`name`; `expires_in_days` 1 to 365, or never; `runtime_id` for one machine or self-hosted runtime, else every hosted machine; shown once); revoke one (`key_id`) | Everyone |
| `self_runtimes`, `register_self_runtime`, `offline_licence` | The person's self-hosted runtimes (address, state, version, last heartbeat); register one (`name`, `public_url`, a plain `https://<host>`; its token and environment shown once); an offline licence for one (`runtime_id`, `days` 1 to 365) | Everyone; `offline_licence` on Enterprise only |

Each result is a short text and the same as structured content; a refusal is a tool result with `isError` and the API's error (`{"error": {"code", "message", "trace_id", …}}`) as structured content, bad arguments `E_INVALID`. An unknown tool is a JSON-RPC error (`-32602`). Each call runs in a savepoint, so a refusal leaves nothing half done.

**The account panel.** One MCP App resource, `ui://glyphh/account/3` (`text/html;profile=mcp-app`, MCP Apps 2026-01-26), listed by `resources/list` and read by `resources/read`; `whoami`, `plan` and `usage` name it in `_meta.ui.resourceUri`. It shows who you are, the plan with its machines, managed precedents and features, the usage (precedents and hosting this month, machine by machine), Upgrade (opens Checkout, or changes plan), Manage billing, the installs (sign one out) and the grants (revoke one); every action is a call of the connector's own tools through the host. The server advertises nothing for it, as MCP Apps says: on 2026-07-28 requests the tools carry the link only when the request's `clientCapabilities` name the `io.modelcontextprotocol/ui` extension with that mime type; on the stateless earlier revisions, where a request carries no capabilities, they always carry it, and a client without panels ignores it. Its address carries its version: a new panel is a new address. Generic styling, with the host's theme variables.

### Anthropic's terms

From Claude Code's legal page and the Consumer Terms (checked 2026-10-14):

- Third-party developers may not offer Claude.ai login in their apps, route requests through someone's subscription, or "collect, store, or intermediate Claude.ai credentials or session tokens"; nor pay for or resell Claude usage on their users' behalf.
- **Glyphh never touches a Claude login:** Claude runs on the person's own subscription in Anthropic's own products (Claude Code, routines, scheduled tasks) and calls Glyphh's tools. rrotor has no Claude in it.
- A routine's API token, if a person gives one to Glyphh to start their routine, starts that routine only; it is not a Claude login.

## Data model

### In the cloud

![The cloud's tables](img/data-model-cloud.png)

```mermaid
erDiagram
    PLANS ||--|{ PLAN_VERSIONS : "has versions"
    PLAN_VERSIONS ||--o{ ORGS : "pinned by"
    ORGS ||--o{ MACHINE_MONTHS : "billed for"
    RROTORS |o..o{ MACHINE_MONTHS : "metered as"
    ORGS ||--o{ METER_EVENTS : "reported"
    ORGS ||--|{ USERS : "members"
    ORGS |o--o| USERS : "admin"
    ORGS ||--o{ INVITES : "sends"
    USERS ||--|{ IDENTITIES : "signs in with"
    USERS ||--o{ INSTALLS : "has"
    INSTALLS ||--o{ TOKENS : "holds"
    INSTALLS ||--o{ DEVICE_CODES : "approved by"
    USERS ||--o{ RROTORS : "has: hosted machines, one local per install, any self-hosted"
    INSTALLS ||--o| RROTORS : "local runtime"
    USERS ||--o| GITHUB_INSTALLATIONS : "installed the App"
    USERS ||--o{ ROUTINE_TRIGGERS : "gave"
    MODELS ||--o{ MODEL_EVENTS : "raised"
    ROUTINE_TRIGGERS ||--o{ MODEL_EVENTS : "fired by"
    MODELS |o--o{ ROUTINE_TRIGGERS : "for"
    USERS ||--o{ MODELS : "owns"
    ORGS ||--o{ MODELS : "holds"
    MODELS ||--|{ MODEL_VERSIONS : "has"
    MODEL_VERSIONS ||--o{ DEPLOYMENTS : "deployed as"
    RROTORS ||--o{ DEPLOYMENTS : "runs"
    MODEL_VERSIONS ||--o{ RUNS : "ran"
    RROTORS ||--o{ RUNS : "ran on"
    USERS ||--o{ RUNTIME_KEYS : "made"
    RROTORS |o--o{ RUNTIME_KEYS : "named by"
    RUNS ||--o{ APPROVALS : "waits on"
    USERS ||--o{ CONNECTOR_GRANTS : "allows"
    OAUTH_CLIENTS ||--o{ CONNECTOR_GRANTS : "granted to"
    OAUTH_CLIENTS ||--o{ OAUTH_CODES : "asked for"
    USERS ||--o{ OAUTH_CODES : "allowed"
    CONNECTOR_GRANTS |o--o{ OAUTH_CODES : "redeemed into"
    CONNECTOR_GRANTS ||--o{ CONNECTOR_TOKENS : "holds"
    PLANS {
        uuid id PK
        text name UK
        bool active
        int sort
    }
    PLAN_VERSIONS {
        uuid id PK
        uuid plan_id FK
        int version "unique per plan"
        text stripe_price_id UK
        int price_cents "null: per contract"
        text billing_interval "month, year or null"
        bool self_serve
        int max_machines
        int precedents "the managed bucket"
        bool sync
        bool ha
        bool offline
        bool sso
        int hosting_markup_pct "never shown"
        timestamp created_at
    }
    FLY_RATES {
        text item PK "small, medium, large or volume"
        text region PK
        numeric usd_per_30_days
        date effective_from PK
        text source
    }
    MACHINE_MONTHS {
        uuid rrotor_id PK "kept past the machine"
        text month PK
        uuid org_id FK
        text name
        text size
        bigint cost_micros
        bigint charge_micros
        timestamp updated_at
    }
    METER_EVENTS {
        uuid id PK "the event's identifier"
        uuid org_id FK
        text customer
        int cents
        timestamp at
        timestamp created_at
        timestamp sent_at
    }
    MODS {
        text slug PK
        text name
        text description
        bool active
        int sort
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
        int markup_pct "its own, over the plan's"
        timestamp plan_until "an Enterprise grant's end"
        timestamp created_at
    }
    USERS {
        uuid id PK
        uuid org_id FK
        text email UK "in any case"
        text name
        text role
        timestamp created_at
    }
    IDENTITIES {
        text provider PK
        text provider_user_id PK
        uuid user_id FK
        timestamp created_at
    }
    INVITES {
        uuid id PK
        uuid org_id FK
        text email "one open per org"
        text token_hash UK
        timestamp expires_at
        timestamp accepted_at
        timestamp created_at
    }
    INSTALLS {
        uuid id PK
        uuid user_id FK
        text machine_id "unique per user, not revoked"
        text name
        text surface
        text mod_version
        timestamp last_seen_at
        timestamp revoked_at
        timestamp created_at
    }
    TOKENS {
        uuid id PK
        uuid install_id FK
        text token_hash UK
        timestamp expires_at
        timestamp revoked_at
        timestamp created_at
    }
    DEVICE_CODES {
        text device_code_hash PK
        text user_code UK
        uuid install_id FK
        text machine_id
        text name
        text surface
        text mod_version
        int interval
        timestamp polled_at
        timestamp expires_at
        timestamp approved_at
        timestamp denied_at
        timestamp created_at
    }
    RROTORS {
        uuid id PK
        uuid user_id FK
        text mode "hosted, local or self"
        uuid install_id FK "local: unique"
        text fly_machine_id "hosted"
        text fly_volume_id "hosted"
        text region
        text image_version
        text state
        text token_hash UK
        timestamp last_seen_at
        bigint seq "last applied from its link"
        text name "hosted and self; hosted: unique per user"
        text size "hosted: small, medium or large"
        text public_url "self: https://host"
        timestamp last_heartbeat_at "self"
        text machine_hash "self"
        int active_runs "self"
        text month "hosted: its tally's"
        int month_seconds "hosted: online this month"
        timestamp metered_at "hosted: metered up to"
        bigint precedents "its total, as it last said"
        timestamp precedents_at
        timestamp created_at "the first machine is the oldest"
    }
    RUNTIME_KEYS {
        uuid id PK
        uuid rrotor_id FK "null: every hosted machine"
        uuid user_id FK
        text name
        text key_hash UK
        timestamp created_at
        timestamp expires_at "null: never"
        timestamp revoked_at
        bigint calls
        timestamp last_used_at
    }
    MODELS {
        uuid id PK
        uuid user_id FK
        uuid org_id FK
        text name
        text repo
        timestamp created_at
    }
    MODEL_VERSIONS {
        uuid id PK
        uuid model_id FK
        int version "unique per model"
        text commit_sha "the version's identity"
        json manifest
        timestamp created_at
    }
    DEPLOYMENTS {
        uuid rrotor_id PK, FK
        uuid model_version_id PK, FK
        timestamp deployed_at
        bool active
    }
    RUNS {
        uuid id PK
        uuid model_version_id FK
        uuid rrotor_id FK
        text function
        text caller
        text status
        timestamp started_at
        timestamp ended_at
        int seconds
    }
    APPROVALS {
        uuid id PK
        uuid run_id FK
        text step
        text prompt
        text answer
        timestamp asked_at
        timestamp notified_at
        timestamp answered_at
    }
    GITHUB_INSTALLATIONS {
        uuid id PK
        uuid user_id FK, UK
        bigint installation_id UK
        text account_login
        timestamp created_at
        timestamp removed_at
    }
    ROUTINE_TRIGGERS {
        uuid id PK
        uuid user_id FK
        uuid model_id FK
        text name
        text fire_url
        text token_enc
        text status "ok or broken"
        timestamp last_fired_at
        timestamp created_at
    }
    MODEL_EVENTS {
        uuid id PK
        uuid model_id FK
        uuid routine_trigger_id FK
        text kind
        text session_url
        timestamp at
    }
    OAUTH_CLIENTS {
        uuid id PK "the client_id"
        text name
        text_array redirect_uris
        text auth_method
        text secret_hash "confidential clients"
        text_array grant_types
        timestamp created_at
    }
    OAUTH_CODES {
        text code_hash PK
        uuid client_id FK
        uuid user_id FK
        text redirect_uri
        text code_challenge "S256"
        text scope
        text resource
        uuid grant_id FK "once redeemed"
        timestamp expires_at
        timestamp used_at
        timestamp created_at
    }
    CONNECTOR_GRANTS {
        uuid id PK
        uuid user_id FK
        uuid client_id FK "one live per user"
        text scope
        text resource
        timestamp last_used_at
        timestamp revoked_at
        timestamp created_at
    }
    CONNECTOR_TOKENS {
        uuid id PK
        uuid grant_id FK
        text kind "access or refresh"
        text token_hash UK
        timestamp expires_at
        timestamp used_at "refresh: rotated"
        timestamp revoked_at
        timestamp created_at
    }
```

Every table and column is drawn, as `db/schema.sql` has them (28 tables); the tables from rrotors on are for Ada models, which rrotor runs as models, so the tables say `models`. Timestamps carry the time zone; ids are made by the database.

- **Plan versions never change their price or limits.** Changing either adds a version with its own Stripe price; an org stays on the version it subscribed to.
- **Mods:** every plan includes every active mod; a retired mod (`active` false) is in no license.
- **A limit left empty is unlimited.** `max_machines` is how many hosted machines the org may have, its people's together (0: none); `precedents` the managed bucket, the total a hosted runtime may hold across its Ada models. `hosting_markup_pct` is the markup on Fly's rates (null where there is no hosting or it is each customer's); an org's own `markup_pct` is over it.
- **Fly's rates** (`fly_rates`): never changed; a new rate is a new row, the newest whose `effective_from` has come in force. Not an org's: no row-level security.
- **Machine months** (`machine_months`): a hosted machine's cost and charge for a month, in micro-dollars, by its id (no foreign key, so a deleted machine's month stays), its name and size copied. **Meter events** (`meter_events`): each report of an org's hosting cents to Stripe's meter, written before it is sent; `sent_at` once Stripe took it. Both row-level secure on the org.
- **Runtimes** (`rrotors`): hosted machines (`mode: hosted`, each with its `name`, unique per person, `size`, its Fly machine and volume (`fly_machine_id`, `fly_volume_id`), `region`, and its month's online seconds, up to the plan's `max_machines`, the org's together), one local per install that started one (`mode: local`, keyed by its install), and any self-hosted ones (`mode: self`, each with its `name` and `public_url`, one per address per person, and from its heartbeat `last_heartbeat_at`, `image_version`, `active_runs` and `machine_hash`, never an address of its caller's); each its own token. `state` is `stopped` until its first link, `online` while its link is up, `offline` after; `seq` is the last result or event sequence number applied from its link, so a replay is applied once (a new token starts it again). `precedents` is the total across its Ada models it last reported.
- **Installs are machines:** `INSTALLS.machine_id` is the id the plugin sends (a hash of the hardware UUID, or a random id it keeps; 16 to 128 of `A-Za-z0-9_-`), unique per user among installs not revoked. `DEVICE_CODES.machine_id` carries it to approval, which reuses that machine's install (its old tokens revoked) or makes a new one: installs are never limited.
- **One org per user;** people found by the provider's own id; installs and tokens hashed; tenant isolation by row-level security on the org.
- **Models** (Ada models, as rrotor runs them): the record only: name, repo, versions (commit SHA, manifest), where each is deployed. The code is in the person's repo and their runtimes; secrets and data are in the rrotor.
- **GitHub installations:** the person's Glyphh GitHub App installation, from which the Cloud mints a short-lived token per deploy; no long-lived GitHub key is kept.
- **Routine triggers:** the routines the person let Glyphh start (fire URL and token, encrypted), marked broken on a 401. **Model events:** what a model raised and the routine session it started; an event that fired no routine has neither.
- **Runs:** who called (`routine`, `claude`, `panel`, `test`), the status, the times and the seconds rrotor ran, for the log; never inputs, outputs or content.
- **Approvals:** a step waiting for the person, until answered anywhere; `notified_at` is for the email, and stays empty until there is one (below, Not built yet).
- **Runtime keys** (`runtime_keys`): each key the person made, by its SHA-256 only, for one runtime (`rrotor_id`) or, empty, every hosted machine of theirs; `expires_at` empty for never; `calls` and `last_used_at` from rrotor's `usage`; a revoked or expired one kept, dated, until its record is deleted.
- **OAuth clients:** the MCP clients that registered (RFC 7591), each with its exact redirect URIs; a confidential one's secret only as a hash. They belong to no org.
- **OAuth codes:** an authorization the person allowed, until its code is redeemed (once, within 2 minutes), with its PKCE challenge and the resource it is for; `grant_id` names the grant it went into, so a second use revokes it.
- **Connector grants:** each client (a routine, the desktop, claude.ai) the person allowed to call the Glyphh connector, one live per client, revocable one by one. **Connector tokens:** its access tokens (1 hour) and refresh tokens (30 days, rotated on use; a rotated one used again revokes the grant), kept only as hashes.
- **Orgs:** `renews_at` is when the subscription renews, from Stripe; empty when it isn't subscribed or ends at the period's end. `markup_pct` and `plan_until` are an Enterprise grant's.

### Keys, checks, indexes and row-level security

Every constraint and index in `db/schema.sql`, table by table. An `ix_<table>_<column>` index is a plain index on that one column. Ids are `gen_random_uuid()`; `created_at` (and `asked_at`, `at`, `paid_at`, `started_at`, `deployed_at`, `updated_at`) default to `now()`.

| Table | Keys and checks | Foreign keys (on delete) | Indexes | Row-level security |
|---|---|---|---|---|
| `mods` | PK `slug`; `active` true, `sort` 0 by default | none | none | none |
| `plans` | PK `id`; `name` unique; `active` true, `sort` 0 by default | none | none | none |
| `plan_versions` | PK `id`; `plan_versions_version` unique (`plan_id`, `version`); `stripe_price_id` unique; `plan_versions_price` `price_cents` ≥ 0; `plan_versions_interval` `billing_interval` in `month`, `year` (or null); `plan_versions_limits` `max_machines` and `precedents` ≥ 0; `plan_versions_markup` `hosting_markup_pct` ≥ 0; `self_serve` true, `sync`, `ha`, `offline`, `sso` false by default | `plan_id` → `plans` (restrict) | `ix_plan_versions_plan_id` | none |
| `fly_rates` | PK (`item`, `region`, `effective_from`); `fly_rates_item` `item` in `small`, `medium`, `large`, `volume`; `fly_rates_rate` `usd_per_30_days` ≥ 0 (numeric 12, 4) | none | none | none |
| `orgs` | PK `id`; `stripe_customer_id` and `stripe_subscription_id` unique; `orgs_billing_status` `billing_status` in `none` (the default), `active`, `trialing`, `past_due`, `unpaid`, `canceled`, `incomplete`, `incomplete_expired`, `paused`; `orgs_markup` `markup_pct` ≥ 0 | `plan_version_id` → `plan_versions` (restrict); `admin_user_id` → `users` (set null; `orgs_admin_user_id_fkey`, added once both tables exist) | `ix_orgs_plan_version_id` | `id` is the org |
| `users` | PK `id`; `users_role` `role` in `admin`, `member` | `org_id` → `orgs` (restrict) | `users_email` unique on `lower(email)`; `ix_users_org_id` | `org_id` is the org |
| `identities` | PK (`provider`, `provider_user_id`); `identities_provider` `provider` in `google`, `github` | `user_id` → `users` (cascade) | `ix_identities_user_id` | its user is visible |
| `invites` | PK `id`; `token_hash` unique | `org_id` → `orgs` (cascade) | `invites_one_open` unique on (`org_id`, `lower(email)`) where `accepted_at` is null; `ix_invites_org_id` | `org_id` is the org |
| `installs` | PK `id`; `installs_surface` `surface` in `desktop`, `cli` | `user_id` → `users` (cascade) | `installs_user_machine` unique on (`user_id`, `machine_id`) where `revoked_at` is null; `ix_installs_user_id` | its user is visible |
| `tokens` | PK `id`; `token_hash` unique | `install_id` → `installs` (cascade) | `ix_tokens_install_id` | its install is visible |
| `device_codes` | PK `device_code_hash`; `user_code` unique; `device_codes_surface` `surface` in `desktop`, `cli`; `device_codes_one_answer` not both `approved_at` and `denied_at`; `interval` 5 by default | `install_id` → `installs` (cascade) | none | none: read before anyone is signed in |
| `rrotors` | PK `id`; `install_id` unique; `token_hash` unique; `rrotors_mode` `mode` in `hosted`, `local`, `self`; `rrotors_local_install` an install exactly when `local`; `rrotors_self_address` `public_url` and `name` exactly when `self`; `rrotors_hosted_machine` `size` and `name` exactly when `hosted`; `rrotors_size` `size` in `small`, `medium`, `large`; `month_seconds` and `seq` 0 by default; `metered_at` a hosted machine's metered-up-to instant, empty until its first tick | `user_id` → `users` (cascade); `install_id` → `installs` (cascade) | `rrotors_hosted_name` unique on (`user_id`, `name`) where hosted; `rrotors_self_url` unique on (`user_id`, `public_url`) where self; `rrotors_self_host` on `public_url` where self; `ix_rrotors_user_id` | its user is visible |
| `runtime_keys` | PK `id`; `key_hash` unique; `calls` 0 by default | `rrotor_id` → `rrotors` (cascade); `user_id` → `users` (cascade) | `ix_runtime_keys_rrotor_id`; `ix_runtime_keys_user_id` | its user is visible |
| `machine_months` | PK (`rrotor_id`, `month`), no foreign key on `rrotor_id`; `cost_micros` and `charge_micros` 0 by default | `org_id` → `orgs` (cascade) | `ix_machine_months_org_id` | `org_id` is the org |
| `meter_events` | PK `id`; `meter_events_cents` `cents` > 0 | `org_id` → `orgs` (cascade) | `ix_meter_events_org_id` | `org_id` is the org |
| `models` | PK `id` | `user_id` → `users` (cascade); `org_id` → `orgs` (restrict) | `ix_models_org_id`; `ix_models_user_id` | `org_id` is the org |
| `model_versions` | PK `id`; `model_versions_version` unique (`model_id`, `version`); `model_versions_commit` unique (`model_id`, `commit_sha`) | `model_id` → `models` (cascade) | `ix_model_versions_model_id` | its model is visible |
| `deployments` | PK (`rrotor_id`, `model_version_id`); `active` true by default | `rrotor_id` → `rrotors` (cascade); `model_version_id` → `model_versions` (cascade) | `ix_deployments_model_version_id` | its version is visible |
| `runs` | PK `id`; `runs_caller` `caller` in `routine`, `claude`, `panel`, `test` | `model_version_id` → `model_versions` (cascade); `rrotor_id` → `rrotors` (cascade) | `ix_runs_model_version_id`; `ix_runs_rrotor_id` | its version is visible |
| `approvals` | PK `id` | `run_id` → `runs` (cascade) | `ix_approvals_run_id` | its run is visible |
| `github_installations` | PK `id`; `user_id` unique; `installation_id` unique | `user_id` → `users` (cascade) | none beyond the unique ones | its user is visible |
| `routine_triggers` | PK `id`; `routine_triggers_status` `status` in `ok` (the default), `broken` | `user_id` → `users` (cascade); `model_id` → `models` (set null) | `ix_routine_triggers_model_id`; `ix_routine_triggers_user_id` | its user is visible |
| `model_events` | PK `id` | `model_id` → `models` (cascade); `routine_trigger_id` → `routine_triggers` (cascade) | `ix_model_events_model_id`; `ix_model_events_routine_trigger_id` | its model is visible |
| `oauth_clients` | PK `id`; `oauth_clients_auth_method` `auth_method` in `none`, `client_secret_post`, `client_secret_basic`; `oauth_clients_secret` a `secret_hash` exactly when not `none`; `oauth_clients_redirect_uris` at least one | none | none | none: a client is no org's |
| `oauth_codes` | PK `code_hash` | `client_id` → `oauth_clients` (cascade); `user_id` → `users` (cascade); `grant_id` → `connector_grants` (cascade) | `ix_oauth_codes_client_id`; `ix_oauth_codes_user_id` | its user is visible |
| `connector_grants` | PK `id` | `user_id` → `users` (cascade); `client_id` → `oauth_clients` (cascade) | `connector_grants_user_client` unique on (`user_id`, `client_id`) where `revoked_at` is null; `ix_connector_grants_client_id`; `ix_connector_grants_user_id` | its user is visible |
| `connector_tokens` | PK `id`; `token_hash` unique; `connector_tokens_kind` `kind` in `access`, `refresh` | `grant_id` → `connector_grants` (cascade) | `ix_connector_tokens_grant_id` | its grant is visible |

**Row-level security.** Each of the 22 tables marked above has row-level security enabled and forced (so it binds the server's own role, which is no superuser), and one policy, `tenant`. A request made with an install's token or an OAuth access token, and a runtime's own link, heartbeat and introspection, run in their org: `glyphh.org_id` is set for the transaction (`db/tenancy.py`). With it set, `tenant` shows only that org's rows: the org itself, rows whose `org_id` is it, and rows reached through a visible parent (a user, an install, a grant, a model, a version or a run). With it unset (sign-in, the connector's OAuth endpoints, Stripe's webhook, the schema step, the minute tick's sweeps and the few operations that cross orgs on purpose, such as joining another org) every row is seen. The tables marked none (`mods`, `plans`, `plan_versions`, `fly_rates`, `device_codes`, `oauth_clients`) belong to no org.

## Not built yet

Nothing in this section works today.

| Area | What |
|---|---|
| What the paid tiers are sold on | Centralised precedent-store sync across instances (`sync`), multi-node HA (`ha`), SSO/SAML (`sso`), RBAC, audit logs: only the licence's flags ship |
| The licensing engine | The key, rrotor's start, its three enforcement modules, the telemetry heartbeat and the Stripe-driven key issuance in [pricing.md](pricing.md); how today's licences differ is its [Against what is built](pricing.md#against-what-is-built) |
| The platform's Approvals page, and approvals in Claude | Nothing reads `/v1/approvals/stream` yet; an answer is `POST /v1/approvals/{id}` |
| Approvals email | When nobody is watching: needs a mail provider (`approvals.notified_at` stays empty) |
| The local runtime from the plugin | The server issues its token (`POST /v1/runtime/local`) and takes its link; no plugin installs or starts rrotor locally. Then Windows (WSL2) and Linux (Docker or Podman) |
| Routines as the runner | A Claude routine (schedule, API trigger, GitHub event) calling the runtime's MCP |
| The live panel | A run as it happens (steps, log, approvals), an MCP App served by the runtime's own MCP |
| Hosted storage | Growing a machine's volume (`POST /v1/runtime/storage`); every GB is already metered |
| Reconciling hosting | Each month, by hand: `machine_months.cost_micros` against Fly's invoice for the runtimes app; a gap means a rate row is out of date |
| Air-gapped sign-in | An air-gapped runtime takes runtime keys only (`RROTOR_KEYS_SHA256`); no Glyphh sign-in without the link |
| Rate limiting | None anywhere, the OAuth endpoints included |
| OAuth client ID metadata documents | Registration is RFC 7591 only |
| Programs, then the gateway | Programs (coding-agent CLIs on the runtime), then the gateway. Remote Control needs a full claude.ai login on the machine, which [Anthropic's terms](#anthropics-terms) rule out |

**Open**

- The database's reset on every deploy, to turn off (`GLYPHH_RESET_DATABASE` out of `fly.toml`) before paid customers or Enterprise grants.
- The hosted machines each plan allows and the markups on Fly's rates: placeholders marked TBD in `db/seed.py`.
- Whether Fly keeps a deleted volume's snapshots.
