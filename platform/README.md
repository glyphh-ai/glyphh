# platform

The Glyphh platform, https://platform.glyphh.ai: the one web app a person uses. They sign in, register the runtimes they run,
make the keys that call them, pay and run their org. Every page shows the server's API; the platform stores nothing.

| Part | Repo | What |
|---|---|---|
| Platform | `glyphh-ai/platform` (this) | Every page a person sees |
| Server | `glyphh-ai/server` | The API and the authorization server, https://api.glyphh.ai. Renders no page |
| Runtimes | `glyphh-ai/rrotor` | rrotor: self-hosted at its own address, `https://<host>` (`RROTOR_PUBLIC_HOST`); Glyphh-hosted at `https://<machine>.glyphh.app` only while hosting is on (it is off). Claude and apps call it directly |

The contract is the server's `docs/architecture.md` (the API table and **The platform**); prices and plan rules are
its `docs/pricing.md`.

## Sign-in

1. **The platform** is a confidential OAuth client of the server (`PLATFORM_CLIENT_ID`, `PLATFORM_CLIENT_SECRET`,
   registered once at `POST {server}/oauth/register`). `/login` starts `/auth/login`, which goes to
   `{server}/oauth/authorize`; the server sends the browser to `/authorize` here to pick Google or GitHub, and the
   tokens come back to `{PLATFORM_URL}/auth/callback`. They live in a sealed, HttpOnly cookie; the browser never holds
   a token.
2. **Claude** connects to a runtime at `https://<host>/mcp` (or, with hosting on, `https://<machine>.glyphh.app/mcp`). Its OAuth runs
   against the same server and lands on `/authorize` here; already signed in, it is one Allow.
3. **Apps** call a runtime with a runtime key (made on API Keys, shown once) as the bearer.

## Routes the server sends a browser to

The server redirects here with signed values in the query. A consent is tied to the browser that started it by the
server's `glyphh_signin` cookie (ten minutes, on the server's domain), so each answer is a link, not a fetch.

| Route | Arrives from | Shows | Answers with |
|---|---|---|---|
| `/device?code=` | `GET {server}/v1/device?code=` (without a code, asks for it) | The code, to match Claude's; a button per provider from `GET {server}/auth/providers` | Link to `GET {server}/auth/{provider}/start?code=` |
| `/device/approve?consent=` | the provider's callback | `GET {server}/auth/consent` → `{kind: "device", code, name, surface, email}` | Link to `GET {server}/auth/approve?consent=&decision=approve` or `deny` |
| `/device/done?result=approved\|denied` | `/auth/approve` | "Signed in" or "Nothing was signed in" | — |
| `/authorize?oauth=&client=` | `GET {server}/oauth/authorize` | "<client> wants to use your Glyphh account"; a button per provider | Link to `GET {server}/auth/{provider}/start?oauth=` |
| `/allow?consent=` | the provider's callback | `GET {server}/auth/consent` → `{kind: "oauth", client, returns_to, resource, email}` | Link to `GET {server}/auth/oauth/allow?consent=&decision=allow` or `deny` |
| `/account?linked=<provider>` | a provider link's callback | Redirects to `/settings/profile`, which confirms the link | — |
| `/billing?done=1` | Stripe Checkout and the portal | Redirects to `/settings/billing`, read afresh | — |
| `/github?installed=<login>` | the GitHub App's callback | "Glyphh's GitHub App is installed on <login>" | — |
| `/error?code=&message=&trace=` | any refusal in a browser flow | The message and the trace id | — |

A refusal from `GET {server}/auth/consent` is JSON, `{"error": {"code", "message", "trace_id"}}`, shown like `/error`.

## Hosting off, and features not built

The server's `GLYPHH_HOSTING` is off by default. The platform reads it from the server and hard-codes nothing:

- **Hosting is off** when `GET /v1/rates` is refused with `E_UNAVAILABLE` `reason: hosting_off` (503, as the server
  does; read as no rates, never shown as an error), or answers `{"hosting": "off"}` or an empty `plans` map; never
  from the plans. A plan's `limits.machines` is its **runtime nodes**: every runtime linked for the org, hosted or
  self-hosted (Free 1, Pro 3, Team 10, Enterprise unlimited), shown as "runtime nodes" with hosting on or off.
  With hosting off, Machines is gone from the sidebar and `/machines` opens Add a runtime (`/?add=1`), which offers
  this computer, Docker, Helm and Terraform only; Home has no Start, no cost and no link to Machines; Billing, Plans and Usage
  say nothing of hosted machines, rates or hosting cost. A hosted machine route the server refuses with `E_UNAVAILABLE` `reason: hosting_off` says to run rrotor
  yourself. With hosting on, every page is as before.
