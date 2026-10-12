# Glyphh design

The one design doc: what Glyphh is and how it looks, the decisions, the brand, where the screens are and how to build them, and how the design agent and the code agent work together. The boards are in `screens/`, the artwork in `brand/`. What is still open is in the server's doc, under Open (https://github.com/glyphh-ai/server/blob/main/docs/architecture.md#open).

## The brief

### What Glyphh is

What if you could combine every AI super power into one? Glyphh does. A member's **super powers** are bots that run on their own machine (**rrotor**), always on, each with its own models, connections, folders and browser. **Glyphh** is the main assistant that orchestrates them. Members reach it all from Claude or ChatGPT through the Glyphh plugin, or from any browser. Under it: about 3,900 models across 125 providers on the member's own keys, and about 3,500 connections (Gmail, Slack, Salesforce, ...).

### The direction

**An ultra-modern AI startup.** Confident, precise, a little playful. A fresh direction for **fonts and colours**, carried through every surface so Glyphh feels like one brand everywhere.

**Keep:**

- **The Glyphh logo.**
- **The cat avatars:** the Glyphh cat and the super power faces (16 bodies). They are alive: **the blink**, the little **hop**, and the glowing **ring with its comet** from the current site. Every super power wears a cat, and its **mood** shows in its eye (thinking, working, done, stuck, ...). The artwork and the motion are in `brand/` (see Brand assets, below).
- **The look and feel of the old desktop app**, reworked: it becomes rrotor's UI (below).

### Surfaces and screens

#### 1. Marketing site (glyphh.ai)

The beta page today: the cat in its ring, the super powers orbiting into it, "What if you could combine every AI super power into one?", **Sign up for the beta** (email sales@glyphh.ai). Rebrand it, and give it room to grow into a full site.

#### 2. app.glyphh.ai: the platform, and the same views as cards

What is in the system for a person (powers, super powers and their grants, machines, catalogs, usage, billing, members), as pages, and the same views as cards in Claude and ChatGPT, built from one component library (`@glyphh-ai/ui`, in `glyphh-ai/platform`). The work itself runs on the member's machines and shows in rrotor's UI. Every page has its own address.

**Pages only a browser can show** (something sends the person here):

- **Sign in:** Continue with Google, Continue with GitHub.
- **Allow:** "Claude wants to use your Glyphh": allow or deny, for an AI host (Claude, ChatGPT, Codex).
- **Approve a code:** "Is this code on your new machine?", for a machine or a CLI signing in.
- **Join:** "You're invited to Acme", then sign in, then "You've joined Acme".
- **Return pages:** you're connected (go back to Claude), machine approved, checkout done ("You're on Pro") or cancelled, a service connected ("Gmail is connected").
- **Error:** what happened, what to do, and its **trace id**.

**The app itself** (signed in):

- **My machines (home):** each machine, online or not, where it runs; tap to open its UI.
- **Deploy a machine:** the one-click hosts (Fly, AWS, Azure, GCP, DigitalOcean, Hetzner, any VPS), then live status: waiting, registered, starting, ready.
- **Add Glyphh to your AI:** Claude, ChatGPT and Codex, each with its setup steps.
- **Account:** profile, plan and usage, Stripe's portal for payment details, connected AI hosts (disconnect one), sign out.
- **Opening a machine:** connecting, and "this machine is offline".
- **Super powers, Powers, Marketplace, Usage:** what is in the system for the person; **Org** for org admins and **Glyphh admin** for super admins (see Navigation, below).

**States for every page:** loading, success, expired link, refused, error with its trace id.

#### 3. rrotor's UI (the old app, reworked)

The app every machine serves, in the browser and inside Claude. It gets a UI of its own, designed next; it is not built from `@glyphh-ai/ui`.

- **Home:** the machine, its super powers, what is running now.
- **Glyphh, the main assistant:** chat, with a **talk button** (voice), and the swarm's live status beside it.
- **Super powers rail:** each with its cat, name, status dot.
- **Super power editor:**
  - **identity row:** avatar, voice (with a sample to hear), name;
  - description and instructions;
  - **sliders:** personality (serious to playful), directness (gentle to blunt), temperament (kind to spicy);
  - effort, and its loop (Claude Code, Codex, or the Glyphh loop on a model);
  - its **powers map:** folders (read or write), connections, models, skills, browsers, other super powers;
  - tool permissions (allow, ask, deny), and schedules.
- **Runs:** history and the **live view**: steps, logs, the browser screen, **take control** to sign in to a website.
- **Settings:** theme, notifications, voice.

Catalogs, connections, usage, billing and org admin are the platform's (above), not rrotor's.

#### 4. Cards inside Claude and ChatGPT (through the plugin)

The same screens as app.glyphh.ai, built from the same components, as native-feeling cards in the chat, taking the host's light or dark theme. Only after sign-in: signing in itself is always a browser page.

- **My machines:** a list, online or not, tap to open.
- **Deploy a machine:** the steps, then live status (waiting, registered, starting, ready).
- **Usage and plan:** "what have I used this month?"
- **The swarm:** what is running, live.
- **Needs you:** a super power asking a question, or for permission.

### Must haves

- **Dark first, with a light theme.** Contrast at WCAG AA or better.
- **Phone, iPad and desktop.** Inside Claude's chat it adapts to the host's theme.
- **Motion with meaning:** the blink, the hop, the comet; everything still for people who turn motion off.
- **Tokens:** colour, type scale, spacing, radius, shadow, motion; for light and dark.
- **Components:**
  - buttons, inputs, selects, toggles, sliders, chips, status dots;
  - avatars (the cats), cards, tables, tabs, modals;
  - toasts (with a trace id), empty states, skeletons;
  - code and terminal blocks, provider logo tiles.
