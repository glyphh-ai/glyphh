# Glyphh

The one doc for the relaunch (Chris, 2026-10-13 and 14): the [product](#product), the [architecture](#architecture), the [data model](#data-model) and the [plans](#plans). It replaces the programs, rrotor and machines architecture; that version is in git history (`25c1288`).

## Product

**Glyphh makes mods for Claude, as a business** (Chris, 2026-10-14). A mod is a Claude Code plugin that adds commands, tools and panels to Claude. Each mod is its own product, installed on its own from one Glyphh marketplace; one Glyphh account and one subscription turn them on.

The first mods:

| Mod | What it is | Plans |
|---|---|---|
| `glyphh` | The account: sign in, license, account, org, plan and billing panels, and the browser machine every other mod uses | Every plan; the others depend on it |
| `glyphh-workspaces` | Workspaces: a layout grid of live web tabs plus the Claude session it runs (model, folder, permission mode, effort); switching workspaces switches all of it | Every plan; Free up to 2 workspaces |
| `glyphh-rpa` | A browser for Claude apart from yours: named profiles signed in only where you choose, tasks recorded once and run as tools, Claude watched live in a panel and stopped for your approval where it matters | Pro and Team |

- **Pro and Team include every mod**, and every mod as it ships, so the subscription grows in value. One mod sold on its own as an add-on can come later without a redesign.
- **Everything is in Claude.** Every screen is a panel Claude shows. There is no Glyphh app and no Glyphh web UI; the only pages are the device sign-in's and Stripe's own.
- **Desktop first, then the CLI.** The same mods run in both. In the CLI they look and feel CLI native.
- **They look like Claude.** Fonts and colors follow the person's Claude theme.
- **Functional first.** Every screen works before design draws it; design then builds the screens.

## Architecture

![The whole system](img/architecture.png)

```mermaid
flowchart TB
    subgraph Machine["The person's machine"]
        subgraph Claude["Claude, desktop or CLI"]
            Base["glyphh<br/>account, panels"]
            WS["glyphh-workspaces"]
            RPA["glyphh-rpa"]
        end
        BM["Browser machine<br/>glyphh's local MCP server"]
        Chrome["Chrome<br/>tabs, sign-ins"]
        Local[("~/.glyphh")]
        Base --> BM
        WS --> BM
        RPA --> BM
        BM --> Chrome
        Base --> Local
        WS --> Local
        RPA --> Local
    end

    subgraph Cloud["Glyphh cloud"]
        API["API server<br/>accounts, org, seats, installs, license"]
        DB[("Postgres")]
        API --- DB
    end

    Market["glyphh-ai/releases<br/>the marketplace"]
    Stripe["Stripe"]
    SignIn["Google, GitHub"]

    Base <-- "device flow, license" --> API
    Market -- "/plugin install" --> Claude
    API --> Stripe
    API --> SignIn
```

Three parts: the mods on the machine, one small server, and the marketplace they are installed from. **What a person makes stays on their machine; the cloud holds only who they are, their org and what they pay for.**

### Mods and how they are installed

- **A mod is a Claude Code plugin** whose hooks are a code module (`hooks/hooks.json` naming `register.tsx`, with `.claude-plugin/plugin.json`). It hooks Claude's events (session start, commands, tool calls, drawing) and reaches everything else through the engine (`$`): files, HTTP, processes, panels, MCP servers.
- **Installed from the marketplace**, in a terminal: `/plugin install glyphh-workspaces --marketplace glyphh-ai/releases`. Installed at the user scope, a mod loads in every session, the desktop app's Code tab too. Every mod depends on `glyphh` (`plugin.json` `dependencies`).
- **Source and releases are apart.** `glyphh-ai/glyphh` (private) holds the source, one folder per mod (`mods/glyphh`, `mods/glyphh-workspaces`, `mods/glyphh-rpa`), with their tests. `glyphh-ai/releases` (public) is the marketplace: `.claude-plugin/marketplace.json` listing every mod, and each mod as one built, minified module. Nobody installing a mod gets the source, the tests or the history.
- **Each mod checks the license** when a session starts: a mod the license does not include draws only a panel that says which plans include it.
- **Under development** a mod runs from its folder: `claude --plugin-dir <folder>`, or on the desktop linked into the session's mods folder with hot reloading.

### Two kinds of panel

| | Mod panels | MCP App panels |
|---|---|---|
| What | Drawn from Claude's own elements: boxes, text, buttons, inputs, selects, links, markdown, SVG | An HTML page with scripts, which an MCP tool returns (`text/html;profile=mcp-app`, at a `ui://` address) and Claude shows in a frame |
| Can | Forms, lists, actions, at once on desktop and CLI | Live pictures, video, take control, anything a page can do; the host passes its theme as CSS variables (`--color-*`, `--font-*`) |
| Cannot | Pictures (desktop), scripts, video | Draw in the CLI's own terminal |
| Used for | Account, org, plan, billing, workspaces, a site's commands | A live tab, take control, record |

Proved on 2026-10-12 (`glyphh-ai/server`, branch `proto/stream`): an MCP App panel in Claude showed a machine's screen live and took control of it. What it taught still holds: Claude's panel frame preflights every POST; tickets stay out of URLs; a panel's `ui://` address carries its version, since hosts keep its HTML by address.

### `glyphh`: the account and the browser machine

- **Sign in** by device flow: `/glyphh` shows the code and opens the link in Claude's browser pane (in the CLI, prints it); the person signs in with Google or GitHub; the mod, polling, gets the install's token. One sign-in serves every mod.
- **License:** fetched and checked (Ed25519) at start and refreshed daily; every mod reads it.
- **Panels** (mod panels): account, org, plan, billing.
- **The browser machine:** `glyphh` ships a local MCP server (the plugin's own, started by Claude), which owns Chrome:
    - Chrome driven over a private pipe (`--remote-debugging-pipe`), never a debugging port, one Chrome per **named profile** (`~/.glyphh/profiles/<name>/`): an isolated browser holding only the sign-ins made in it, kept on disk so a site signed in once stays signed in. A profile is open in one Chrome at a time, and the browser machine is its one owner.
    - Render, watch, take control, drive and record are its own local API; the other mods build on it.
    - Its MCP App panels show a tab live (frames, or WebRTC where the frame allows it) with take control: the person's clicks, keys and paste go into the tab while Claude waits, and Claude sees no picture while they hold it, so a password or a code never reaches the model.
    - Only this machine's Claude reaches it; other agents could pair with it later.

### `glyphh-workspaces`

Built from `~/development/glyphh/workspaces` (its README holds what a mod can and cannot do).

- **Workspaces:** switch with `/dip`, by number or name. A workspace sets the session's model, folder, permission mode and effort, and opens its grid.
- **Tabs:** each browser cell is a tab with a URL. **No redirect** keeps a tab in its cell when the site tries to hand itself to its native app (Slack, Teams, Zoom, Discord, Notion), as `glyphh-ai/app`'s `forceWeb` did.
- **Live pages:** the browser machine renders every tab.
    - **Desktop:** the layout as one page in Claude's browser pane (`/stream`), each tab as WebRTC video (JPEG when WebRTC fails); clicks, keys and scrolls go back.
    - **CLI:** frames drawn in the terminal with the kitty graphics protocol (Ghostty, kitty), the grid in characters, dividers dragged with the mouse.
- **Saved as it is left:** dragged sizes are written back to the workspace's file.
- **The limit:** the mod registers each workspace's name with the server when it creates one; past the plan's limit it is refused.
- **Panel** (mod panel): list, create, edit (model, folder, permission mode, effort, grid, tabs), delete.

### `glyphh-rpa`

**A browser for Claude, apart from yours** (Chris, 2026-10-14). Claude never works in the person's own browser: it works in a named profile that holds only the sign-ins the person made in it, so a mistake reaches those accounts and nothing else (not their own email, bank or saved passwords). The person records a task once or lets Claude work it out, watches Claude do it live in a panel in Claude, and approves the steps that matter. A mini bot in Claude.

**Everything is an MCP tool**, so Claude does it for the person. `glyphh-rpa` ships its own local MCP server, built on the browser machine; its tools and its live panel are what Claude uses, and a skill teaches Claude the flow. The person asks in plain words:

> Use Glyphh to post our weekly update to LinkedIn. Ask me to approve before it posts. Work it out, then let's test it.

and Claude:

1. **Opens a Glyphh panel** (`panel_open`): the profile's browser, live, in Claude.
2. **Picks or makes a profile** (`profile_list`, `profile_create`), asking the person what to call it ("Work", "Shopping").
3. **Asks the person to sign in** (`ask_user`, kind `login`): the panel hands them control; they type their own password and 2FA; Claude sees no picture while they hold it, so a credential never reaches the model. The sign-in stays in that profile.
4. **Asks what to call the task** (`ask_user`, kind `text`), and which steps need approval.
5. **Works it out:** records the person doing it once (`record_start`, `record_stop`), or explores the site itself (`page_read`, `page_act`), proposing steps the person sees in the panel.
6. **Saves it** (`site_save`, `sequence_save`): a sequence of steps, each with its approval rule, which becomes a tool.
7. **Tests it** (`run`): the panel shows every step live; a step set to `ask` stops with "Claude wants to click Post" and waits for **Approve**, **Decline** or **Take control**.

| MCP tool | Does |
|---|---|
| `profile_list` · `profile_create {name}` · `profile_delete {name}` | The named profiles |
| `panel_open {profile, url?}` | The live panel (MCP App): the profile's tab, steps, approvals, take control |
| `ask_user {profile, kind, prompt}` | Asks the person in the panel and waits: `login` (they take control and sign in), `approve`, `choose`, `text` |
| `page_read {profile}` | The page's text, as untrusted content |
| `page_act {profile, action}` | One step: click, type, go to, read, a script; under the approval rules |
| `record_start {profile}` · `record_stop` | Captures the person's steps (with selectors) as a draft sequence |
| `site_save {name, match, profile}` | A site: the URLs it matches and the profile it runs in |
| `sequence_save {site, name, steps}` | A sequence; each step `auto` or `ask` |
| `run {site, sequence, inputs?}` | Runs it live in the panel, stopping at every `ask` |
| `sites_list` · `log_read {site?}` | Saved sites and sequences; what ran, who did each step (Claude or the person) and what was approved |

- **Approval rules:** reading runs (`auto`); sending, posting, buying, deleting and anything set to `ask` waits for the person. When nobody is watching (a run on a clock, or started by another agent), `ask` means refused.
- **Saved sequences are tools** too (`<site>_<sequence>`), so Claude runs them by name later: "post the weekly update".
- **Commands and sequences** keep `glyphh-ai/app`'s format (`src/shared/rpa.ts`), with an approval rule on each step.
- **Panels:** the live panel (MCP App: watch, record, approve, take control); a site's sequences (mod panel: run, edit, delete).

### On the machine: `~/.glyphh`

Nothing here goes to the cloud.

| Path | Mod | What |
|---|---|---|
| `install.json` | `glyphh` | This install's id and token, mode 0600 |
| `license.json` | `glyphh` | The signed license: plan, limits, mods, expiry |
| `profiles/<name>/` | `glyphh` | A named profile: an isolated Chrome profile with only the sign-ins made in it |
| `workspaces/<slug>.json` | `glyphh-workspaces` | A workspace: session, grid with its saved sizes, cells, tabs |
| `rpa/<slug>.json` | `glyphh-rpa` | A site: what it matches, its profile, its commands and sequences with their approval rules |
| `rpa/log/` | `glyphh-rpa` | What ran: each step, who did it, what was approved |

### The server

The `glyphh-ai/server` repo: Python 3.13, FastAPI, Pydantic v2, SQLAlchemy 2 (async) on Postgres, in Docker. Built database first, then API; 100% test coverage; errors with stable codes and a trace id; small files.

- **Sign in, by device flow (RFC 8628).** Each approval is an **install**: one machine, signed in once for every mod.
- **Org.** The first user creates the org, is its admin and handles all billing. A user belongs to exactly one org. The admin invites members by email; an invite is accepted by signing in.
- **Plans and seats.** Each seat is a member. The admin subscribes through Stripe and adds or removes seats; Stripe's webhooks keep the org's subscription and seat count true.
- **Mods.** The server keeps the catalog of mods. A plan version includes every mod (Pro, Team) or only the free ones (Free).
- **License.** The server signs a short-lived license for each install (plan, limits, the mods it includes, expiry) that the mods check with its public key.
- **Limits are enforced by the server**, at the moment they would be crossed:
    - **members:** an invite is refused when the org is at its plan's limit or out of seats;
    - **installs:** a device approval is refused when the user is at their limit;
    - **workspaces:** creating one past the limit is refused. Only the name and the user go to the server, nothing of what is in it.
- **What a mod gates locally** (a mod not in the license) can be edited out by someone determined; what is worth paying for is enforced here.

### API

JSON over HTTPS under `/v1`, described by `/openapi.json`. Every call but the device flow's, the plans and mods lists and Stripe's webhook carries the install's token (`Authorization: Bearer`). Refusals are `{"error": {"code", "message", "trace_id"}}`; a limit reached is `E_LIMIT`, with `limit`, `used`, `max` and the `plan` that would lift it.

**Device flow** (RFC 8628):

| Call | Does |
|---|---|
| `POST /v1/device/code` `{name, surface, mod_version}` | Starts a sign-in: `device_code`, `user_code`, `verification_uri`, `verification_uri_complete`, `interval`, `expires_in` |
| `POST /v1/device/token` `{device_code}` | Polled: `authorization_pending`, `slow_down`, `expired_token`, `access_denied`, or the install's `access_token` and `install_id` |
| `GET /v1/device?code=` | The page the link opens: Continue with Google or GitHub, then this install is approved and the page says to go back to Claude |

Signing in the first time makes the person's org (Free, them its admin), unless an invite for their email is waiting, in which case they join that org. The install is refused past the plan's `max_installs`.

**Account:**

| Call | Does |
|---|---|
| `GET /v1/me` | The user, their org and role, the plan version, its limits and mods, and what is used (members, seats, installs, workspaces) |
| `PATCH /v1/me` `{name}` | Rename |
| `GET /v1/installs` · `DELETE /v1/installs/{id}` | List installs; revoke one (signs that machine out) |
| `POST /v1/sign-out` | Revoke this install |
| `GET /v1/license` | This install's license, signed (Ed25519): plan, limits, `mods`, `expires_at` (24 hours) |
| `GET /v1/license/key` | The public key the mods check it with |
| `GET /v1/workspaces` · `POST /v1/workspaces` `{name}` · `PATCH /v1/workspaces/{name}` `{name}` · `DELETE /v1/workspaces/{name}` | The user's workspace names; creating one past `max_workspaces` is refused |

**Org** (writes are the admin's):

| Call | Does |
|---|---|
| `GET /v1/org` · `PATCH /v1/org` `{name}` | The org |
| `GET /v1/org/members` · `DELETE /v1/org/members/{user_id}` | Members; remove one (never the admin) |
| `GET /v1/org/invites` · `POST /v1/org/invites` `{email}` · `DELETE /v1/org/invites/{id}` | Invites; one is refused past the plan's members or the seats bought. An invite answers with its link to share |
| `POST /v1/invites/accept` `{token}` | An existing user joins: only when their own org has no one else and nothing paid, which is then removed |

**Mods, plans and billing** (writes are the admin's):

| Call | Does |
|---|---|
| `GET /v1/mods` | The catalog: each mod's slug, name, description, whether it is free, and the plans that include it |
| `GET /v1/plans` | Each plan's newest version: price per seat, limits, its mods |
| `POST /v1/billing/checkout` `{plan, seats}` | Stripe Checkout's address, to open in the browser pane |
| `POST /v1/billing/plan` `{plan}` | Change plan: the newest version of it, prorated |
| `POST /v1/billing/seats` `{seats}` | Change the seats; never below the members and open invites |
| `POST /v1/billing/portal` | Stripe's portal address: card, invoices, cancel |
| `POST /v1/stripe/webhook` | Stripe's events keep `orgs` true: plan version, seats, status |

### Panels

Each works before design draws it.

| Panel | Mod | Kind |
|---|---|---|
| Sign in: the code, the link, waiting, signed in | `glyphh` | Mod |
| Account: name, email, providers, installs (revoke), sign out | `glyphh` | Mod |
| Org: name, members (remove), invites (send, revoke) | `glyphh` | Mod |
| Plan: plan, limits, usage, mods included, change plan | `glyphh` | Mod |
| Billing (admin): seats, checkout, Stripe's portal | `glyphh` | Mod |
| A live tab with take control | `glyphh` | MCP App |
| Workspaces: list, create, edit, delete | `glyphh-workspaces` | Mod |
| The live panel: the profile's tab, the steps, Approve / Decline / Take control, Record and Stop, sign in | `glyphh-rpa` | MCP App |
| A site's commands and sequences: run, edit, delete | `glyphh-rpa` | Mod |
| Not in your plan: which plans include this mod | every mod | Mod |

### To prove first

- **MCP App panels from a plugin's local MCP server in the Code tab:** proved from the server's remote MCP; to prove from `glyphh`'s own local server, with one live tab and take control.
- **Dependencies through the marketplace:** that installing `glyphh-workspaces` brings `glyphh` with it.
- **A built mod loads:** that one minified module per mod loads and validates as its source does.
- **Google sign-in in the browser machine's Chrome:** Google may refuse a sign-in in a Chrome under automation ("This browser or app may not be secure"). Gmail and Calendar tabs depend on it.
- **Sign-in pages from a panel:** whether Google allows its sign-in page in Claude's browser pane.

## Data model

### In the cloud

![The cloud's tables](img/data-model-cloud.png)

```mermaid
erDiagram
    PLANS ||--|{ PLAN_VERSIONS : "has versions"
    PLAN_VERSIONS ||--o{ ORGS : "pinned by"
    ORGS ||--|{ USERS : "members"
    ORGS ||--o{ INVITES : "sends"
    USERS ||--|{ IDENTITIES : "signs in with"
    USERS ||--o{ INSTALLS : "has"
    USERS ||--o{ WORKSPACES : "owns"
    INSTALLS ||--o{ TOKENS : "holds"
    INSTALLS ||--o{ DEVICE_CODES : "approved by"
    MODS }o..o{ PLAN_VERSIONS : "free, or all_mods"
    PLANS {
        uuid id PK
        text name
        bool active
        int sort
    }
    PLAN_VERSIONS {
        uuid id PK
        uuid plan_id FK
        int version
        text stripe_price_id UK
        int seat_price_cents
        int max_members
        int max_installs
        int max_workspaces
        bool all_mods
        timestamp created_at
    }
    MODS {
        text slug PK
        text name
        text description
        bool free
        bool active
        int sort
    }
    ORGS {
        uuid id PK
        text name
        uuid plan_version_id FK
        uuid admin_user_id FK
        text stripe_customer_id
        text stripe_subscription_id
        int seats
        text billing_status
    }
    USERS {
        uuid id PK
        uuid org_id FK
        text email
        text name
        text role
    }
    IDENTITIES {
        text provider PK
        text provider_user_id PK
        uuid user_id FK
    }
    INVITES {
        uuid id PK
        uuid org_id FK
        text email
        text token_hash
        timestamp expires_at
        timestamp accepted_at
    }
    INSTALLS {
        uuid id PK
        uuid user_id FK
        text name
        text surface
        text mod_version
        timestamp last_seen_at
        timestamp revoked_at
    }
    WORKSPACES {
        uuid user_id FK
        text name
        timestamp created_at
    }
    DEVICE_CODES {
        text device_code_hash PK
        text user_code UK
        uuid install_id FK
        timestamp expires_at
        timestamp approved_at
    }
    TOKENS {
        uuid id PK
        uuid install_id FK
        text token_hash UK
        timestamp expires_at
        timestamp revoked_at
    }
```

- **Plan versions never change their price or limits.** Changing either adds a version with its own Stripe price (Stripe prices cannot change either). An org stays on the version it subscribed to (`orgs.plan_version_id`), so an update never touches an org; new orgs get the newest version, and an org moves only when its admin changes plan or we migrate it on purpose.
- **Which mods a version includes:** `all_mods` true includes every active mod, new ones as they ship (Pro, Team); false, only the free ones (Free). A mod once free stays free, so no org ever loses a mod it had.
- **A limit left empty is unlimited.**
- **One org per user:** `users.org_id`, not a memberships table. `role` is `admin` or `member`; the org's first user is its admin (`orgs.admin_user_id`).
- **People are found by the provider's own id** (`identities`), never by email alone.
- **Installs:** one per device-flow approval, one per machine for every mod, with its surface (`desktop` or `cli`). Revoking one signs that machine out. Its tokens are stored hashed.
- **Workspaces:** names only, for the limit. Everything else about a workspace is in `~/.glyphh`.
- **Tenant isolation:** row-level security keyed on the org.

### On the machine

![What lives in ~/.glyphh](img/data-model-local.png)

- **A workspace is one file**, `workspaces/<slug>.json`: its session (model, folder, permission mode, effort), its grid (columns, rows and their saved sizes), the desktop panes it opens, its cells and its tabs.
- **A cell** sits at a column and row with its spans, and is a `browser` (showing one of the workspace's tabs), `file`, `editor`, `terminal` or `diff`.
- **A tab** is a URL with its name and no redirect.
- **A site is one file**, `rpa/<slug>.json`: what URLs it matches, its commands, and sequences of steps that call them (`recorded` when made with Record). A tab on a matching URL gets the site's tools.
- **A site runs in one named profile** (`profiles/<name>/`), signed in only where the person signed in; a workspace tab names its profile too.
- **Each step of a sequence has an approval rule:** `auto` or `ask`.
- **`license.json`** is refreshed from the server through the install's token and carries the plan's limits and mods.

## Plans

Billed per seat, per month. Installs and workspaces are per user.

| | Free | Pro | Team |
|---|---|---|---|
| Price per seat | $0 | $8 | $16 |
| Mods | `glyphh`, `glyphh-workspaces` | Every mod | Every mod |
| Members | 1 | 1 | Unlimited |
| Installs | 1 | 5 | 10 |
| Workspaces | 2 | 10 | Unlimited |

Team's installs are capped so one seat can't be shared across a team's machines.
