# platform

The Glyphh platform, https://platform.glyphh.ai: the one web app a person uses. Glyphh is one thing, Ada. They sign in,
use Ada Cloud (make a model, load it, tune it, try it, read what it decided), make the keys their code calls it with, see
what they use, pay and run their org, and browse the Marketplace of plugins for Claude. Every page shows the server's
API; the platform stores nothing.

| Part | Repo | What |
|---|---|---|
| Platform | `glyphh-ai/platform` (this) | Every page a person sees |
| Server | `glyphh-ai/server` | The API and the authorization server, https://api.glyphh.ai: accounts, billing, Ada Cloud. Renders no page |
| Plugins | `glyphh-ai/plugins` (public) | The plugins for Claude the Marketplace page shows. The platform only reads it |

The contract is the server's `docs/architecture.md` (the API table and **The platform**); prices and plan rules are
its `docs/pricing.md`.

## Sign-in

1. **The platform** is a confidential OAuth client of the server (`PLATFORM_CLIENT_ID`, `PLATFORM_CLIENT_SECRET`,
   registered once at `POST {server}/oauth/register`). `/login` starts `/auth/login`, which goes to
   `{server}/oauth/authorize`; the server sends the browser to `/authorize` here to pick Google or GitHub, and the
   tokens come back to `{PLATFORM_URL}/auth/callback`. They live in a sealed, HttpOnly cookie; the browser never holds
   a token.
2. **Claude** reaches Ada through the connector at `{server}/mcp`, whose OAuth runs against the same server and lands
   on `/authorize` here; already signed in, it is one Allow.
3. **Apps** call Ada Cloud with an API key (made on API Keys; shown once) as the bearer.

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
| `/error?code=&message=&trace=` | any refusal in a browser flow | The message and the trace id | — |

A refusal from `GET {server}/auth/consent` is JSON, `{"error": {"code", "message", "trace_id"}}`, shown like `/error`.

## What Glyphh no longer has

Glyphh is Ada alone (2026-11-24). The platform has no bots, hosted connections, programs, projects, crews, templates,
runtimes (rrotor), runtime keys, licence keys, nodes, apps catalogue or GitHub App pages, and calls none of the
server's endpoints for them (`/v1/bots*`, `/v1/connections*`, `/v1/programs*`, `/v1/projects*`, `/v1/recents`,
`/v1/github*`, `/v1/templates*`, `/v1/apps*`, `/v1/runtimes*`, `/v1/runtime/*`, `/v1/license/*`). Their old addresses
are moved on, each with everything under it and with a replace, so Back does not return to them (`src/routes/router.tsx`):
`/bots`, `/approvals`, `/connections`, `/projects`, `/swarms`, `/programs`, `/templates`, `/marketplace/models` and
`/marketplace/bots` go to `/marketplace`; `/runtimes`, `/runtime-keys`, `/licence`, `/apps`, `/artifacts`, `/github`,
`/getting-started`, `/machines`, `/logs`, `/settings/claude-key`, `/settings/github-token`, `/settings/licence` and
`/settings/logs` go to `/` (Home, which is the Marketplace while Ada Cloud is off). Of an answer it still reads (`/v1/me`, `/v1/plans`, `/v1/billing`,
`/v1/billing/series`, `/v1/org/sso`, the staff API) it needs none of the fields that went with them: a plan's `limits`
and its runtime features, `precedents` per node, `connections`, `bots`, `reviewers`, `licences`.

## Plans and features not built

- **A feature not built** is shown as "Coming soon", never as included. A plan's `features` is a boolean per feature
  with a separate `built` map beside it (`{"features": {"sso": true}, "built": {"sso": true}}`);
  `{"sso": {"included": true, "built": true}}` is read alike. The platform has words for single sign-on, roles and
  audit logs: roles and audit logs are included where `sso` is when the server does not name them, and built only when
  it says so. Any other feature a server names is not shown. Plans are listed, priced and bought as before.