- **Voice:** plain, short, confident. Errors say what happened and what to do.

### Deliverables

1. Brand: logo usage, the cat set and its motion, the colour palette, the typefaces.
2. Tokens for light and dark.
3. The component library.
4. The screens above, starting with **app.glyphh.ai** (sign-in first), then **rrotor's UI**, then the **cards in the chat**.

## Decisions

### Logo

- **One logo, on every ground:** `brand/logo/glyphh-logo-black.png`, the ink mark in its white sticker border. No light, dark or white version, no recolouring.
- The cat alone is the favicon and the small app icon.

### The cats

- **Black and white.** A super power's colour lives only in its eye; the body is ink, the sticker border white. Glyphh's own eye is white.
- **Moods change the eye:**
  - Done: a small check as the eyeball.
  - Playful, and the Wink face: a heart for an eye, lashes on the eye's outline; the whole eye closes on the blink.
  - The rest as drawn in `brand/moods/`.
- **On a status page, Glyphh's eye takes the status colour:** violet on success, red on failure, pink when it needs you, cyan while thinking.
- **On light grounds:** no black fill behind a cat or a logo tile; only a thin outline.

### Colour: Ink & Violet

| Role | Dark | Light |
|---|---|---|
| Ground | Ink `#0B0A0F` | Paper `#F5F5F7` |
| Accent (main action, the ring, running) | Violet `#7C4DFF`, white text on it | the same |
| Accent as text | `#B49CFF` | `#6A3DF0` |
| Thinking, info | Ion `#6FD8FF` | `#00679E` as text |
| Needs you | Pink `#F062D0` | `#C2189C` as text |
| Stuck, errors | Red `#FF4D4D` | `#C21D3C` as text |

Yellow, lime, green and orange were tried and dropped.

- **Signal colours are for status only:** Ion, Pink and Red mean thinking, needs you and stuck, nowhere else.
- **Power colours belong to the cats:** the eye colours a super power can wear (Frost `#FFFFFF`, Violet, Ion, Iris `#B49CFF`, Bloom `#FF8AD8`, Rose `#FF6B9A`, Azure `#5B8CFF`, Teal `#2EE6D6`) are used only in a cat's eye, never on UI.
- **Kinds are not colour-coded.** Skills, plugins, tasks, apps, a task's steps and the power map's cards all take the accent text colour and are told apart by their icon and label. A super power takes Violet.
- **No tints of their own:** soft or deeper copies of a colour are not new colours; use the values above.

### Type: Red Hat

- Red Hat Display for headlines.
- Red Hat Text for everything you read and press.
- Red Hat Mono for trace ids, codes and logs.

### Buttons

One height everywhere (48–52 px). On a phone, a pair stacks full width. A layout never squeezes a button; the container grows instead.

### Sign-in pages: the brand panel ("rrotor in motion")

The left half on desktop, collapsing to a small ring above the content on a phone:

- **Glyphh in its ring**, winking now and then.
- **Three rings around it,** alternating direction, each slower than the one inside:
  - super powers (cats with varied faces, a new one popping into an empty slot);
  - models;
  - connections.
- **Logo tiles:** neutral boxes with a light outline; only the logo is in its brand colour.
- **Headline:** "Create AI super powers." Line: "Glyphh combines your models, connections and agents into super powers you run on Glyphh machines, anywhere."
- **Footer:** "© 2026 Glyphh AI".

### app.glyphh.ai

- **Machine cards** show up to 8 super powers, each in an outlined square with its name under it (two lines, then an ellipsis), then "+N / See all".
- **See all** opens a dialog with search, status filters and pages.
- **Clicking a super power** opens it on its machine in rrotor. The platform shows and edits what is in the system (powers, grants, settings, catalogs, plans); the work runs on machines and is never run from the web.
- **Every header has the light/dark toggle.** The account menu and the Account page offer Light, Dark or System.

### Logos of other companies

Always the real, full-colour artwork, never a one-colour silhouette. Black marks (OpenAI, GitHub, Grok, Cursor, Anthropic, the AWS wordmark) get an off-white copy for dark grounds. Claude shows the Claude mark; Codex shows OpenAI's.

### Eye colours and the Docker logo

Approved 2026-10-11: the four power colours outside the palette (Bloom, Rose, Azure, Teal) stay as cat eye colours, and laptop machines (Docker hosts) get the Docker logo.

Also approved 2026-10-11: three simple stroked icons on the marketplace boards, a featured star, a drag handle and up/down arrows. And **admin actions are recorded** in an audit log, beside the usage audit log: Org → Audit log for org admins, Glyphh admin → Audit log for super admins (board `AdminAudit`).

### Lists

Everything that can grow is paginated, in the designs as in the build: "Showing 1–5 of 23", Previous, page numbers, Next; on a phone, Previous, "Page 1 of 5", Next.

### Billing

- **One Billing page,** server-old's flow and copy:
  - Current plan, then Credit balance with auto top-up and spend by day, then Plans, then Invoices (View, PDF).
  - Every action opens a dialog: Add funds, Auto top-up, Switch plan.
