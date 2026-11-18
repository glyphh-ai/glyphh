# platform

The Glyphh platform, https://platform.glyphh.ai. Glyphh's products were retired on 2026-11-18 (Ada Cloud, the Claude
connector, rrotor's licences, plans and billing); Glyphh now makes games. The platform keeps its console shell, its
look and its sign-in, to become the games' admin: what is left is listed below, and nothing else is served.

| Part | Repo | What |
|---|---|---|
| Platform | `glyphh-ai/platform` (this) | The sign-in, Home (empty) and Glyphh's staff view |
| Server | `glyphh-ai/server` | The API and the authorization server, https://api.glyphh.ai. With its `GLYPHH_PRODUCTS` off (the default) every product route answers `410 E_WOUND_DOWN`, and only Glyphh's staff sign in |

## What is left

| Route | Page | Calls |
|---|---|---|
| `/login` | Log in with Google or GitHub (single sign-on when the server offers it) | `GET /auth/providers`, then `/auth/login` |
| `/authorize?oauth=&client=`, `/allow?consent=` | The two steps the server sends a browser to in a sign-in | `GET {server}/auth/consent`, links to `{server}/auth/...` |
| `/error?code=&message=&trace=` | Any refusal in a browser step, with the trace id to quote | none |
| `/` | Home, in the console's shell (the logo, the sidebar, the account menu with the theme and Log out): empty, "Nothing here yet." Glyphh's staff land on the staff view instead | `GET /v1/me` |
| `/admin`, `/admin/*` | Glyphh's staff view, staff only (the server refuses anyone else): Dashboard, Infrastructure, Log alerts, Organisations, People, Plans, Traffic, Marketing links, Ada versions, Audit log | `/v1/admin/*` |
| anything else | "Page not found" | none |

The staff view is as it was: it still shows the retired products' numbers (plans, Ada versions, the queues), which
the server still answers for staff. Trimming it belongs with the games' admin.

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