- **Single sign-on** (Enterprise) is set on Settings → Auth (`GET`/`PUT`/`DELETE /v1/org/sso`): the OpenID Connect
  issuer, client id and secret (never shown back), the email domains that route a sign-in to the org, the redirect URI
  to register at the identity provider, and whether it is required (then Google and GitHub are refused for the org's
  people). The sign-in pages offer "Continue with single sign-on" when `GET {server}/auth/providers` says `sso`: the
  person gives their work email and goes to `{server}/auth/sso/start?…&email=`; the platform's own log-in remembers
  the email beside the provider so `/authorize` continues without asking again.

## Ada Cloud

`GET /v1/me` answers `ada_cloud: true` (the server's `GLYPHH_ADA_CLOUD`): Home, Models, API Keys and Usage are in the
sidebar, with the Marketplace under them. Off, or missing, those four leave the sidebar and their addresses go to the
Marketplace, the one page that needs none of Ada. The browser calls `/api/ada/v1/*` here; the route handler adds the
session's token and passes the call to Ada's host (`GLYPHH_ADA_URL`, `https://ada.glyphh.ai`), which takes a Glyphh
sign-in as the account API does. An import's file goes `PUT /api/ada/v1/uploads/<link>`, streamed to the upload link
without a token (the link is its own credential).

| Route | Page | Ada calls | Does |
|---|---|---|---|
| `/` | Home | `GET /v1/usage`, `GET /v1/ada`; the account's `GET /v1/billing`, `/v1/billing/series` | A greeting; the balance and the month's tokens (with hosted models on) and Ada's requests against the plan; the week's volume; Ada's newest versions; the docs, the connector URL (`{server}/mcp`) to add in Claude, the SDK's install line and the way to the Marketplace |
| `/models` | Models | `GET /v1/models`, `GET /v1/ada` | Each model's live version, the Ada it runs (Beta labelled) and precedents; searched and paged |
| `/settings/releases` (the old `/ada`) | Releases, in Settings | `GET /v1/ada`, `GET /v1/models` | Every Ada version, newest first: its status (Stable, Beta, Deprecated with its end, Retired), release date, whether it changes answers from the one before, its release notes as prose (the kernel's semver only in its details line), the org's models on it, each with a link to its Upgrade Ada flow. `#<name>` lands on one |
| `/models/new` | New model | `POST /v1/models {name, spec, ada}`, `GET /v1/ada` | A spec editor, checked as typed (the cloud's bounds), from an example or blank; its Ada, the latest stable first (betas labelled, deprecated and retired not offered); a refusal of the Ada chosen offers the latest stable |
| `/models/:name` | A model, a tab each (`?tab=`), in this order; ← Models above its name | `GET /v1/models/{name}`, `…/stats`, `…/map`, `…/precedents/{id}`, `…/versions`, `…/settings`, `GET /v1/jobs/{id}` | **Dashboard** (first): its precedents against the org's plan, reads over the last 30 days, the share of decides that asked a person, the live version; charts (chart.js, in the theme's tokens) of reads a day (decides apart), precedents over time, the share that asked a day, how sure the decides were, outcomes by output; the latest jobs. Each says what will show while there is nothing yet. **3D view**: up to 2,000 of its precedents (`…/map`), each a cloud of its glyph's bits laid out by its nearest (three.js, loaded with the tab; after the old GlyphViewer), coloured by outcome, lines to the nearest of the same or a different outcome, layers on 0–9, E explode, F freeze, L labels, Esc clear, search by id; a picked point's case (`…/precedents/{id}`); laid out unseen and drawn still when the person asked for less motion. **Try it**: a form from the spec, `POST /v1/decide`: the answer, confidence, whether a person should decide, the precedents. **Import**: a CSV (each column mapped to a role, an outcome, ts, id or skipped) or JSON Lines (`POST …/imports`, then the file to its link), with progress. **Backtest**: candidates (settings changed, or another version) on the newest held-out cases (`POST …/backtest`), the results and Make live (with the backtest kept on the version). **Settings**: every lever, saved as a version (`PATCH …/settings`). **Export**: JSON Lines or SQLite (`POST …/export`), then its download link. **Spec** (last): the live spec, a new version (`PUT …/spec`), versions and Make live (`POST …/versions/{n}/activate`). **Versions**: each version with its Ada; **Upgrade Ada** (`?upgrade=<name>`, none for the latest stable): choose a version, backtest the live spec on it (`POST …/backtest {ada}`), see the score change, then `POST …/upgrade {ada, backtest}` and its re-encode job; rollback is the version before made live, on its own Ada. Under the name, the Ada it runs and `ada_notice`: a newer stable (its notes, Backtest and upgrade), a quieter line for a beta, a warning while deprecated (its end) or retired, word of a move Glyphh made. Delete after typing the name |
| `/keys` | API Keys | `GET`, `POST /v1/keys`, `DELETE /v1/keys/{id}` | Cloud keys: name, expiry, clearance (0 to 1); shown once; revoke |
| `/usage` | Usage | `GET /v1/usage`, `GET /v1/models`; the account's `GET /v1/me`, `/v1/billing`, `/v1/billing/series`, `/v1/llm/usage` | `{plan, month, resets_at, models, precedents: {used, max}, requests: {used, max, over, overage}, requests_per_second}`: precedents and the month's requests against the plan's (the month, UTC, and when it starts again); past it, Pro and Team are billed ($1 per 10,000, the plan's `overage_cents_per_10k`), Free stops until it turns, with the way to upgrade; the calls a second; Ada's requests by day; with hosted models on, their tokens and charges by day and by model; each model's precedents |

Ada's plan refusals are shown on every Ada page in the server's words with the way on (`AdaErrorNotice`): 429 `E_RATE` (the
plan's calls a second; Retry-After, passed back by the route handlers), 403 `E_LIMIT` `requests` (Upgrade to the plan the
server names, or Talk to us) and `precedents` (the plans). The plan cards show each plan's cloud caps (`cloud` on
`GET /v1/plans`) and, with hosted models on, its tokens a month (`llm_tokens`).

