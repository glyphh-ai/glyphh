# platform

The Glyphh platform, https://platform.glyphh.ai: the one web app a person uses. They sign in, run their machines,
make the keys that call them, pay and run their org. Every page shows the server's API; the platform stores nothing.

| Part | Repo | What |
|---|---|---|
| Platform | `glyphh-ai/platform` (this) | Every page a person sees |
| Server | `glyphh-ai/server` | The API and the authorization server, https://api.glyphh.ai. Renders no page |
| Runtimes | `glyphh-ai/rrotor` | rrotor: hosted at `https://<machine>.glyphh.app`, or self-hosted at `https://<host>`. Claude and apps call it directly |

The contract is the server's `docs/architecture.md` (the API table and **The platform**); prices and plan rules are
its `docs/pricing.md`.

## Sign-in

1. **The platform** is a confidential OAuth client of the server (`PLATFORM_CLIENT_ID`, `PLATFORM_CLIENT_SECRET`,
   registered once at `POST {server}/oauth/register`). `/login` starts `/auth/login`, which goes to
   `{server}/oauth/authorize`; the server sends the browser to `/authorize` here to pick Google or GitHub, and the
   tokens come back to `{PLATFORM_URL}/auth/callback`. They live in a sealed, HttpOnly cookie; the browser never holds
   a token.
2. **Claude** connects to a runtime at `https://<machine>.glyphh.app/mcp` (or `https://<host>/mcp`). Its OAuth runs
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

## Pages

The browser calls `/api/v1/*` here; the route handler adds the session's token and passes the call to `{server}/v1/*`.

| Route | Page | Server calls | Does |
|---|---|---|---|
| `/getting-started` | Getting started | `GET /v1/plans`, `GET /v1/runtimes`, `GET /v1/runtimes/self`, `GET /v1/me` | The SDK and plugin install commands. Where rrotor runs: hosted (make a first machine, `POST /v1/runtimes {name, size}`, or start it, `POST /v1/runtimes/{id}/start`) or Docker Compose, Helm or Terraform (register, `POST /v1/runtimes/self {name, public_url}`, token shown once; the option's settings from the answer's `env`; connector URL `https://<host>/mcp`). Self-hosted runtimes: rotate the token (`POST /v1/runtimes/self/{id}/token`), delete (`DELETE /v1/runtimes/self/{id}`), offline licence on Enterprise (`POST /v1/runtimes/{id}/offline-licence {days}`) |
| `/machines` | Machines | `GET /v1/runtimes`, `GET /v1/me`, `GET /v1/plans`, `GET /v1/rates` | Each hosted machine's size, state, address, connector URL and cost this month. Make one (`POST /v1/runtimes {name, size}`), start, stop, restart (`POST /v1/runtimes/{id}/start`, `stop`, `restart`), delete after typing its name (`DELETE /v1/runtimes/{id}?confirm=<name>`). `E_LIMIT` `reason: machines` links to Billing. On Free, the plans with hosting and their rates |
| `/` | Home | `GET /v1/runtime`, `GET /v1/me` | The first machine: address, state, cost this month, connector URL. Start (`POST /v1/runtime/start`), stop (`POST /v1/runtime/stop`) |
| `/keys` | API Keys | `GET /v1/runtime/keys` | Make one (`POST /v1/runtime/keys {name, expires_in_days?}`: 7, 30, 60, 90 or 365 days, or never; shown once), revoke (`DELETE /v1/runtime/keys/{id}`), delete a revoked or expired one (`DELETE /v1/runtime/keys/{id}/record`) |
| `/models` | Models | `GET /v1/models` | Each Ada model's versions by commit and where each is active. Delete (`DELETE /v1/models/{id}`) |
| `/settings/general` | General | `GET /v1/org`, `GET /v1/me` | Rename the org (`PATCH /v1/org`) |
| `/settings/billing` | Billing | `GET /v1/me`, `GET /v1/plans`, `GET /v1/rates` | The plan, its renewal and hosting this month; the plans above it; the hosted machine rates. Invoices and payment (`POST /v1/billing/portal`) |
| `/settings/plans` | Plans (full window) | `GET /v1/me`, `GET /v1/plans`, `GET /v1/rates` | Choose a plan: Stripe Checkout without a subscription (`POST /v1/billing/checkout {plan}`), else a prorated change (`POST /v1/billing/plan {plan}`). Enterprise is Talk to us (`mailto:sales@glyphh.ai`) |
| `/settings/usage` | Usage | `GET /v1/me`, `GET /v1/plans`, `GET /v1/runtime/keys` | Precedents on hosted machines against the plan's bucket, hosting this month by machine, each API key's calls |
| `/settings/members` | Members | `GET /v1/org`, `GET /v1/org/members`, `GET /v1/org/invites`, `GET /v1/me` | Invite (`POST /v1/org/invites {email}`, valid seven days), cancel an invite (`DELETE /v1/org/invites/{id}`), remove a member (`DELETE /v1/org/members/{id}`) |
| `/settings/profile` | Profile | `GET /v1/me` | Rename (`PATCH /v1/me`), link a provider (`POST /v1/me/identities` → its link), unlink (`DELETE /v1/me/identities/{provider}`) |
| `/settings/installs` | Installs | `GET /v1/installs` | Sign out an install (`DELETE /v1/installs/{id}`) |

The platform's own routes: `/login`, `/auth/login`, `/auth/callback`, `/auth/logout` (POST), `/auth/session`,
`/auth/providers` (the server's, passed through) and `/api/v1/*`. Writes must come from this origin.

## Settings

| Variable | What |
|---|---|
| `GLYPHH_SERVER_URL` | The server: `https://api.glyphh.ai` |
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
npm run fake-server         # a stand-in server with sample data on FAKE_SERVER_PORT (default 8080)
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
