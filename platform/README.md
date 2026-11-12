# platform

The Glyphh platform, https://platform.glyphh.ai: the one web app a person uses. They sign in, use Ada Cloud, see the
licence their runtimes run on, register the runtimes they run themselves, make the keys that call them, pay and run their
org. Every page shows the server's API; the platform stores nothing. Glyphh hosts no runtime: for rrotor the server only
grants licences.

| Part | Repo | What |
|---|---|---|
| Platform | `glyphh-ai/platform` (this) | Every page a person sees |
| Server | `glyphh-ai/server` | The API and the authorization server, https://api.glyphh.ai: accounts, billing, licences, Ada Cloud. Renders no page |
| Runtimes | `glyphh-ai/rrotor` | rrotor, the runtime a person runs for their programs and CLIs: local on their own computer (installed from Claude with the `glyphh` plugin's `rrotor` skill, or `deploy/compose` in `glyphh-ai/glyphh`), or self-hosted at its own address, `https://<host>` (`RROTOR_PUBLIC_HOST`). It reads its licence key as `GLYPHH_LICENSE_KEY`. Claude and apps call it directly |

The contract is the server's `docs/architecture.md` (the API table and **The platform**); prices and plan rules are
its `docs/pricing.md`.

## Sign-in

1. **The platform** is a confidential OAuth client of the server (`PLATFORM_CLIENT_ID`, `PLATFORM_CLIENT_SECRET`,
   registered once at `POST {server}/oauth/register`). `/login` starts `/auth/login`, which goes to
   `{server}/oauth/authorize`; the server sends the browser to `/authorize` here to pick Google or GitHub, and the
   tokens come back to `{PLATFORM_URL}/auth/callback`. They live in a sealed, HttpOnly cookie; the browser never holds
   a token.
2. **Claude** reaches a local rrotor at `http://127.0.0.1:7777/mcp` (the `rrotor` skill adds it), and a self-hosted one
   at `https://<host>/mcp`, whose OAuth runs against the same server and lands on `/authorize` here; already signed in,
   it is one Allow.
3. **Apps** call a self-hosted runtime with a runtime key (made on Runtime keys, or API Keys with Ada Cloud off; shown
   once) as the bearer.

## Routes the server sends a browser to

The server redirects here with signed values in the query. A consent is tied to the browser that started it by the
server's `glyphh_signin` cookie (ten minutes, on the server's domain), so each answer is a link, not a fetch.

| Route | Arrives from | Shows | Answers with |
|---|---|---|---|
| `/device?code=` | `GET {server}/v1/device?code=` (without a code, asks for it) | The code, to match Claude's; a button per provider from `GET {server}/auth/providers`, and single sign-on when it says `sso` (the work email, whose domain names the org) | Link to `GET {server}/auth/{provider}/start?code=` (`/auth/sso/start?code=&email=`) |
| `/device/approve?consent=` | the provider's callback | `GET {server}/auth/consent` → `{kind: "device", code, name, surface, email}` | Link to `GET {server}/auth/approve?consent=&decision=approve` or `deny` |
| `/device/done?result=approved\|denied` | `/auth/approve` | "Signed in" or "Nothing was signed in" | — |
| `/authorize?oauth=&client=` | `GET {server}/oauth/authorize` | "<client> wants to use your Glyphh account"; a button per provider, and single sign-on as on `/device` | Link to `GET {server}/auth/{provider}/start?oauth=` (`&email=` for single sign-on) |
| `/allow?consent=` | the provider's callback | `GET {server}/auth/consent` → `{kind: "oauth", client, returns_to, resource, email}` | Link to `GET {server}/auth/oauth/allow?consent=&decision=allow` or `deny` |
| `/account?linked=<provider>` | a provider link's callback | Redirects to `/settings/profile`, which confirms the link | — |
| `/billing?done=1` | Stripe Checkout and the portal | Redirects to `/settings/billing`, read afresh | — |
| `/github?installed=<login>` | the GitHub App's callback | "Glyphh's GitHub App is installed on <login>" | — |
| `/error?code=&message=&trace=` | any refusal in a browser flow | The message and the trace id | — |

A refusal from `GET {server}/auth/consent` is JSON, `{"error": {"code", "message", "trace_id"}}`, shown like `/error`.

## Licences only, and features not built

