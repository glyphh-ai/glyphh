# platform

The Glyphh platform, https://platform.glyphh.ai. Glyphh's products were retired on 2026-11-18 (Ada Cloud, the Claude
connector, rrotor's licences, plans and billing); Glyphh now makes games. The platform keeps its console shell, its
look and its sign-in, to become the games' admin: what is left is listed below, and nothing else is served.

| Part | Repo | What |
|---|---|---|
| Platform | `glyphh-ai/platform` (this) | The sign-in, Home (empty) and Glyphh's staff view: the games' admin |
| Server | `glyphh-ai/server` | The API and the authorization server, https://api.glyphh.ai. With its `GLYPHH_PRODUCTS` off (the default) every product route answers `410 E_WOUND_DOWN`, and only Glyphh's staff sign in |

## What is left

| Route | Page | Calls |
|---|---|---|
| `/login` | Log in with Google or GitHub (single sign-on when the server offers it) | `GET /auth/providers`, then `/auth/login` |
| `/authorize?oauth=&client=`, `/allow?consent=` | The two steps the server sends a browser to in a sign-in | `GET {server}/auth/consent`, links to `{server}/auth/...` |
| `/error?code=&message=&trace=` | Any refusal in a browser step, with the trace id to quote | none |
| `/` | Home, in the console's shell (the logo, the sidebar, the account menu with the theme and Log out): empty, "Nothing here yet." Glyphh's staff land on the staff view instead | `GET /v1/me` |
| `/admin` | The games' admin, staff only: every game's health, build, players, revenue and what waits for someone | `GET /api/games/overview` |
| `/admin/games/:id?tab=` | One game's admin: a tab for each of its lists, with that game's own actions (confirmed in a dialog where they can't quietly be taken back) | `POST /api/games/:id/tools/:tool` |
| `/admin/traffic`, `/admin/events`, `/admin/audit` | Glyphh's own sites' traffic, the server's errors, the staff audit log | `/v1/admin/*` |
| anything else | "Page not found" | none |

The retired products' staff screens (Dashboard, Infrastructure, Organisations, People, Plans, Marketing links, Ada
versions) were removed with the games' admin (2026-11-19).

## The games' admin

His ruling, 2026-11-19: "one admin, games keep their own DBs". Each game keeps its own server and database; the
platform calls each game's existing admin MCP endpoint, `POST {site}/mcp?admin=<key>` (JSON-RPC `tools/call`),
server-side only (`server/games.ts`), with that game's own `ADMIN_MCP_KEY`. Keys never reach the browser. Every
`/api/games` call checks the session is staff (`GET {server}/v1/me`, `staff: true`) and every action is written to
the platform's log with the staff member's email; each game also keeps its own record ("admin key").

| Game | Site | Platform secret (copy of the game's Fly secret) |
|---|---|---|
| Free Fall Frank | https://freefallfrank.com | `GAME_ADMIN_KEY_FRANK` = `ADMIN_MCP_KEY` of `free-fall-frank` |
| Crabby Knife Fight | https://crabbyknifefight.com | `GAME_ADMIN_KEY_CRABBY` = `ADMIN_MCP_KEY` of `crabby-knife-fight` |
| Bams & Brags | https://bamsandbrags.com | `GAME_ADMIN_KEY_MAHJ` = `ADMIN_MCP_KEY` of `glyphh-mahj` |
| Send a Carol | https://sendacarol.com | `GAME_ADMIN_KEY_CAROL` = `ADMIN_MCP_KEY` of `send-a-carol` |

A game without its key shows as "Not connected". `GAME_URL_<GAME>` points the platform at another address of a game.
Only the tools listed per game in `server/games.ts` can be called; `src/games/catalog.ts` is what each game's page
shows and offers.

## What was removed (2026-11-18)

- **Pages, their sidebar items and their calls:** Ada Cloud (Home, Models, a model's tabs, Ada versions, Templates,
  API Keys, Usage), Runtimes & licences (Runtimes, Licence, Apps, Runtime keys, Usage), Plans, every Settings page
  (General, Billing with tokens and funds, Members, Auth, Profile, Installs), the device sign-in pages (`/device`,
  `/device/approve`, `/device/done`) and `/github`. The account menu keeps the theme and Log out.
- **Route handlers:** `/api/ada/v1/*` and the upload to Ada Cloud; `GLYPHH_ADA_URL` is no longer read.
- **Hosts:** demo.glyphh.ai (the demos, `/voice`, `/bot`, `DEMO_*`) and games.glyphh.ai (`GAMES_HOST`; glyphh.ai
  serves the games pages itself, from `glyphh-ai/web`). This app answers one host. Their Fly certificates, DNS
  records and the app's `DEMO_GLYPHH_API_KEY` and `DEMO_DAILY_CALLS` secrets are no longer used.
- **The local fake server** (`dev/`), which faked the products.

## Sign-in

The platform is a confidential OAuth client of the server (`PLATFORM_CLIENT_ID`, `PLATFORM_CLIENT_SECRET`). `/login`
starts `/auth/login`, which goes to `{server}/oauth/authorize`; the server sends the browser to `/authorize` here to
pick a provider, then to `/allow`, and the tokens come back to `{PLATFORM_URL}/auth/callback`. They live in a sealed,
HttpOnly cookie; the browser never holds a token. `/api/v1/*` passes a call to `{server}/v1/*` with the session's
token, renewing it when it has expired; `POST /auth/logout` revokes it.

## The logo

`public/glyphh-logo-black.png`, the file glyphh.ai's header shows (from `glyphh-ai/web`'s `public/`): the cat and the
name in black with a white outline, one file for every theme, 38px high in the sidebar (`src/ui/Logo`). Never typed.

## Run it

    npm ci
    npm run typecheck
    npm test
    npm run build && npm start

Settings are in `.env.example`. `npm run dev` serves the pages with hot reload against the server named in `.env`.
Every push runs the types, the tests and the image build; a merge to main deploys to Fly (`fly.toml`, the app
`glyphh-ai-app`).