## Marketplace

`/marketplace` shows what is in the public repository [github.com/glyphh-ai/plugins](https://github.com/glyphh-ai/plugins),
laid out as Claude's own plugin browser lays plugins out. The platform only shows it: a plugin is installed in Claude.

| Route | Page | Does |
|---|---|---|
| `/marketplace` | Marketplace | A search (`?q=`: a plugin's name, description, author, category, keywords, or the name of anything it holds) and a grid of cards, 24 a page (`?page=`). A card: the plugin's name, "by" its author, its description (three lines at most), a chip with a count for each kind it holds (Skills, Commands, Agents, Hooks, Connectors: its MCP servers) and its version. The whole card opens the plugin. While the repository is empty: "The marketplace is being stocked", a link to the repository and the line that adds it to Claude Code. When it cannot be loaded: a quiet "could not be loaded" with "Open it on GitHub" |
| `/marketplace/:plugin` | A plugin | Its name, author, version, licence, category and keywords, and "View on GitHub" (its folder in the repository). **Install in Claude**, each line with Copy: `/plugin marketplace add glyphh-ai/plugins`, then `/plugin install <plugin>@<the marketplace's name>`; and the path in the Claude desktop app (Customize → Plugins → Add marketplace → `glyphh-ai/plugins`). Then **Skills** (each one's name and description from its `SKILL.md` front matter, opening to the file's body), **Commands**, **Agents**, **Connectors** (its MCP servers by name), each item with a link to its file, and **About** (its `README.md`). A plugin kept in another repository is shown from the marketplace's list alone, with a link to its own repository |

The data is read by the route handlers, never by the browser (`server/marketplace.ts`), and served to signed-in pages
as one answer, `GET /api/marketplace` → `{name, owner, description, version, repo, url, plugins[], fetched_at, stale}`:

- One call lists every path, `GET https://api.github.com/repos/glyphh-ai/plugins/git/trees/HEAD?recursive=1` (409 or
  404: the repository is empty, so the marketplace is too); each file is then read from
  `https://raw.githubusercontent.com/glyphh-ai/plugins/HEAD/<path>`. No token is sent (the repository is public), only
  a User-Agent; nothing of the person's goes to GitHub.
- `.claude-plugin/marketplace.json` names the marketplace (`name`, default `plugins`; `owner.name`;
  `metadata.description`, `.version`, `.pluginRoot`) and lists the plugins (`name`, `source`, `description`, `version`,
  `author.name`, `category`, `keywords`). With no list, every folder holding a `.claude-plugin/plugin.json` is a plugin.
- For a plugin whose `source` is a path in the repository (`./plugins/x`): its `.claude-plugin/plugin.json` (fills in
  what the list leaves out: `version`, `description`, `author`, `homepage`, `license`, `keywords`; `mcpServers`),
  `README.md`, `skills/*/SKILL.md`, `commands/*.md`, `agents/*.md`, `hooks/hooks.json` and `.mcp.json`. A file that is
  missing or broken is left out and the plugin is still shown. Any other `source` (another repository) is not followed.
- The answer is kept in memory ten minutes. When GitHub cannot be read, the last answer is served marked `stale`, and
  GitHub is left alone for a minute; with nothing kept, the route answers 502 `E_MARKETPLACE`.
- Markdown from the repository (a README, a skill's body) is drawn as React elements, never as HTML
  (`src/components/Markdown.tsx`): a tag in it shows as text, a link goes to http(s) only, an image is its words.

## Pages

The browser calls `/api/v1/*` here; the route handler adds the session's token and passes the call to `{server}/v1/*`.
Models, API Keys and the Marketplace are searchable and paged alike (`src/components/SearchPaged.tsx`): a search field
whose text reaches the URL as `?q=` once typing pauses, 24 a page with Previous/Next as `?page=` and "25–30 of 30".

| Route | Page | Server calls | Does |
|---|---|---|---|
| `/settings/general` | General | `GET /v1/org`, `GET /v1/me` | Rename the org (`PATCH /v1/org`) |
| `/settings/billing` | Billing | `GET /v1/me`, `GET /v1/plans`, `GET /v1/billing`, `GET /v1/billing/payment`, `GET /v1/billing/ledger` | The plan, its renewal and what it includes. With hosted models on, the overage balance, Add funds (`POST /v1/billing/topup`) and its history. What happens past each limit. The card on file (`POST /v1/billing/card`) and the invoices (`POST /v1/billing/portal`) |
| `/settings/plans` | Plans (full window) | `GET /v1/me`, `GET /v1/plans` | Choose a plan: Stripe Checkout without a subscription (`POST /v1/billing/checkout {plan}`), else a prorated change (`POST /v1/billing/plan {plan}`). Enterprise is Talk to us (`mailto:sales@glyphh.ai`). With hosted models on, their rates |
| `/settings/members` | Members | `GET /v1/org`, `GET /v1/org/members`, `GET /v1/org/invites`, `GET /v1/me` | Invite (`POST /v1/org/invites {email}`, valid seven days), cancel an invite (`DELETE /v1/org/invites/{id}`), remove a member (`DELETE /v1/org/members/{id}`) |
| `/settings/auth` | Auth | `GET /v1/org/sso`, `GET /v1/me` | Single sign-on, above |
| `/settings/profile` | Profile | `GET /v1/me` | Rename (`PATCH /v1/me`), link a provider (`POST /v1/me/identities` → its link), unlink (`DELETE /v1/me/identities/{provider}`) |
| `/settings/installs` | Installs | `GET /v1/installs` | Sign out an install (`DELETE /v1/installs/{id}`) |
| `/admin`, `/admin/*` | The staff view (Glyphh's staff only) | `/v1/admin/*` | Dashboard, infrastructure, log alerts, organisations and people, plans, traffic, marketing links, Ada versions, the audit log; and the games' admin (`/api/games*`, `server/gamesAdmin.ts`) |

The platform's own routes: `/login`, `/auth/login`, `/auth/callback`, `/auth/logout` (POST), `/auth/session`,
`/auth/providers` (the server's, passed through), `/api/v1/*`, `/api/ada/v1/*`, `/api/marketplace` and `/api/games*`.
Writes must come from this origin.

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
| `GAMES_HOST` | The host the games answer on (default `games.glyphh.ai`) |
| `GAME_ADMIN_KEY_FRANK`, `_CRABBY`, `_MAHJ`, `_CAROL` | Each game's own admin key, for the staff view's games admin; a game without one shows as not connected. `GAME_URL_<GAME>` points at another address of a game |

The Marketplace needs no setting: the repository it reads is public.

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

A demo of Ada, kept: it is not the bots product, which is gone. Teach a bot: the visitor makes up a rule for approving
expenses and keeps it to themselves. A bot that knows nothing
works through 40 expenses: it asks the visitor where Ada is under 75% sure (and about the first five whatever she
thinks), and where she is sure but has little to stand on (the bot's own gate: the two closest answers must each be
50% alike or more and both say what she says); otherwise it decides alone. The visitor answers, and says whether each decision made alone was
right. Every answer is recorded, Ada learns the roles' weights again every five answers from the tenth (once both
outcomes are there), and the page shows the questions falling away: a cell an expense (asked, alone and right, alone
and wrong), what the visitor's decisions turn on as Ada learned it, and at the end how many of the 40 the bot asked
about. No language model runs: the bot runs on Ada alone, and the page says so. Ada is the model, never the bot.

The start is the bot itself: its mascot (`demo/public/bot/mascot.svg`, the Glyphh cat with the mohawk, the "spiky"
head of `os/src/renderer/character.js`), "Meet the bot", three steps and Start; the mascot sits beside everything
the bot says during a take, and the reminder and the small print come only once a take is going.

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

Measured against Ada Cloud on 2026-11-12 with a script answering by a known rule (this loop, six rules, three takes
of 40 expenses each). On Ada's own ask alone the bot asked 9.2 times a take and got 2.3 of its 30.8 decisions wrong
(92% right); the wrong ones were calls she was about 100% sure of with nothing close to stand on (`decide` does not
read `min_sim`; the closest answer was 63% alike at the median, against 78% for the right ones). With the bot's gate
it asks 16.4 times a take and gets 0.7 of 23.6 wrong (97% right), 3.5 questions and 0.3 wrong in the last 20:

| Rule | Asked of 40 | Wrong |
|---|---|---|
| No receipt, no money | 12 | 0.0 |
| Nothing over $500 | 15 | 0.3 |
| Only travel is paid | 21 | 0.3 |
| Sales never gets meals or gifts | 15 | 0.7 |
| Engineering gets anything, others under $300 | 22 | 0.7 |
| The company policy (a receipt, and within limit or pre-approved) | 13 | 2.0 |

A rule on one field is learned nearly without error; one that joins two fields still errs. Without the gate and with
no rule at all (a coin toss) the bot went back to asking 8 of the last 10.

Every demo page wears the platform's look: `demo/public/platform.css` (dark-hc's tokens, white buttons, 8px corners,
the wordmark), loaded after each page's own stylesheet.

## games.glyphh.ai

The same process answers `games.glyphh.ai` with the games Glyphh makes (`server/games.ts`, `games/public`): plain
pages in the platform's look (`games/public/games.css`), no sign-in, no session, no `/api`. `/` is the front page, a
card per game; each game is one entry in `games/public/games.js` (`soon: true` shows its card without a link) and a
folder of its own. The games run on their own sites; these pages show them and link there. Every game's page is laid
out by `games/public/game.css` and `game.js` (the copy buttons, one video at a time), and has the same parts: a hero,
its videos (played from the game's own site, with a poster kept here), screenshots (its `shots` folder), how to play,
what is in it, how it connects to Claude (its connector's address and tools), its price, and Advertise, which writes
to support@glyphh.ai. Links to a game carry `?src=games` so the game's admin counts what the page sends.

- `/free-fall-frank/` is Free Fall Frank (freefallfrank.com): its videos are `/ad.mp4`, `/ad2.mp4` and `/ad3.mp4`,
  its screenshots were taken from the game with its own bot playing, its connector is `https://freefallfrank.com/mcp`,
  and it has the second level, ROCK BOTTOM ($0.99 once, with a free taste), building a level and making a Frank.
- `/bams-and-brags/` is Bams & Brags (bamsandbrags.com), American mah jongg: its reel is `/landing/reel-720.mp4`, its
  screenshots are its landing page's own, its connector is `https://bamsandbrags.com/mcp`, and it has leagues
  ($29.99 once to start one) and the pass ($2.99 once).
- `/crabby-knife-fight/` is Crabby Knife Fight (crabbyknifefight.com), a platformer: its videos are
  `/landing/play-wide.mp4` and `/landing/play-tall.mp4`, its screenshots are its landing page's own, its connector is
  `https://crabbyknifefight.com/mcp`, and it is free.

What a page says of a game (features, prices, the connector's tools) is taken from that game's own landing page and
code; when the game changes, its page here is changed with it.

Production is the Fly app `glyphh-ai-app` (`fly.toml`), deployed by CI (`.github/workflows/ci.yml`) on a merge to
main.

## Develop

Node 22 or later.

```bash
npm ci
cp .env.example .env        # then set PLATFORM_CLIENT_ID, PLATFORM_CLIENT_SECRET and SESSION_SECRET
npm run fake-server         # a stand-in server with sample data on FAKE_SERVER_PORT (default 8080): the org on Free,
                            # Ada Cloud on (its API at /ada/v1; FAKE_ADA=off for a server without it);
                            # FAKE_LLM=on for hosted models' tokens, the overage balance and top-ups;
                            # FAKE_STAFF=on to sign in as Glyphh's staff
npm run dev                 # the platform on PLATFORM_URL (default http://localhost:3000), hot reload
npm test                    # route handlers, API calls and every page, against fake servers; never the network
npm run typecheck
npm run build && npm start  # production build
```

With the fake server, any client id and secret will do; `SESSION_SECRET` from `openssl rand -base64 32`. Logging in
runs the whole OAuth round trip and lands on Home. The Marketplace is read from GitHub by the platform itself, in
development too.

## Layout

| Path | What |
|---|---|
| `server/` | The route handlers (Hono on Node): `app.ts` the routes, `oauth.ts` the calls to the token endpoint, `seal.ts` the cookie (AES-256-GCM), `config.ts` the settings, `marketplace.ts` the Marketplace's reader, `gamesAdmin.ts` the games' admin; `demo.ts`, `voice.ts`, `bot.ts` and `games.ts` the other hosts |
| `src/api/` | The server's types, the `/api/v1` client, one TanStack Query hook per read and write |
| `src/pages/` | One folder per page; sign-in and consent in `pages/flows/`, Settings in `pages/settings/`, Ada in `pages/ada/`, the Marketplace in `pages/marketplace/` |
| `src/admin/`, `src/games/` | The staff view and its games admin |
| `src/routes/` | The route table and the two layouts with their sidebars |
| `src/layout/` | The app shell, sidebar, top bar, account menu, page headers, settings sections, the sign-in card |
| `src/ui/` | The component library, a folder each with its CSS Module; nothing in it knows the API |
| `src/styles/` | `tokens.css` (every colour, size and font for the `dark`, `light`, `dark-hc` and `light-hc` themes), `base.css` |
| `dev/fake-server.ts` | The stand-in server |

## Standards

- Plain British English in the UI, short and concrete. Labels never darker than `#999` on a dark background.
- Tests for every route handler and API call; the pages against a fake server.
- Commits: one step each; Claude's end with its `Co-Authored-By` line.