- **Paying happens inside the page** and matches it: dark on dark, light on light, our fields and violet button. That needs Stripe's Payment Element (see Requests).
- **Credits are dollars** (decided 2026-10-11, as Anthropic does it): the balance, what a plan includes, top-ups and every charge are shown in dollars ("Credit balance: $12.40"). A connection call costs 2¢ for each started 30 seconds; runs cost nothing. Add funds takes $5 to $10,000, and that is the credit added. **Auto top-up reloads to a target:** "when the balance falls below $5, reload to $25", with an optional monthly cap an org admin sets, off by default. Gifts are credit grants in dollars. A plan's included usage **does not carry over**: it expires at the period's end. **The usage a subscription includes is always spent before bought credit** (Chris, 2026-10-12), so bought credit waits, for its year, until the included usage is gone. Auto top-up's trigger, target and cap are each $5 to $10,000, and the cap is at least one reload (target minus trigger). **Bought credit expires a year after purchase**, as Anthropic's does, and Billing shows when.
- **Plans, first numbers** (to adjust): Free $0, 1 seat, $1 of usage a month, 2 machines; Solo $20, 1 seat, $10, 3 machines; Basic $40 a seat, up to 25 seats, $10 a seat, 10 machines; Pro $150 a seat, up to 100 seats, $50 a seat, 50 machines; Enterprise arranged. Extra machines $5 a month (none on Free). These replace the `[BRACKETS]` on the billing, usage and admin boards.
- **Plans are versioned:** a change to a plan is its next version, sold to new orgs; an org keeps the version it is on until it changes plan or a super admin moves it, with **30 days' notice** by email and a banner on Billing.

### Versions and release notes

Decided 2026-10-11. A published power or super power has explicit versions: its manifest carries the version (1.0.0, 1.1.0, ...) and its release notes, and every version is kept, frozen, with them. Publish (`ListingSubmit`) shows the version and its release notes and asks for both; a listing's page and the review screens show the version under review and its notes, and the version history with each one's notes; an installed power shows its version, and a newer version offers its notes before updating. Versions are semver and must be higher than the last published one (a rejected version's number is used up, never reused); release notes are required, up to 2,000 characters; a version number is never reused.

### Usage of powers and super powers

Decided 2026-10-11. Beside the metered connection calls, every use of a power or super power is counted (never its content, never billed): model calls with their tokens in and out as the provider reports them, tool calls, skills, task steps, folders, browsers. Usage pages show models, connections and super powers side by side, by day, user, super power and power; an org admin sees each member's use, model token counts included (counts only, even on the member's own key); a publisher sees their listing's installs, installs used in the last 30 days, and runs.

### Navigation

Decided 2026-10-11 and 2026-10-12: the top nav is Machines, Super powers, Powers and Marketplace; **Org** for org admins (Members, Teams, Models, Connections, Review, Usage, API keys, Audit log, Billing); **Glyphh admin** for super admins (Orgs, Models, Marketplace, Plans, Audit log); the account menu has Usage and API keys. Plans edits each plan's versions and the billing settings: what a connection call costs per started 30 seconds (2¢), and the smallest and largest top-up ($5, $10,000), each change kept with who made it and from when.

### Admin decisions

Decided 2026-10-11, as the admin boards draw them:
- **Providers and models:** a super admin adds, edits, turns off and removes them. Off is for now: members' powers on it are disabled with the reason and come back when it's on again. Removed is for good: those powers can only be deleted. A provider with a black mark has a second logo for dark grounds.
- **Disabling an org:** members can't sign in to it, its machines are cut off, its schedules stop, its billing pauses, its data is kept; Enable undoes it.
- **Teams:** a person can be in many teams; they may add what any of their teams allows, inside the org's list.
- **Many orgs per person:** everyone has a Personal org plus any orgs they join; the host picks which at Allow ("Use with").
- **Review:** org review, then Glyphh review for the marketplace, each step approve, ask for changes or reject, with a thread on the listing; Glyphh's reviewer (a super power on Glyphh's own machine) writes a report a person decides on. Icons are square PNGs (512 px), up to six screenshots (PNG or JPEG, 5 MB each), never SVG uploads.

### Powers: connections and permissions

- **Where it lives:** Powers sits in the top nav beside Machines, with tabs Loops, Connections, Models, Folders, Skills.
- **A connection is always the member's own account.** Pipedream holds the sign-in, which happens on Pipedream's page in a dialog (or its own window when a provider refuses frames). There is no shared org account.
- **Every tool is Allow, Ask or Deny,** grouped by risk: Read, Create and update, Delete. A tool with no setting asks. A super power can carry its own Allow or Deny for runs nobody watches, where Ask is refused.
- **Phones get a compact row per connection:** logo, name, account, one status line, and a chevron (or Reconnect).

### The plugin

The app's screens as cards in the chat, following the host's theme:
- My machines
- Deploy (pick a host, then live status)
- Usage
- The swarm
- Needs you (a question, or a permission)
- Empty, loading and error states

## Brand assets

Everything in `brand/` is the source artwork.

- `logo/`: the Glyphh logo and mascot, as on glyphh.ai (light and dark versions, the favicon).
- `cats/`: the 16 super power faces, each the Glyphh cat with one or two parts changed (eyes, ears, tail, an antenna, a cape, a bolt). `01-glyphh` is Glyphh itself; `02-side-eye` is the face a new super power wears until one is picked.
- `moods/`: Glyphh's moods. A mood changes the eye, so a cat shows what its super power is doing: idle, thinking, generating, done, listening, error, curious, sleepy, playful, dizzy.
- `glyphh-alive.svg`: Glyphh with its motion, as a reference: open it in a browser.

### Motion

