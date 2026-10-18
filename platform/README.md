# platform

The Glyphh platform: the one door. A person signs in here, has a runtime, makes the keys that call it, answers
approvals, pays, and runs their org. Everything it shows comes from the server's API; it keeps nothing of its own.

Three parts, kept simple:

| Part | Repo | What |
|---|---|---|
| **Platform** | `glyphh-ai/platform` (this) | The one web app: every page a person sees |
| **Server** | `glyphh-ai/server` | The API and the authorization server: accounts, plans, Stripe, licences, provisioning, the record. Renders nothing |
| **Runtimes** | `glyphh-ai/rrotor` | One rrotor per person, reached directly at `https://<machine>.glyphh.app` (REST and MCP); nothing of Glyphh's on the data path |

The UI is built to Chris's design (the Glyphh Style canvas: ngrok's style, Glyphh's palette, light and dark in the
platform, dark only on the sign-in pages). The contract it builds to is the server's `docs/architecture.md` (the API table and the section **The platform**);
what is not built yet is the server's `docs/roadmap.md`.

## How a person gets in

1. **Sign in once, here.** The platform is a confidential OAuth client of the server (`PLATFORM_CLIENT_ID` and
   `PLATFORM_CLIENT_SECRET`, registered once at `POST {server}/oauth/register`). Sign in goes to the server's
   `/oauth/authorize`, which sends the browser straight back to this platform's `/authorize` page (below) to pick
   Google or GitHub; the tokens come back to `{PLATFORM_URL}/auth/callback` and live in a sealed, HttpOnly cookie.
   The browser never holds a token.
2. **Connect Claude once, to the runtime.** Getting started walks a new account through it. Home shows the one connector URL, `https://<machine>.glyphh.app/mcp`.
   Adding it in Claude runs OAuth against the same server, which lands on `/authorize` here; signed in already,
   that is one Allow click.
3. **Apps** use a runtime key (made on Keys, shown once) as the bearer at the runtime's address.

## The routes the server sends a browser to

The server renders no page. In every flow it redirects the browser here with signed values in the query; the page
reads what it needs from the server and answers with the server call named. A consent is tied to the browser that
started the flow by the server's own short-lived cookie (`glyphh_signin`, ten minutes, on the server's domain), so
each answer is a top-level navigation (a link, not a fetch).