- **Glyphh hosts no runtime.** For rrotor the server only grants licences: the licence key, the runtimes a person
  registers to run at their own address and their tokens, offline licences, runtime keys and the nodes counted. It has
  no hosted machines, rates, hosting cost or runtime telemetry, and the platform shows none. A plan's `limits.machines`
  is its **runtime nodes**: every rrotor linked for the org, local or self-hosted (Free 1, Pro 3, Team 10, Enterprise
  unlimited), shown as "runtime nodes"; its `limits.precedents` is per node (Free 5,000, Pro 50,000, Team 500,000),
  shown as "precedents per node". The old `/machines`, `/logs` and `/settings/logs` go to Runtimes, `/getting-started`
  to its Add a runtime.
- **A feature not built** is shown as "Coming soon", never as included. A plan's `features` is a boolean per feature
  with a separate `built` map beside it (`{"features": {"sync": true, …}, "built": {"sync": false, "ha": false,
  "offline": true, "sso": true}}`); `{"sync": {"included": true, "built": false}}` is read alike. Sync, HA, SSO, roles
  and audit logs missing from `built` (or with no map) are not built; roles and audit logs are included where `sso`
  is when the server does not name them, and built only when it says so. Plans are listed, priced and bought as before.
- **Single sign-on** (Enterprise) is set on Settings → Auth (`GET`/`PUT`/`DELETE /v1/org/sso`): the OpenID Connect
  issuer, client id and secret (never shown back), the email domains that route a sign-in to the org, the redirect URI
  to register at the identity provider, and whether it is required (then Google and GitHub are refused for the org's
  people). The sign-in pages offer "Continue with single sign-on" when `GET {server}/auth/providers` says `sso`: the
  person gives their work email and goes to `{server}/auth/sso/start?…&email=`; the platform's own log-in remembers
  the email beside the provider so `/authorize` continues without asking again. Settings → Auth also takes the
  **reviewer groups** (`reviewers`): the identity provider's groups whose members review the org's apps beside the
  admin.

## Ada Cloud

With the server's `GLYPHH_ADA_CLOUD` on, `GET /v1/me` answers `ada_cloud: true`: Home, Models, Ada, API Keys and Usage
are Ada's (the sidebar's Ada), and **Runtimes & licences** sits beside them (Runtimes, Licence, Apps, Runtime keys; below,
Pages). The old `?add=1` on Home opens Home. Off, or on an older server without the field, every page is as below. The browser calls
`/api/ada/v1/*` here; the route handler adds the session's token and passes the call to Ada's host
(`GLYPHH_ADA_URL`, `https://ada.glyphh.ai`), which takes a Glyphh sign-in as the account API does. An import's file goes
`PUT /api/ada/v1/uploads/<link>`, streamed to the upload link without a token (the link is its own credential).