- **Blink:** every 5 s, the eye squashes to a tenth of its height and back (the last 8% of the cycle).
- **Hop:** now and then (every 4 to 9 s on the site), a squash, a 7px hop, a squash on landing and a small bounce.
- **Ring and comet** (the site's hero): the cat sits in a glowing ring whose rim turns slowly (14 s a turn); at random moments a bright comet sweeps once round the ring (1.5 s), shedding dust that drifts outward.
- **Pop in:** a cat appears scaled from 0.6 and turned -8°, settling in 0.6 s.
- All of it stops for people who turn motion off.

## Screens

### Where they are

Every board is in `screens/` as a `.dc.html` file, with the logos it uses in `screens/assets/` and the canvas index in `screens/canvas.json`. They come from one Claude Design canvas, **Glyphh Design** (https://claude.ai/artifact/DMiUf6vx7u61MNLDd4anLq), private to Chris; the code agent can't open it and works from this copy. The design agent re-exports it after each round of changes, and the commit says which boards changed. **The design keeps moving:** pull before starting a page, and read its board again rather than working from memory.

- `glyphh-logo-black.png` in `screens/assets/` is the one logo; the full-colour third-party logos have a `-dark` copy where the mark is black; `glyphh-icons*.json` are older single-colour icon paths, kept only so the boards still resolve.

### How to read a board

- **Sketches, not specs.** The boards were drawn before the component library existed. Build every screen from `@glyphh-ai/ui` components; never copy a board's raw colours, sizes or fonts. The boards' values are what `tokens.css` carries (Ink & Violet, Red Hat; see Decisions).
- **One board, every state.** Each board lays out one page in all its states (default, loading, empty, error with trace id, success, validation), at 1200 wide (desktop) and 390 wide (phone). The state name is printed above each frame.
- **Light and dark.** Where a page has both, they are separate canvas pages. The light board is the dark one with `[data-theme="light"]` values: no layout differences.
- **Dialogs** are drawn over a copy of the page beneath them.
- **Placeholders** in `[BRACKETS]` are not decided. Prices, included usage and machines per plan are decided now (Billing, above); the install command is not. Leave the rest visible or ask; don't invent them.
- **Example data** (Northwind, studio-mac, Sam Rivera, Inbox Zero, …) is only example data.
- **The markup is the layout.** It uses `<sc-for>` (a repeat) and `<sc-if>` (a branch), with `{{holes}}` filled from the script.
- **The script at the bottom is the content.** `STATES` (or `PAGES`, `CARDS`) lists every state; the helper functions build the rows, labels, copy and numbers each state shows. The copy is the copy to ship.
- **Cats** are drawn by the `cat()` helper from `brand/cats` paths.
- **They don't open in a browser:** they need the canvas's runtime (`support.js`), which isn't here. Read them as source.

### The pages

| Canvas page | Board file(s) | What it is | Build order |
|---|---|---|---|
| Brand | `Main`, `Palettes`, `Type`, `LogoInUse` | Logo, cats and moods, motion, Ink & Violet, Red Hat, the sign-in panel's animation | n/a |
| Components (requested) | `Components` | Every requested component, each variant and state, dark and light side by side, props named under each: LogoTile, CatRing with the comet, Avatar person and org, TextInput `code`, DescriptionList, Menu radio, check and danger items, Pagination, SegmentedControl, the themed Payment Element, ConnectFrame, bars by day, PowerMap and FlowCanvas nodes | with the page that needs it |
| Sign in | `SignInFlow` | Google / GitHub, loading, signed in, expired, refused, error | 1 |
| Allow a host | `AllowFlow` | "Claude wants to use your Glyphh": allow, deny, connected | 1 |
| Approve a code | `CodeFlow` | Enter a code (validation), confirm the machine, approved | 1 |
| Join an org | `JoinFlow` | Invite: signed out, accept, wrong account, joined | 1 |
| Machines | `PlayerFlow` | Machine cards (8 super powers, then See all), the See all dialog with search and pages, add a machine, connecting, offline, account menu | 2 |
| Light and account | `LightAccount` | The light theme, the Account page, the account menu, signed out | 2 |
| Billing (dark / light) | `BillingFlow`, `BillingLight` | Plan, credit balance in dollars and auto top-up (reload to a target, monthly cap), spend by day, plans with their numbers, invoices with each top-up's expiry; dialogs for Add funds, Auto top-up, Switch plan; Stripe checkout inside the page; the plan-move banner | 3 |
| Plugin | `PluginCards` | The cards in Claude and ChatGPT: machines, deploy, usage, the swarm, needs you | 8 |
| Powers (4 pages) | `PowersFlow`, `PowersMobile`, `PowersLight`, `PowersLightMobile` | Connections through Pipedream (catalog, sign-in, reconnect, disconnect) and tool permissions (Allow, Ask, Deny) | 4 |
| Super power editor (dark / light) | `SuperPowerEdit`, `SuperPowerEditLight` | The power map, identity, sliders, brief, the Powers rail, the Add a power dialog | 5 |
| Task flow (dark / light) | `TaskCanvas`, `TaskCanvasLight` | A Task's Flow tab: the React Flow canvas made editable, the inspector, slots, schedule | 6 |
| Custom powers (dark / light) | `CustomPowers`, `CustomPowersLight` | Skills, plugins, tasks and apps in one list; New power; each type's detail | 5 |
| Marketplace (dark / light) | `Marketplace`, `MarketplaceLight` | Discover, search with pages, a power's and a super power's detail, Add | 7 |
| rrotor · Splash (dark / light) | `RrotorSplash`, `RrotorSplashLight` | rrotor's UI, not the platform: the first screen on a machine, naming the machine before anything else; starting, opening, ready, on a laptop, waking, updating, a failed step, an expired link, someone else's machine, offline | rrotor |
| Org · Members and teams (dark / light) | `OrgTeams`, `OrgTeamsLight` | Members, invites and seats; teams (a person can be in many); a member's teams; remove from a team or the org | Org |
| Org · Allowed models and connections (dark / light) | `OrgLimits`, `OrgLimitsLight` | The limit switches at the org and a team, the allowed lists, adding from the catalog, removing (it turns off for whoever uses it), a member's disabled power | Org |
| Org · Review (dark / light) | `OrgReview`, `OrgReviewLight` | The org admin's review queue: approve for the org, approve and send to Glyphh, request changes, reject; Glyphh's feedback | Discover |
| Publish a listing (dark / light) | `ListingSubmit`, `ListingSubmitLight` | A member publishes a power or super power: icon, screenshots, what it needs, where it goes, the review timeline, changes requested, published, new version, unpublish | Discover |
| Usage (3 pages, dark / light) | `UsageFlow`, `UsageMore`, `UsageAudit` and each `…Light` | By billing period (credits by connector, a connector's tools, a closed period); your usage by super power, power, model, connection, machine; a super power's and a model's usage; the org's usage by person and team; a publisher's stats; the audit log of connector calls and power uses | Usage |
| Glyphh admin · Orgs (dark / light) | `AdminOrgs`, `AdminOrgsLight` | Every org; an org's overview, members, machines, powers, super powers, billing | Admin |
| Glyphh admin · Org actions and plans (dark / light) | `AdminOrgActions`, `AdminOrgActionsLight` | Gift credits, change or comp a plan, move orgs to a new version, disable and enable an org; plans and their versions | Admin |
| Glyphh admin · Models (dark / light) | `AdminCatalog`, `AdminCatalogLight` | Providers and models: turn off and on, add a provider (logo, API), add and import models, models with no description | Admin |
| Glyphh admin · Marketplace (dark / light) | `AdminMarket`, `AdminMarketLight` | Glyphh's review queue with the reviewer's report, publish, request changes, reject, the thread; listings, featured and categories | Admin |
| API keys (dark / light) | `ApiKeys`, `ApiKeysLight` | A member's keys (account menu): make one (shown once), revoke; when the org doesn't allow member keys; Org → API keys: the switch (turning it off stops members' keys straight away) and every key in the org | Org |
| Audit log of admin actions (dark / light) | `AdminAudit`, `AdminAuditLight` | Org → Audit log (every change in the org, Glyphh's actions marked), a row's before → after, export; Glyphh admin → Audit log (staff and the reviewer agent across orgs); an org's log from its detail | Org, Admin |

Board files are at `screens/<name>.dc.html`.

**The build is greenfield.** Every page is built new, on the component library and the SDK. Built so far (2026-10-11): the tokens and Red Hat, and the sign-in pieces (AuthLayout, BrandOrbit, CatRing, LogoTile, Icon, the Alert with TraceId, ThemeToggle); the sign-in screens are next. The order above is a suggestion: the pages a browser must show first, then the app, then the editors. The design agent keeps drawing ahead of it.

## Building it

### How the build must be made

A clean UI build: small, well-formed, reusable components, and screens made only by composing them.

- **No inline styles.** No `style={…}` and no style attributes, anywhere: not in components, not in screens. The boards are full of inline styles because that is how the canvas draws; that is never the build's shape.
- **No big stylesheets.** Each component has its own small `ComponentName.module.css`, written only in tokens. The only global CSS is `tokens.css` and the base reset in `base.css`. No page or screen stylesheets, no utility-class frameworks, no one-off CSS.
- **Screens compose; they don't style.** A screen is components and layout components (Page, Section, Stack, Row) with props. If a screen seems to need its own CSS, a component is missing.
- **A missing component is a request,** added under Requests, below. It is never patched in a screen. The design agent styles it; you build its behaviour.
- **Variants and states are props,** not new components or class overrides: `<Button variant="primary" size="lg" busy>`, `<Alert tone="danger" traceId="…">`.
- **Tokens only.** No raw colour, size, font, radius, shadow or duration in any file but `tokens.css`.
- **Small files, one job each.** A component folder holds its `.tsx`, its test, its `.module.css` when it has a look of its own, and nothing that belongs to a screen.
- **Use the brand; never invent a style.** Every look comes from the brand and the boards:
  - the logo and the cats come from `design/brand/`, used as given;
  - colour, type, radius, shadow and motion come from the tokens;
  - each component's look comes from the design agent.

  Never make up a colour, gradient, shadow, border, icon, illustration, animation or layout the boards don't show. If a screen needs a look that isn't drawn, ask, or add a request; don't improvise one.
- **Ask Chris before adding any image, logo, icon or other asset.** That includes a new icon set, a third-party logo, a stock photo or illustration, a font, or any file in `public/`. Use only what's in `design/brand/` and what the boards already show, until he says yes.
- **Repeated patterns become components the first time they repeat.** For example: the trace id block, the logo tile, the list row with a status chip, and the pager.

### Components each page needs

The component library, `@glyphh-ai/ui` (in `glyphh-ai/platform`, `ui/`): Alert, Avatar, Badge, Button, Card, Checkbox, Code, CodeBlock, CopyButton, Dialog, EmptyState, Field, Form, FormError, Heading, IconButton, Link, Menu, Page, ProgressSteps, RadioGroup, Row, Section, Select, Skeleton, Slider, Spinner, Stack, StatusDot, SubmitButton, Switch, Table, Tabs, Text, TextArea, TextInput, Toast, and, built for the sign-in pages: AuthLayout, BrandOrbit, CatRing (Glyphh in its ring), Icon, LogoTile, ThemeToggle, TraceId.

Still requested (see Requests, below): a TextInput `code` variant, DescriptionList, Avatar kinds (person, org), Menu radio items, **Pagination**, **SegmentedControl**, a themed **Stripe Payment Element**, **ConnectFrame**, a **bars-by-day chart**.

| Page | Built from | Waits on |
|---|---|---|
| Sign-in pages | AuthLayout, Heading, Text, Button (with its icon), Alert (trace id), Spinner, TextInput, CatRing, LogoTile | TextInput `code`, DescriptionList |
| Machines | Card, Avatar, StatusDot, Badge, Button, Dialog, TextInput, Tabs, Skeleton, EmptyState, ProgressSteps, Menu, LogoTile | Pagination, Menu radio items |
| Account | Section, Avatar, Button, Switch, Card, LogoTile | SegmentedControl (Light, Dark, System) |
| Billing | Card, Badge, Button, Dialog, TextInput, Switch, Table, Alert, Spinner | Stripe Payment Element, bars-by-day chart, Pagination |
| Plugin cards | Card, Avatar, StatusDot, Button, ProgressSteps, RadioGroup, Alert, Skeleton, LogoTile | bars-by-day chart, Pagination |
| Powers | Tabs, Card, Badge, Dialog, TextInput, Button, Alert, Spinner, EmptyState, LogoTile | ConnectFrame, SegmentedControl, Pagination |
| Super power editor | Avatar, Select, TextInput, TextArea, Slider, Button, Dialog, Tabs, Menu | PowerMap, Pagination |
| Task flow | Tabs, Button, Select, TextInput, Switch, Dialog | FlowCanvas, Pagination |
| Custom powers, Marketplace | Tabs, Card, Badge, Button, Menu, Dialog, TextInput, TextArea, EmptyState, LogoTile | Pagination |

The power map and the editable flow canvas are new: PowerMap and FlowCanvas, under Requests.

## Working together

### Who owns what

| | Design agent (Claude Design) | Code agent (Claude Code, this repo) |
|---|---|---|
| **Owns** | How it looks | How it works |
| Brand | Logo use, the cat avatars and their motion, colour, type, voice | Using the brand assets as given |
| Tokens | Every value: colours, fonts, sizes, spacing, radius, shadows, motion | The token **names** and where they are used |
| Components | How each one looks, in every variant and state | The React components: behaviour, accessibility, forms and validation, hooks, error handling, tests |
| Screens | The layouts, composed from the components | Building the screens from the components and wiring them to the SDK |
| Never | Writes React, invents components outside the library, changes behaviour | Picks colours or fonts, restyles on its own |

### Tokens

One file, `ui/src/tokens.css` in `glyphh-ai/platform`: CSS custom properties on `:root` (dark) and `[data-theme="light"]`. The code agent names them; the values are the design's (taken from the boards' own palette) and the design agent may change any value or propose new names. Red Hat is hosted with the platform (`ui/src/fonts.css`).

- **Colour:** `--color-bg`, `--color-surface`, `--color-surface-raised`, `--color-surface-strong`, `--color-surface-sunken`, `--color-dialog`, `--color-line`, `--color-line-strong`, `--color-tile-line`, `--color-scrim`, `--color-text`, `--color-text-muted`, `--color-text-subtle`, `--color-accent`, `--color-on-accent`, `--color-accent-text`, `--color-accent-glow`, `--color-accent-halo`, `--color-chip-bg`, `--color-chip-text`, `--color-info`, `--color-info-bg`, `--color-attention`, `--color-attention-bg`, `--color-attention-line`, `--color-danger`, `--color-danger-text`, `--color-danger-bg`, `--color-danger-line`, `--color-ok`, `--color-warn`, `--color-focus`
- **Type:** `--font-display`, `--font-body`, `--font-mono`, `--text-xs` … `--text-4xl`, `--text-display`, `--weight-regular`, `--weight-medium`, `--weight-semibold`, `--weight-bold`, `--leading-tight`, `--leading-snug`, `--leading-normal`, `--tracking-display`, `--tracking-label`
- **Space and size:** `--space-1` … `--space-10`, `--control-height` (52), `--control-height-md` (48), `--control-height-sm` (44), `--icon-button`
- **Shape:** `--radius-sm` … `--radius-3xl`, `--radius-full`, `--shadow-sm`, `--shadow-md`, `--shadow-lg`, `--shadow-focus`, `--shadow-glow`, `--shadow-ring`
- **Motion:** `--duration-fast`, `--duration-normal`, `--duration-blink`, `--duration-spin`, `--ease-out`, `--ease-spring`

Components use only tokens: never a raw colour, size or font.

### How design reaches code, and code reaches design

- **Design to code:** the boards in `screens/`, exported from the canvas. The code agent builds every screen from them, on the component library.
- **Code to design:** `/design-sync` uploads `@glyphh-ai/ui` into a Claude Design design-system project, so the design agent draws with the real components. It needs `/design-login` once, from an interactive Claude Code session on the Mac. It does not bring designs back into code.
- **Components:** each lives in its own folder (`Name.tsx`, `Name.test.tsx`, and `Name.module.css` when it has a look of its own). Class names and props are the code agent's; the look is the design's. A need nobody has drawn is a request (below), never a one-off.

## Requests

**Built 2026-10-12 from the `Components` board:** LogoTile (with initials, disabled, loading), CatRing (still, turning, the comet), Avatar person and org, TextInput `code`, DescriptionList, Menu radio, check and danger items, Pagination, SegmentedControl, the themed Stripe Payment Element, ConnectFrame, bars by day (`DayBars`), and the PowerMap and FlowCanvas nodes (`PowerCard`, `PowerChip`, `FlowNode`). The canvases themselves (pan, zoom, drag, connect) are built with the editors.

**Still to draw:** kind glyphs for a plugin, a folder, a browser and a super power on PowerCard (the board draws only a task ◆, a skill ◆ and an app ▦; until then those show their logo).

The requests as they were made:


From the design agent, after sketching app.glyphh.ai's sign-in pages and machines against the brief. Each is something those screens need that the library list above does not cover yet.

- **LogoTile** (built 2026-10-11: the logo, sizes, highlighted; still to build: initials without a logo, disabled, loading) (the brief's "provider logo tiles"): a square tile holding a third-party logo or, without one, its initials. For model providers, connections, AI hosts (Claude, ChatGPT, Codex), sign-in providers (Google, GitHub) and deploy hosts (Fly, AWS, ...). Sizes small, medium, large; states default, disabled, loading (skeleton).
- **Button: a leading icon or logo slot** (built: Button's `icon`). For "Continue with Google", "Continue with GitHub" and "Add a machine". Every existing variant, size and state.
- **TextInput: a `code` variant** for one-time codes (`WDJB-MJHT`): monospace, large, centred, uppercased, the dash added as you type, pasting a whole code works. States default, focus, error, disabled.
- **DescriptionList:** label and value pairs, two columns on wide screens and stacked on phones. For "Is this code on your new machine?" (machine, OS, location, when) and for account and machine details.
- **Avatar: three more kinds** beside the cats (the ring is built as CatRing, still and turning; the comet is still to build): a person (initials or photo), an org (letter tile) and a `ring` option, the glowing ring with its comet, for heroes, sign-in pages and empty states. Ring states: still, turning, comet.
- **AuthLayout** (built 2026-10-11): a brand panel beside the content on desktop (logo, Glyphh in its ring showing the page's mood, one line), collapsing to logo, small ring and content on a phone. For every page "only a browser can show".
- **Menu: radio and check items**, for the org switcher in the account menu (Personal, Acme, ...), plus a danger item (Sign out).

From the design agent, after billing, Powers (connections, tool permissions) and the plugin cards:

- **Pagination:** "Showing 1–5 of 23", then Previous, page numbers (shortened with "…") and Next on wide screens, and Previous, "Page 1 of 5" and Next on phones. All buttons 44 px; the current page marked. A `cursor` mode with only Previous and Next, for lists served by cursor (Pipedream's app catalog). Every list that can grow uses it: connections, the catalog, a connection's tools, invoices, machines, super powers, the plugin's cards.
- **SegmentedControl** (or a RadioGroup variant): three or more options in one bar, one chosen. For a tool's permission (Allow, Ask, Deny; Deny in the danger colour), a group's "Set all", and the theme (Light, Dark, System). Keyboard: arrows move the choice.
- **Stripe's Payment Element, themed:** checkout inside the page that takes the tokens for its colours, font and radius, and follows light and dark. Embedded Checkout (server-old's choice) can only set a background and a button colour, so it can't match.
- **ConnectFrame:** a dialog that holds Pipedream's sign-in page in a frame, falling back to "Open the sign-in" in its own window when a provider refuses frames, then "Checking with Pipedream…" and done or error with a trace id.
- **Chart: bars by day:** one bar a day across the period, past days filled, today marked, days to come outlined; a title per bar on hover. The same component on the Billing page and in the usage card, at every width.

From the design agent, for the editors (`SuperPowerEdit`, `TaskCanvas` and their light boards):

- **PowerMap:** the top of the super power editor. The super power's cat in its ring at the centre, and around it one card per power it holds (folders, connections, models, skills, tasks, plugins, browsers, other super powers), each a LogoTile or kind icon, its name and a coloured left edge for its kind, joined to the centre by a dashed line that flows while the super power runs (still when motion is off). Desktop: a dotted ground you can pan, cards you drag, ⌘-scroll to zoom, and four 44 px controls: Zoom in, Zoom out, Fit, Reset the layout. Phone: no canvas; the cat in its ring with the powers as chips under it. States: empty (only the cat, with "Add a power"), a power disabled by a limit (dimmed, with why), loading (skeleton). Saving keeps each card's position. Built on `@xyflow/react` with the same node and edge look as FlowCanvas.
- **FlowCanvas:** a task's Flow tab, React Flow (`@xyflow/react`) made editable. Node kinds, each with its label, kind icon and kind colour from the tokens: Trigger, Agent (a slot), Model, Connection, Decide (yes and no exits), Memory, Skill, Checkpoint, Output. A node shows its title and a one-line detail (`gmail · find-email → emails`), an in handle on top and out handles below. Edges are curves in the accent; a Decide's "no" edge is muted and each exit is labelled. Desktop: pan, zoom, drag nodes, connect handles, a minimap bottom left, zoom and Fit controls bottom right, "+ Add step" and an inspector panel for the chosen node. Phone: the flow read top to bottom as a list, tap a step to edit it. States: chosen node, a broken step (danger edge and its error), an unfilled slot, empty ("Add the first step"), read-only while a run is live. Every edit is saved, never run, from the web.

## Handoff to the design agent

### How to work this list

1. **Pull first** (`glyphh-ai/glyphh`), then read this whole doc: Decisions is what is settled, and every item below comes from it. The server's doc (`glyphh-ai/server`, `docs/architecture.md`) has the data behind each decision; never contradict it.
2. **Take one item at a time,** in the order below. Open its boards on the canvas and change only what the item says: every state, desktop (1200) and phone (390), dark and its light board.
3. **Use what exists:** the tokens, the components in the library (Components each page needs, above), the logos in `screens/assets/` and the artwork in `brand/`. A look nobody has drawn, or a component the library doesn't have, goes under Requests; never improvise one on a board.
4. **The copy is the copy to ship:** plain, short, confident; errors say what happened and what to do, with the trace id. Put the decided numbers in; leave a placeholder in `[BRACKETS]` only for what is still undecided.
5. **Ask, don't guess:** if an item is unclear or clashes with a board, add the question under Questions, below, and move on to the next item. Chris answers there.
6. **Finish an item** by re-exporting the changed boards into `screens/`, taking the item's line out of the list, and committing with the boards' names in the message ("Billing: credit balance, reload to a target, ..."). The code agent builds from the re-exported boards.

### The list

Board changes from the decisions of 2026-10-11 and 2026-10-12.

All done (2026-10-12): the Usage boards (dark and light) now let a plan's included usage expire at the period's end and carry over only bought credit. Included usage is spent before bought credit, as decided.


### Questions

Answered by Chris, 2026-10-12:

1. **Does a plan's included usage carry over?** No: it expires at the period's end, as Billing and the admin ledger draw it. The Usage boards change (the list, above).
2. **"Higher than the last version":** the last *published* version. A rejected 1.3.0 is used up, never reused; 1.2.0 stays the bar. As drawn.
3. **Auto top-up's monthly cap:** yes, at least one reload, and $5 to $10,000 for trigger, target and cap. As drawn.
4. **The extra navigation** (Org: Usage, API keys, Audit log; Glyphh admin: Audit log; the account menu: Usage, API keys): yes. In Decisions → Navigation.

## Handoff to the build agent

From the design agent, 2026-10-12. What changed on the boards since the last handoff, what to build from it, and how. Pull first; every board named here is re-exported in `screens/`.

### Start here

1. **Read Decisions** (above) again: credits are dollars, plans are versioned with their first numbers, a connection call costs 2¢ for each started 30 seconds, bought credit expires a year after purchase, versions are semver with required release notes, a person can be in many teams, and Remove is for good where Turn off is for now. The boards follow them; where a board and Decisions disagree, Decisions wins and you tell the design agent.
2. **Open `Components` first.** It is the look of every component under Requests, each variant and state, dark and light side by side, with suggested props under each sample (the names are yours). Build those components before the pages that wait on them (Components each page needs, above).
3. **Then the pages, in the build order of the table above.** The sign-in screens are next (they wait only on TextInput `code` and DescriptionList, both on `Components`).

### New boards

- **Org:** `OrgTeams` (members, invites, seats, teams, a member's teams), `OrgLimits` (allowed models and connections at the org and a team), `OrgReview`, `ApiKeys` (yours and Org → API keys), `AdminAudit` (Org → Audit log).
- **Publishing:** `ListingSubmit` (icon, screenshots, what it needs, version and release notes with their validation, the review timeline).
- **Usage:** `UsageFlow` (by billing period: credit by connector, a connector's tools, a closed period), `UsageMore` (a super power, a model, the org by user and team, a member for org admins, a publisher's stats), `UsageAudit` (the audit log of connector calls and power uses). The three files share one script; each shows its own states (`var PART`).
- **Glyphh admin:** `AdminOrgs` and `AdminOrgActions` (one script, split the same way: orgs and an org's tabs; gift, plan, comp, move with 30 days' notice, disable; plans, versions and Billing settings), `AdminCatalog` (providers and models: turn off, remove, add, import, descriptions), `AdminMarket` (Glyphh's review with the reviewer's report, listings, featured, categories), `AdminAudit` (Glyphh admin → Audit log).
- **rrotor:** `RrotorSplash`, the first screen on a machine. It belongs to rrotor's own UI, not the platform library.
- **Light:** every board above has a `…Light` copy: the same layout with the light tokens. Build one component per look and let `[data-theme="light"]` do the rest; never a second component for light.

### Changed boards

- **`BillingFlow`, `BillingLight`:** Credit balance in dollars; auto top-up reloads to a target with an optional monthly cap (and its validation); each top-up's expiry; the plan numbers; the plan-move banner.
- **`RrotorSplash`:** laptop machines show the Docker logo; "A step failed" shows the message without the step list.
- **Navigation:** Org gains **Usage**, **API keys** and **Audit log** (Members, Teams, Models, Connections, Review, Usage, API keys, Audit log, Billing); Glyphh admin gains **Audit log** (Orgs, Models, Marketplace, Plans, Audit log); the account menu gains **Usage** and **API keys**. These go beyond the navigation under Decisions and are in the server's Open list for Chris's yes; build the pages, hold the nav items until he answers.

### Assets

- **New:** `screens/assets/docker.svg` (approved by Chris), for laptop machines. Nothing else is new; ask before adding any other asset.
- **Approved icons:** a featured star, a drag handle and up/down arrows (marketplace and categories). Draw them as simple strokes in the Icon component, nothing more.
- **Uploads members make** (listing icons, screenshots, provider logos) are PNG (icons and logos square, 512 px) or JPEG for screenshots, 5 MB each, never SVG.

### What the boards still leave open

The Questions above (to Chris), and the server's Open list (`docs/architecture.md`, Open → Design): API key details, usage time zones, the audit log's retention and export, multi-select pickers, admin navigation on a phone. Build what is decided; leave a `[BRACKETS]` placeholder or ask for the rest. Never invent a value or a look.