- **A feature not built** is shown as "Coming soon", never as included. A plan's `features` is a boolean per feature
  with a separate `built` map beside it (`{"features": {"sync": true, …}, "built": {"sync": false, "ha": false,
  "offline": true, "sso": false}}`); `{"sync": {"included": true, "built": false}}` is read alike. Sync, HA, SSO, roles
  and audit logs missing from `built` (or with no map) are not built; roles and audit logs follow `sso` when the server
  does not name them. A plan's `limits.precedents` is per node, hosted or self-hosted (Free 5,000, Pro 50,000, Team
  500,000), shown as "precedents per node" with hosting on or off. Plans are listed, priced and bought as before.

## Ada Cloud

With the server's `GLYPHH_ADA_CLOUD` on, `GET /v1/me` answers `ada_cloud: true` and the platform is Ada's: no
runtimes, machines, licence, rrotor's logs, Add a runtime or self-hosting (`/logs`, `/licence`, `/machines`,
`/getting-started` go Home). Off, or on an older server without the field, every page is as below. The browser calls
`/api/ada/v1/*` here; the route handler adds the session's token and passes the call to Ada's host
(`GLYPHH_ADA_URL`, `https://ada.glyphh.ai`), which takes a Glyphh sign-in as the account API does. An import's file goes
`PUT /api/ada/v1/uploads/<link>`, streamed to the upload link without a token (the link is its own credential).