| Route | Page | Ada calls | Does |
|---|---|---|---|
| `/` | Home | `GET /v1/models`, `GET /v1/usage` | The models, the precedents and this month's requests against the plan (and what happens past the month), the connector URL (`{server}/mcp`) to add in Claude |
| `/models` | Models | `GET /v1/models`, `GET /v1/ada` | Each model's live version, the Ada it runs (Beta labelled) and precedents |
| `/ada` | Ada (after Models in the sidebar) | `GET /v1/ada`, `GET /v1/models` | Every Ada version, newest first: its status (Stable, Beta, Deprecated with its end, Retired), release date, whether it changes answers from the one before, its release notes as prose (the kernel's semver only in its details line), the org's models on it, each with a link to its Upgrade Ada flow. `/ada#<name>` lands on one |
| `/models/new` | New model | `POST /v1/models {name, spec, ada}`, `GET /v1/ada` | A spec editor, checked as typed (the cloud's bounds), from an example or blank; its Ada, the latest stable first (betas labelled, deprecated and retired not offered); a refusal of the Ada chosen offers the latest stable |
| `/models/:name` | A model, a tab each (`?tab=`), in this order; ← Models above its name | `GET /v1/models/{name}`, `…/stats`, `…/map`, `…/precedents/{id}`, `…/versions`, `…/settings`, `GET /v1/jobs/{id}` | **Dashboard** (first): its precedents against the org's plan, reads over the last 30 days, the share of decides that asked a person, the live version; charts (chart.js, in the theme's tokens) of reads a day (decides apart), precedents over time, the share that asked a day, how sure the decides were, outcomes by output; the latest jobs. Each says what will show while there is nothing yet. **3D view**: up to 2,000 of its precedents (`…/map`), each a cloud of its glyph's bits laid out by its nearest (three.js, loaded with the tab; after the old GlyphViewer), coloured by outcome, lines to the nearest of the same or a different outcome, layers on 0–9, E explode, F freeze, L labels, Esc clear, search by id; a picked point's case (`…/precedents/{id}`); laid out unseen and drawn still when the person asked for less motion. **Try it**: a form from the spec, `POST /v1/decide`: the answer, confidence, whether a person should decide, the precedents. **Import**: a CSV (each column mapped to a role, an outcome, ts, id or skipped) or JSON Lines (`POST …/imports`, then the file to its link), with progress. **Backtest**: candidates (settings changed, or another version) on the newest held-out cases (`POST …/backtest`), the results and Make live (with the backtest kept on the version). **Settings**: every lever, saved as a version (`PATCH …/settings`). **Export**: JSON Lines or SQLite (`POST …/export`), then its download link. **Spec** (last): the live spec, a new version (`PUT …/spec`), versions and Make live (`POST …/versions/{n}/activate`). **Versions**: each version with its Ada; **Upgrade Ada** (`?upgrade=<name>`, none for the latest stable): choose a version, backtest the live spec on it (`POST …/backtest {ada}`), see the score change, then `POST …/upgrade {ada, backtest}` and its re-encode job; rollback is the version before made live, on its own Ada. Under the name, the Ada it runs and `ada_notice`: a newer stable (its notes, Backtest and upgrade), a quieter line for a beta, a warning while deprecated (its end) or retired, word of a move Glyphh made. Delete after typing the name |
| `/keys` | API Keys | `GET`, `POST /v1/keys`, `DELETE /v1/keys/{id}` | Cloud keys: name, expiry, clearance (0 to 1); shown once; revoke |
| `/usage` | Usage | `GET /v1/usage`, `GET /v1/models`, `GET /v1/me` | `{plan, month, resets_at, models, precedents: {used, max}, requests: {used, max, over, overage}, requests_per_second}`: precedents and the month's requests against the plan's (the month, UTC, and when it starts again); past it, Pro and Team are billed ($1 per 10,000, the plan's `overage_cents_per_10k`), Free stops until it turns, with the way to upgrade; the calls a second; each model's precedents |

Ada's plan refusals are shown on every Ada page in the server's words with the way on (`AdaErrorNotice`): 429 `E_RATE` (the
plan's calls a second; Retry-After, passed back by the route handlers), 403 `E_LIMIT` `requests` (Upgrade to the plan the
server names, or Talk to us) and `precedents` (the plans). With Ada Cloud on the plan cards show each plan's cloud caps
(`cloud` on `GET /v1/plans`) in place of runtime nodes and precedents per node.

Billing, Plans, Members, Profile, Installs and General stay; the plan cards show the cloud caps, not a plan's runtime
nodes, precedents per node or runtime features (sync, HA, offline licences).

## Pages

The browser calls `/api/v1/*` here; the route handler adds the session's token and passes the call to `{server}/v1/*`.
Runtimes & licences (Runtimes, Licence, Apps, and Runtime keys with Ada Cloud on or API Keys and Usage with it off) is in the
sidebar either way; with Ada Cloud off, `/` goes to `/runtimes`. Models, API Keys, Runtime keys and Apps are searchable
and paged alike (`src/components/SearchPaged.tsx`): a search field whose text reaches the URL as `?q=` once typing pauses, 24
a page with Previous/Next as `?page=` and "25–30 of 30"; Apps sends both to the server, the others filter and page the
whole list the server answered.

| Route | Page | Server calls | Does |
|---|---|---|---|
| `/runtimes` | Runtimes | `GET /v1/runtimes/self`, `GET /v1/me` | **Install rrotor** on your own computer: from Claude Code, the `glyphh` plugin (`/plugin marketplace add glyphh-ai/glyphh`, `/plugin install glyphh@glyphh`), then "install rrotor" (its `rrotor` skill); or by hand, `glyphh-ai/glyphh`'s `deploy/compose/docker-compose.local.yml` (fetch it, make a local token, `docker compose … up -d`, `claude mcp add` at `http://127.0.0.1:7777/mcp`), with a link to the Docker Compose guide; the key reaches rrotor on its own, or as `GLYPHH_LICENSE_KEY`; none is Community. The runtimes run at their own address: state, version, last heartbeat; rotate the token (`POST /v1/runtimes/self/{id}/token`), delete (`DELETE /v1/runtimes/self/{id}`), offline licence on Enterprise (`POST /v1/runtimes/{id}/offline-licence {days}`). **Add a runtime** (a dialog; `/runtimes?add=1` opens it on load, and the old `/?add=1` and `/getting-started` go there): for a rrotor at its own public address only (one on the person's own computer comes from the `rrotor` skill, above): Docker, Helm or Terraform, each with what it needs (register with a DNS name, `POST /v1/runtimes/self {name, public_url}`, token shown once; the command filled from the answer's `env`, nothing to clone, pasteable in zsh and bash with no `#` lines, ending with a `curl …/healthz` check: Docker is `deploy/compose` as its README has it, `docker-compose.yml` and the `Caddyfile` fetched into a folder, `.env` written with the runtime id, token and public host (and `RROTOR_CPUS`/`RROTOR_MEMORY` for Medium and Large, the Helm chart's presets), `docker compose up -d`; or the image alone with `docker run` behind HTTPS already in front; Helm installs the released chart; Terraform's module is `git::https://github.com/glyphh-ai/glyphh.git//deploy/terraform/<cloud>?ref=main`; on a paid plan, how to set the licence key, as text beside the block, for an air-gapped node only). Then the connector URL `https://<host>/mcp` and the SDK and plugin install commands. Closing it reads the runtimes again |
| `/apps` | Apps | `GET /v1/apps?q=&page=&per_page=24&state=&type=`, `GET /v1/me`, `POST /v1/apps/{id}/approve\|reject\|retire` | What Claude made (a page, a dashboard, a doc, a diagram, a deck, a design) and published to the org's rrotors, from the server's catalogue (`glyphh-ai/server`, `docs/specs/apps.md`): cards with the title, a type chip, the description (three lines at most), the runtime and version, the roles that may open it (or Everyone), who published it and when, and **Open** (the app at the rrotor, `{runtime_url}/apps/{name}/`, a new tab). A search field (`?q=`, sent once typing pauses), a type filter (All types, Pages, Dashboards, Docs, Diagrams, Decks, Designs; `?type=`, absent for all) and 24 a page (`?page=`, Previous/Next, "25–30 of 30"). The old `/artifacts` goes here with its query string. A reviewer (`me.reviewer`: the admin, or a member in a reviewer group) has the tabs Published, Awaiting review (`?state=draft`: Approve, Reject with a reason) and Rejected (`?state=rejected`: the reason), and Retire on a published one; a member asking for a review tab in the URL sees Published |
| `/licence` | Licence | `GET /v1/me`, `GET /v1/license/keys`, `GET /v1/license/nodes` | The key the org's runtimes are sent now (`license_key`), masked with Reveal and Copy: its tier, runtime nodes, precedents per node, sync and expiry. How it reaches rrotor: on its own at the link and the daily heartbeat, renewed at each payment; an air-gapped node takes it as `GLYPHH_LICENSE_KEY` or `/etc/rrotor/license.key`. The runtime nodes "N of M" and each node, local or self-hosted (runtime, node id, role, version, precedents, last seen), over the plan shown, never blocking. Older keys with their state (live, expired, revoked). Free has none: Community, 1 node, 5,000 precedents, no sync. `/settings/licence` goes here |
| `/runtime-keys` (Ada Cloud on), `/keys` (off) | Runtime keys, API Keys | `GET /v1/runtime/keys`, `GET /v1/runtimes/self` | Make one for a self-hosted runtime (`POST /v1/runtime/keys {name, runtime_id, expires_in_days?}`: the runtime, the first until another is chosen; 7, 30, 60, 90 or 365 days, or never; shown once; with no runtime registered, the way to Runtimes), revoke (`DELETE /v1/runtime/keys/{id}`), delete a revoked or expired one (`DELETE /v1/runtime/keys/{id}/record`). With Ada Cloud off, `/runtime-keys` goes to `/keys` |
| `/usage` (Ada Cloud off) | Usage | `GET /v1/me`, `GET /v1/runtime/keys`, `GET /v1/license/nodes` | The fullest node's precedents against the plan's per node; the runtime nodes and each node, as on Licence; each API key's calls. `/settings/usage` goes here |
| `/models`, `/models/*` (Ada Cloud off) | — | — | Models are Ada Cloud's: with it off the account API serves none, so they are not in the sidebar and go to `/runtimes` |
| `/settings/general` | General | `GET /v1/org`, `GET /v1/me` | Rename the org (`PATCH /v1/org`) |
| `/settings/billing` | Billing | `GET /v1/me`, `GET /v1/plans` | The plan, its renewal and what it includes. Invoices and payment (`POST /v1/billing/portal`) |
| `/settings/plans` | Plans (full window) | `GET /v1/me`, `GET /v1/plans` | Choose a plan: Stripe Checkout without a subscription (`POST /v1/billing/checkout {plan}`), else a prorated change (`POST /v1/billing/plan {plan}`). Enterprise is Talk to us (`mailto:sales@glyphh.ai`) |
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
| `DEMO_GLYPHH_API_KEY` | The demo's Ada Cloud key (below). Unset: demo.glyphh.ai shows its page and its API answers 503 |
| `DEMO_HOST` | The host the demo answers on (default `demo.glyphh.ai`) |
| `DEMO_DAILY_CALLS` | The demo's Ada calls a day, all visitors together (default 150) |
| `DEMO_VOICE_DAILY_CALLS` | The voice demo's (demo.glyphh.ai/voice) Ada calls a day, all visitors together (default 300) |
| `DEMO_BOT_DAILY_CALLS` | The bot demo's (demo.glyphh.ai/bot) Ada calls a day, all visitors together (default 6000, about 55 takes) |

## demo.glyphh.ai

The same process answers `demo.glyphh.ai` with the demos and nothing of the platform's: no sign-in, no session, no
`/api/v1`. Anyone can use it. `/` is the front page, a card per demo with a search (`demo/public/index.html`); each
demo is one entry in `demo/public/demos.js` (`soon: true` shows its card without a link until it is live).

The expenses demo is `/expenses/`: the page `demo/public/expenses`, the 40 past expenses `demo/history.json`, the
handlers `server/demo.ts`; they hold `DEMO_GLYPHH_API_KEY` and the browser never sees it.

| Route | Does |
|---|---|
| `GET /api/state` | The model and the ledger: the 40, then what visitors recorded (another visitor's name shown as "Another visitor") |
| `POST /api/decide {claim}` | `POST /v1/decide` on `launch-demo-expenses`: the answer, its probabilities, whether a person decides, the precedents |
| `POST /api/record {claim, outcome}` | `record_many` of one case, the next ref (E-2081 on), approve or reject |
| `POST /api/reset` | The model made again from the 40 (only when something was recorded) |

The key can reach every model in its org, so the handlers name one, `launch-demo-expenses`, and take no model, path
or setting from the page; any other `/api` path is 403. A claim is checked against the expense's shape (words for
department and category, $0 to $3,000, a receipt yes or no, one of the three policy checks, a description of 120
characters at most) before Ada is called. Writes come from the demo page only. Each visitor (their address) has 10
decides and records a minute and 100 a day, and a reset every 5 minutes; the demo has `DEMO_DAILY_CALLS` Ada calls a
day in all. A take adds 20 precedents at most, and an hour after the first, the model goes back to the 40.

### demo.glyphh.ai/voice

A game: Ada reads how a visitor sounds against how they usually sound, as likelihoods of truth, a lie, stress and
anger. **No audio is kept or sent**, and the page says so: the browser measures each take (`demo/public/voice/measure.js`:
pitch, its range and wobble, loudness, pace, pauses, seconds a word), sends seven numbers, each a change from the
visitor's usual voice, and drops the samples. The name stays in the browser (localStorage), with Ada's ids for the
visitor's takes and the numbers of their true takes, from which the usual voice is worked out again each time. The
page is `demo/public/voice`, a card on the front page, the handlers `server/voice.ts`, on the same key; their model is `launch-demo-voice-2`, made the
first time and never reset, every take carrying the visitor's id (a year-long HttpOnly cookie, `glyphh_voice`).

| Route | Does |
|---|---|
| `POST /api/voice/enrol {takes}` | The three set phrases, in order (their name, a truth, a lie), recorded as truth, truth, lie |
| `POST /api/voice/read {take}` | `POST /v1/decide`: each mood's likelihood, whether Ada cannot tell (under 60%), the closest takes' moods |
| `POST /api/voice/teach {take, mood}` | What the take really was, recorded |
| `POST /api/voice/forget {ids}` | Each id checked to carry the visitor's id, then deleted; the visitor gets a new id |
| `GET /api/voice/map` | `GET /v1/models/{name}/map` (600 takes): each take's id, mood and glyph bits, and its nearest, for the 3D view; held 5 seconds, dropped when a take is recorded or forgotten |

A take is a phrase (`self`, `truth`, `lie`, `free`) and the seven numbers, each clamped to its range; anything else is
refused. A visitor keeps 60 takes, the model 20,000; the visitor limits are the expenses demo's, and the voice demo
has `DEMO_VOICE_DAILY_CALLS` Ada calls a day of its own (default 300).

Each measure's range is what a voice moves by between calm and upset, no wider (a number is encoded by where it sits
in its range, so a wide range makes every take look alike). The model starts with 32 research takes (`speaker`
`research`): eight of each mood as the vocal-emotion studies describe it against a calm voice, so stress and anger
can be read before anyone has taught them. A model on an older spec gets this one as a new version at start, its job
followed to the end, then the research takes.