| Route | Arrives from | Shows | Answers with |
|---|---|---|---|
| `/device?code=` | `GET {server}/v1/device?code=` (the link Claude shows; without a code, ask for it and reload with it) | The code, to match against Claude's; Continue with each provider from `GET {server}/auth/providers` → link to `GET {server}/auth/{provider}/start?code=` | — |
| `/device/approve?consent=` | the provider's callback | `GET {server}/auth/consent?consent=` → `{kind: "device", code, name, surface, email}`: "<name> (<surface>) wants to sign in as <email>" | Link to `GET {server}/auth/approve?consent=&decision=approve` or `deny` |
| `/device/done?result=approved\|denied` | `/auth/approve` | "Signed in. Go back to Claude." or "Nothing was signed in." | — |
| `/authorize?oauth=&client=` | `GET {server}/oauth/authorize` (a client's request, already checked) | "<client> wants to use your Glyphh account"; Continue with each provider → link to `GET {server}/auth/{provider}/start?oauth=` | — |
| `/allow?consent=` | the provider's callback | `GET {server}/auth/consent?consent=` → `{kind: "oauth", client, returns_to, resource, email}`: Allow or Deny | Link to `GET {server}/auth/oauth/allow?consent=&decision=allow` or `deny` (the server sends the browser on to the client) |
| `/account?linked=<provider>` | a provider link's callback | The account, the provider now linked | — |
| `/github?installed=<login>` | the GitHub App's callback | "Glyphh's GitHub App is installed on <login>" | — |
| `/billing?done=1` | Stripe's checkout and portal | Billing, refreshed | — |
| `/error?code=&message=&trace=` | any refusal in a browser flow | The message, and the trace id to quote | — |

A refusal from `GET {server}/auth/consent` (the consent expired, or another browser) is JSON, `{"error": {"code",
"message", "trace_id"}}`; show it the same way as `/error`.

## The platform's own pages

Each reads the server with the session's access token (`Authorization: Bearer`), from a route handler, never the
browser.

| Page | Server calls | Does |
|---|---|---|
| Getting started | `GET /v1/runtime`, `GET /v1/runtimes/self` (each self-hosted runtime's state, version, last heartbeat) | The SDKs and the Claude plugin to copy; where rrotor runs: Glyphh hosted (Start, as Home), or Docker Compose, Helm or Terraform (AWS, GCP): register (`POST /v1/runtimes/self {name, public_url}`; the token is shown once), then the option's settings filled in from the answer's `env` and the connector URL `https://<host>/mcp`. Rotate a token (`POST /v1/runtimes/self/{id}/token`, shown once), delete (`DELETE /v1/runtimes/self/{id}`), issue an offline licence for an air-gapped runtime (`POST /v1/runtimes/{id}/offline-licence {days}`, set as `RROTOR_LICENCE`) |
| Home | `GET /v1/runtime` (address, state, this month's hours, `paused`), `GET /v1/me` | Start (`POST /v1/runtime/start`), stop (`POST /v1/runtime/stop`), copy the connector URL `{address}/mcp` |
| Keys | `GET /v1/runtime/keys` | Make one (`POST /v1/runtime/keys {name}`; the key is shown once), revoke (`DELETE /v1/runtime/keys/{id}`) |
| Approvals | `GET /v1/approvals`, live from `GET /v1/approvals/stream` (server-sent events `approval`, `answered`) | Approve or decline (`POST /v1/approvals/{id} {answer}`) |
| Models | `GET /v1/models` (versions by commit, where each is active) | Delete (`DELETE /v1/models/{id}`) |
| Billing | `GET /v1/me` (plan, seats, what is used), `GET /v1/plans`, `GET /v1/addons` | Upgrade (`POST /v1/billing/checkout` → Stripe), change plan or seats, add or remove Ada (`POST /v1/billing/addons/preview`, then `POST`/`DELETE /v1/billing/addons`), portal (`POST /v1/billing/portal`) |
| Org | `GET /v1/org`, `/v1/org/members`, `/v1/org/invites` | Rename, invite (`POST /v1/org/invites`), remove a member or an invite |
| Account | `GET /v1/me`, `GET /v1/installs` | Rename (`PATCH /v1/me`), link a provider (`POST /v1/me/identities` → its link), unlink, sign out an install (`DELETE /v1/installs/{id}`) |

## Settings

| Variable | What |
|---|---|
| `GLYPHH_SERVER_URL` | The server (`https://api.glyphh.ai`; locally a tunnel or `http://localhost:8080`) |
| `PLATFORM_URL` | This app's own address; the server's `GLYPHH_PLATFORM_URL` must be the same |
| `PLATFORM_CLIENT_ID`, `PLATFORM_CLIENT_SECRET` | The platform's OAuth client at the server |
| `SESSION_SECRET` | 32+ random bytes, base64: seals the session cookie |

## Develop

Node 22 or later.

```bash
npm install
cp .env.example .env        # then fill it in, or use the fake server's values below
npm run fake-server         # a stand-in Glyphh server on FAKE_SERVER_PORT (8090), with sample data
npm run dev                 # the platform on PLATFORM_URL, with hot reload
npm test                    # the route handlers, the API calls and every page, against fake servers
npm run typecheck
npm run build && npm start  # production: dist/client is served by the route handlers' server
```

With the fake server, `.env` is `GLYPHH_SERVER_URL=http://localhost:8090`, `PLATFORM_URL=http://localhost:3100`,
any client id and secret, and `SESSION_SECRET` from `openssl rand -base64 32`. Logging in then runs the whole OAuth
round trip and lands on Home.

## How the code is laid out

| Path | What |
|---|---|
| `server/` | The route handlers (Hono on Node): `/auth/login`, `/auth/callback`, `/auth/logout`, `/auth/session`, `/auth/providers` and `/api/v1/*`, which calls the server with the session's token, refreshing it when it runs out. `seal.ts` seals the cookie (AES-256-GCM); `oauth.ts` is the token endpoint |
| `src/styles/` | `tokens.css`: every colour, size and font, one set per theme (`dark`, `light`, `dark-hc`, `light-hc`) on `[data-theme]`; `base.css`: document defaults and the thin scroll bar |
| `src/ui/` | The component library: Button, Chip, Card, TextField, Switch, ProgressBar, CopyField, CodeBlock, Menu (with submenus), Dialog, Toast, the empty, loading and error states, Logo, Avatar. Each is a folder with its component and its CSS Module, and nothing in it knows about the API |
| `src/layout/` | The app shell (sidebar, breadcrumb bar, phone drawer), the account menu with its themes, page headers, settings sections, and the sign-in card |
| `src/api/` | The server's types, the client for `/api/v1`, and one TanStack Query hook per read and write |
| `src/pages/` | One folder per page; Billing's parts live in `pages/settings/billing/` |
| `src/routes/` | The route table, with each page's breadcrumb |
| `dev/fake-server.ts` | A stand-in Glyphh server for working locally |

## Standards

- Plain British English in the UI, short and concrete. Labels never darker than `#999` on a dark background.
- Tests for every route handler and API call; the pages against a fake server.
- Commits: one step each; Claude's end with its `Co-Authored-By` line.