| Route | Page | Ada calls | Does |
|---|---|---|---|
| `/` | Home | `GET /v1/models`, `GET /v1/usage` | The models, the precedents and this month's requests against the plan (and what happens past the month), the connector URL (`{server}/mcp`) to add in Claude |
| `/models` | Models | `GET /v1/models` | Each model's live version and precedents |
| `/models/new` | New model | `POST /v1/models {name, spec}` | A spec editor, checked as typed (the cloud's bounds), from an example or blank |
| `/models/:name` | A model, a tab each (`?tab=`) | `GET /v1/models/{name}`, `…/versions`, `…/settings`, `GET /v1/jobs/{id}` | **Spec**: the live spec, a new version (`PUT …/spec`), versions and Make live (`POST …/versions/{n}/activate`). **Settings**: every lever, saved as a version (`PATCH …/settings`). **Import**: a CSV (each column mapped to a role, an outcome, ts, id or skipped) or JSON Lines (`POST …/imports`, then the file to its link), with progress. **Try it**: a form from the spec, `POST /v1/decide`: the answer, confidence, whether a person should decide, the precedents. **Backtest**: candidates (settings changed, or another version) on the newest held-out cases (`POST …/backtest`), the results and Make live (with the backtest kept on the version). **Export**: JSON Lines or SQLite (`POST …/export`), then its download link. Delete after typing the name |
| `/keys` | API Keys | `GET`, `POST /v1/keys`, `DELETE /v1/keys/{id}` | Cloud keys: name, expiry, clearance (0 to 1); shown once; revoke |
| `/usage` | Usage | `GET /v1/usage`, `GET /v1/models`, `GET /v1/me` | `{plan, month, resets_at, models, precedents: {used, max}, requests: {used, max, over, overage}, requests_per_second}`: precedents and the month's requests against the plan's (the month, UTC, and when it starts again); past it, Pro and Team are billed ($1 per 10,000, the plan's `overage_cents_per_10k`), Free stops until it turns, with the way to upgrade; the calls a second; each model's precedents |

Ada's plan refusals are shown on every Ada page in the server's words with the way on (`AdaErrorNotice`): 429 `E_RATE` (the
plan's calls a second; Retry-After, passed back by the route handlers), 403 `E_LIMIT` `requests` (Upgrade to the plan the
server names, or Talk to us) and `precedents` (the plans). With Ada Cloud on the plan cards show each plan's cloud caps
(`cloud` on `GET /v1/plans`) in place of runtime nodes and precedents per node.

Billing, Plans, Members, Profile, Installs and General stay; a plan's runtime nodes, precedents per node and runtime
features (sync, HA, offline licences) are not shown.

## Pages

The browser calls `/api/v1/*` here; the route handler adds the session's token and passes the call to `{server}/v1/*`.

| Route | Page | Server calls | Does |
|---|---|---|---|
| `/machines` | Machines (hosting on only) | `GET /v1/runtimes`, `GET /v1/me`, `GET /v1/plans`, `GET /v1/rates` | Each hosted machine's size, state, address, connector URL and cost this month. Make one (`POST /v1/runtimes {name, size}`), start, stop, restart (`POST /v1/runtimes/{id}/start`, `stop`, `restart`), delete after typing its name (`DELETE /v1/runtimes/{id}?confirm=<name>`). `E_LIMIT` `reason: machines` links to Billing. On Free, the plans with hosting and their rates |
| `/` | Runtimes | `GET /v1/runtime`, `GET /v1/runtimes/self`, `GET /v1/me`, `GET /v1/plans`, `GET /v1/rates` | The first hosted machine: address, state, cost this month, connector URL. Start (`POST /v1/runtime/start`), stop (`POST /v1/runtime/stop`). Self-hosted runtimes: rotate the token (`POST /v1/runtimes/self/{id}/token`), delete (`DELETE /v1/runtimes/self/{id}`), offline licence on Enterprise (`POST /v1/runtimes/{id}/offline-licence {days}`). **Add a runtime** (a dialog; `/?add=1` opens it on load, and the old `/getting-started` redirects there): where rrotor runs, this computer, Docker, Helm or Terraform, each with what it needs (register, `POST /v1/runtimes/self {name, public_url}`, token shown once; the command filled from the answer's `env`, nothing to clone, pasteable in zsh and bash with no `#` lines, ending with a `curl …/healthz` check: this computer is the image alone with `docker run` on port 7777 (host 127.0.0.1 by default; localhost and IPs allowed for it only), no HTTPS so no Claude connector, the SDKs take `GLYPHH_RUNTIME_URL=http://<host>:7777`; Docker is `curl -fsSL https://glyphh.ai/install.sh \| RROTOR_RUNTIME_ID=… sh`, or the image alone with `docker run`; Helm installs the released chart; Terraform's module is `git::https://github.com/glyphh-ai/glyphh.git//deploy/terraform/<cloud>?ref=main`; on a paid plan, how to set the licence key, as text beside the block, for an air-gapped node only); with hosting on, Glyphh hosted first (make a first machine, `POST /v1/runtimes {name, size}`, or start it, `POST /v1/runtimes/{id}/start`). Then the connector URL `https://<host>/mcp` and the SDK and plugin install commands. Closing it reads the runtimes again |
| `/keys` | API Keys | `GET /v1/runtime/keys` | Make one (`POST /v1/runtime/keys {name, expires_in_days?}`: 7, 30, 60, 90 or 365 days, or never; shown once), revoke (`DELETE /v1/runtime/keys/{id}`), delete a revoked or expired one (`DELETE /v1/runtime/keys/{id}/record`) |
| `/models` | Models | `GET /v1/models` | Each Ada model's versions by commit and where each is active. Delete (`DELETE /v1/models/{id}`) |
| `/settings/general` | General | `GET /v1/org`, `GET /v1/me` | Rename the org (`PATCH /v1/org`) |
| `/settings/billing` | Billing | `GET /v1/me`, `GET /v1/plans`, `GET /v1/rates` | The plan, its renewal and hosting this month; the plans above it; the hosted machine rates (hosting on). Invoices and payment (`POST /v1/billing/portal`) |
| `/settings/plans` | Plans (full window) | `GET /v1/me`, `GET /v1/plans`, `GET /v1/rates` | Choose a plan: Stripe Checkout without a subscription (`POST /v1/billing/checkout {plan}`), else a prorated change (`POST /v1/billing/plan {plan}`). Enterprise is Talk to us (`mailto:sales@glyphh.ai`) |
| `/settings/licence` | Licence | `GET /v1/me`, `GET /v1/license/keys` | The key the org's runtimes are sent now (`license_key`), masked with Reveal and Copy: its tier, runtime nodes, precedents per node, sync and expiry. How it reaches rrotor: on its own at the link and the daily heartbeat, renewed at each payment; an air-gapped node takes it as `GLYPHH_LICENSE_KEY` or `/etc/rrotor/license.key`. Older keys with their state (live, expired, revoked). Free has none: Community, 1 node, 5,000 precedents, no sync |
| `/settings/usage` | Usage | `GET /v1/me`, `GET /v1/plans`, `GET /v1/rates`, `GET /v1/runtime/keys`, `GET /v1/license/nodes` | The fullest node's precedents against the plan's per node; runtime nodes "N of M" and each node (runtime, node id, role, version, precedents, last seen), over the plan shown, never blocking; hosting this month by machine (hosting on), each API key's calls |
| `/settings/logs` | Logs | `GET /v1/telemetry/logs?runtime&node&level&since&text&limit&cursor`, `GET /v1/telemetry/audit?runtime&node&kind&since&limit&cursor`, `GET /v1/telemetry/metrics`, `GET /v1/license/nodes` | What the org's runtimes send with rrotor's opt-in server logs (`RROTOR_SERVER_LOGS=on`). Tabs Logs, Audit and Metrics (`?tab=audit`, `?tab=metrics`). Logs and Audit: newest first, filtered by runtime, node and time (`since`), with level and above and words (`text`) on Logs and `kind` (run.call, …) on Audit; 50 a page, Load older by the answer's `next_cursor`; a cursor refused (422 `reason: cursor`) starts again from the newest. An audit event's actor, route and outcome come from its flattened attributes (`actor.type`, `via`, `outcome.status`). Metrics: the latest point of each series, gathered by node: `rrotor.runs`, `rrotor.run.seconds`, `rrotor.precedents` against `rrotor.precedents.cap`, `rrotor.link.state`, `rrotor.drain.dropped`; any other series listed as it came. Read again every 10 seconds while open; fields the platform does not know are kept and shown under Details. Audit says rrotor records it on Enterprise (below, the events arrive as log lines). With nothing sent, rrotor's default: the data stays on the rrotor; recommended, your own OpenTelemetry collector (`OTEL_EXPORTER_OTLP_ENDPOINT`, rrotor's self-hosting docs); or `RROTOR_SERVER_LOGS=on`, which sends logs, metrics, traces and audit events to Glyphh, never inputs, results or client addresses |
| `/settings/members` | Members | `GET /v1/org`, `GET /v1/org/members`, `GET /v1/org/invites`, `GET /v1/me` | Invite (`POST /v1/org/invites {email}`, valid seven days), cancel an invite (`DELETE /v1/org/invites/{id}`), remove a member (`DELETE /v1/org/members/{id}`) |
| `/settings/profile` | Profile | `GET /v1/me` | Rename (`PATCH /v1/me`), link a provider (`POST /v1/me/identities` → its link), unlink (`DELETE /v1/me/identities/{provider}`) |
| `/settings/installs` | Installs | `GET /v1/installs` | Sign out an install (`DELETE /v1/installs/{id}`) |

The platform's own routes: `/login`, `/auth/login`, `/auth/callback`, `/auth/logout` (POST), `/auth/session`,
`/auth/providers` (the server's, passed through) and `/api/v1/*`. Writes must come from this origin.

## Settings

| Variable | What |
|---|---|
| `GLYPHH_SERVER_URL` | The server: `https://api.glyphh.ai` |
| `GLYPHH_ADA_URL` | Ada Cloud's host of the server (default `https://ada.glyphh.ai`) |
| `PLATFORM_URL` | This app's own address; the server's `GLYPHH_PLATFORM_URL` must match |
| `PLATFORM_CLIENT_ID`, `PLATFORM_CLIENT_SECRET` | The platform's OAuth client at the server |
| `PLATFORM_CLIENT_NAME` | The `client_name` it registered with (default `Glyphh`), so its own consent pages are recognised |
| `SESSION_SECRET` | 32+ random bytes, base64: seals the session cookie |
| `PORT` | Where it listens (default 3000) |

Production is the Fly app `glyphh-ai-app` (`fly.toml`), deployed by CI (`.github/workflows/ci.yml`) on a merge to
main.

## Develop

Node 22 or later.

```bash
npm ci
cp .env.example .env        # then set PLATFORM_CLIENT_ID, PLATFORM_CLIENT_SECRET and SESSION_SECRET
npm run fake-server         # a stand-in server with sample data on FAKE_SERVER_PORT (default 8080); hosting off as
                            # the server has it, FAKE_HOSTING=on to turn it on; no telemetry, as rrotor sends none by
                            # default, FAKE_SERVER_LOGS=on for sample logs, audit events and metrics; FAKE_ADA=on
                            # for Ada Cloud (its API at /ada/v1)
npm run dev                 # the platform on PLATFORM_URL (default http://localhost:3000), hot reload
npm test                    # route handlers, API calls and every page, against fake servers
npm run typecheck
npm run build && npm start  # production build
```

With the fake server, any client id and secret will do; `SESSION_SECRET` from `openssl rand -base64 32`. Logging in
runs the whole OAuth round trip and lands on Home.

## Layout

| Path | What |
|---|---|
| `server/` | The route handlers (Hono on Node): `app.ts` the routes, `oauth.ts` the calls to the token endpoint, `seal.ts` the cookie (AES-256-GCM), `config.ts` the settings |
| `src/api/` | The server's types, the `/api/v1` client, one TanStack Query hook per read and write |
| `src/pages/` | One folder per page; sign-in and consent in `pages/flows/`, Settings in `pages/settings/` |
| `src/routes/` | The route table and the two layouts with their sidebars |
| `src/layout/` | The app shell, sidebar, top bar, account menu, page headers, settings sections, the sign-in card |
| `src/ui/` | The component library, a folder each with its CSS Module; nothing in it knows the API |
| `src/styles/` | `tokens.css` (every colour, size and font for the `dark`, `light`, `dark-hc` and `light-hc` themes), `base.css` |
| `dev/fake-server.ts` | The stand-in server |

## Standards

- Plain British English in the UI, short and concrete. Labels never darker than `#999` on a dark background.
- Tests for every route handler and API call; the pages against a fake server.
- Commits: one step each; Claude's end with its `Co-Authored-By` line.