Under the game, the platform's own 3D view (`src/pages/ada/model/view/scene.ts`) draws every take, the visitor's
bright, again after each take Ada keeps. It is built for the plain page on its own (`src/demo/glyph-view.ts`,
`vite.demo.config.ts`, into `dist/demo`) and served at `/voice/3d/glyph-view.js`.

### demo.glyphh.ai/bot

Teach a bot: the visitor makes up a rule for approving expenses and keeps it to themselves. A bot that knows nothing
works through 40 expenses: it asks the visitor where Ada is under 75% sure (and about the first five whatever she
thinks) and decides alone where she is sure; the visitor answers, and says whether each decision made alone was
right. Every answer is recorded, Ada learns the roles' weights again every five answers from the tenth (once both
outcomes are there), and the page shows the questions falling away: a cell an expense (asked, alone and right, alone
and wrong), what the visitor's decisions turn on as Ada learned it, and at the end how many of the 40 the bot asked
about. No language model runs: the bot is its learned gate alone, and the page says so.

The page is `demo/public/bot`, a card on the front page, the handlers `server/bot.ts`, on the same key. Each take has
a model of its own, `launch-demo-bot-<12 hex>`, made at Start and deleted when the 40 are done, when the visitor
starts again, or after 20 idle minutes, so one visitor's rule never reaches another's bot; models an earlier process
left behind are deleted at the first Start. The take (its expenses, the log, the visitor's place) is held in memory
under the visitor's id (a day-long HttpOnly cookie, `glyphh_bot`).

| Call | What it does |
|---|---|
| `GET /api/bot/state` | The visitor's take, or none: a page loaded again goes on where it was |
| `POST /api/bot/start` | A new take: its model made, 40 expenses made here, the first one back. An earlier take of the visitor's ends |
| `POST /api/bot/answer {n, outcome}` | The visitor's word on expense `n`, `approve` or `reject` (their answer, or the right decision where the bot decided alone): recorded, then the next expense and what the bot does with it (`POST /v1/decide`). An `n` already answered changes nothing |

The expenses are made by the server (`makeItems`), never sent by the page, which sends an outcome and nothing else.
Ada is shown five things about each (department, category, amount, receipt, policy check). 30 takes go on at once; a
visitor (their address) starts 4 in ten minutes and gives 60 answers a minute, 600 a day; the bot demo has
`DEMO_BOT_DAILY_CALLS` Ada calls a day of its own (default 6000; a take is about 110).

Measured against Ada Cloud on 2026-11-12 with a script answering by a known rule (40 expenses, this loop): for five
simple rules (no receipt no money, nothing over $500, the company's policy, only travel, engineering or under $300)
the bot asked 8 to 13 times, nearly all in the first 20, and decided all of the last 10 alone with 0 or 1 wrong; a
rule with a rare exception (sales never gets meals or gifts) still got 3 of the last 10 wrong; with no rule (a coin
toss) it went back to asking 8 of the last 10.

Every demo page wears the platform's look: `demo/public/platform.css` (dark-hc's tokens, white buttons, 8px corners,
the wordmark), loaded after each page's own stylesheet.

Production is the Fly app `glyphh-ai-app` (`fly.toml`), deployed by CI (`.github/workflows/ci.yml`) on a merge to
main.

## Develop

Node 22 or later.

```bash
npm ci
cp .env.example .env        # then set PLATFORM_CLIENT_ID, PLATFORM_CLIENT_SECRET and SESSION_SECRET
npm run fake-server         # a stand-in server with sample data on FAKE_SERVER_PORT (default 8080): licences only,
                            # as the server is, the org on Free; FAKE_ADA=on for Ada Cloud (its API at /ada/v1);
                            # FAKE_LLM=on for hosted models' tokens, the overage balance and top-ups
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
