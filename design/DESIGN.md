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
- **Connections catalog:** search 3,500 services, a native connect screen.
- **Models catalog:** provider logos, name, description, type; add a key.
- **Usage and billing:** credits used and left, usage by user, connection, super power and day; plan, seats, machines.
- **Org admin:** members, invites, teams, allowed models and connections.
- **Settings:** theme, notifications, voice.

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
| Thinking, info | Ion `#6FD8FF` | |
| Needs you | Pink `#F062D0` | |
| Stuck, errors | Red `#FF4D4D` | `#C21D3C` as text |

Yellow, lime, green and orange were tried and dropped.

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
- **Clicking a super power** opens it on its machine in rrotor. The web app stays a front door; nothing is edited there.
- **Every header has the light/dark toggle.** The account menu and the Account page offer Light, Dark or System.

### Logos of other companies

Always the real, full-colour artwork, never a one-colour silhouette. Black marks (OpenAI, GitHub, Grok, Cursor, Anthropic, the AWS wordmark) get an off-white copy for dark grounds. Claude shows the Claude mark; Codex shows OpenAI's.

### Lists

Everything that can grow is paginated, in the designs as in the build: "Showing 1–5 of 23", Previous, page numbers, Next; on a phone, Previous, "Page 1 of 5", Next.

### Billing

- **One Billing page,** server-old's flow and copy:
  - Current plan, then Budget with auto top-up and spend by day, then Plans, then Invoices (View, PDF).
  - Every action opens a dialog: Add funds, Auto top-up, Switch plan.
- **Paying happens inside the page** and matches it: dark on dark, light on light, our fields and violet button. That needs Stripe's Payment Element (see Requests).
- **Dollars or credits:** moved to the server's backlog (https://github.com/glyphh-ai/server/blob/main/docs/backlog.md). The copy follows whichever is decided.

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

### Colour today

Every cat is drawn in Glyphh ink (`#0b0a0f`) inside a white sticker border, and stays black and white: a super power's colour fills only its eye (the white parts inside the `eye` group). Glyphh's own eye stays white. See Decisions, above.

## Screens

### Where they are

Every board is in `screens/` as a `.dc.html` file, with the logos it uses in `screens/assets/` and the canvas index in `screens/canvas.json`. They come from one Claude Design canvas, **Glyphh Design** (https://claude.ai/artifact/DMiUf6vx7u61MNLDd4anLq), private to Chris; the code agent can't open it and works from this copy. The design agent re-exports it after each round of changes, and the commit says which boards changed. **The design keeps moving:** pull before starting a page, and read its board again rather than working from memory.

- `glyphh-logo-black.png` in `screens/assets/` is the one logo; the full-colour third-party logos have a `-dark` copy where the mark is black; `glyphh-icons*.json` are older single-colour icon paths, kept only so the boards still resolve.

### How to read a board

- **Sketches, not specs.** The boards were drawn before the component library existed. Build every screen from `@glyphh-ai/ui` components; never copy a board's raw colours, sizes or fonts. The boards' values are what `tokens.css` carries (Ink & Violet, Red Hat; see Decisions).
- **One board, every state.** Each board lays out one page in all its states (default, loading, empty, error with trace id, success, validation), at 1200 wide (desktop) and 390 wide (phone). The state name is printed above each frame.
- **Light and dark.** Where a page has both, they are separate canvas pages. The light board is the dark one with `[data-theme="light"]` values: no layout differences.
- **Dialogs** are drawn over a copy of the page beneath them.
- **Placeholders** in `[BRACKETS]` are not decided (prices, credits per plan, the install command). Leave them visible or ask; don't invent them.
- **Example data** (Northwind, studio-mac, Sam Rivera, Inbox Zero, …) is only example data.
- **The markup is the layout.** It uses `<sc-for>` (a repeat) and `<sc-if>` (a branch), with `{{holes}}` filled from the script.
- **The script at the bottom is the content.** `STATES` (or `PAGES`, `CARDS`) lists every state; the helper functions build the rows, labels, copy and numbers each state shows. The copy is the copy to ship.
- **Cats** are drawn by the `cat()` helper from `brand/cats` paths.
- **They don't open in a browser:** they need the canvas's runtime (`support.js`), which isn't here. Read them as source.

### The pages

| Canvas page | Board file(s) | What it is | Build order |
|---|---|---|---|
| Brand | `Main`, `Palettes`, `Type`, `LogoInUse` | Logo, cats and moods, motion, Ink & Violet, Red Hat, the sign-in panel's animation | n/a |
| Sign in | `SignInFlow` | Google / GitHub, loading, signed in, expired, refused, error | 1 |
| Allow a host | `AllowFlow` | "Claude wants to use your Glyphh": allow, deny, connected | 1 |
| Approve a code | `CodeFlow` | Enter a code (validation), confirm the machine, approved | 1 |
| Join an org | `JoinFlow` | Invite: signed out, accept, wrong account, joined | 1 |
| Machines | `PlayerFlow` | Machine cards (8 super powers, then See all), the See all dialog with search and pages, add a machine, connecting, offline, account menu | 2 |
| Light and account | `LightAccount` | The light theme, the Account page, the account menu, signed out | 2 |
| Billing (dark / light) | `BillingFlow`, `BillingLight` | Plan, budget and auto top-up, spend by day, plans, invoices; dialogs for Add funds, Auto top-up, Switch plan; Stripe checkout inside the page | 3 |
| Plugin | `PluginCards` | The cards in Claude and ChatGPT: machines, deploy, usage, the swarm, needs you | 8 |
| Powers (4 pages) | `PowersFlow`, `PowersMobile`, `PowersLight`, `PowersLightMobile` | Connections through Pipedream (catalog, sign-in, reconnect, disconnect) and tool permissions (Allow, Ask, Deny) | 4 |
| Super power editor (dark / light) | `SuperPowerEdit`, `SuperPowerEditLight` | The power map, identity, sliders, brief, the Powers rail, the Add a power dialog | 5 |
| Task flow (dark / light) | `TaskCanvas`, `TaskCanvasLight` | A Task's Flow tab: the React Flow canvas made editable, the inspector, slots, schedule | 6 |
| Custom powers (dark / light) | `CustomPowers`, `CustomPowersLight` | Skills, plugins, tasks and apps in one list; New power; each type's detail | 5 |
| Marketplace (dark / light) | `Marketplace`, `MarketplaceLight` | Discover, search with pages, a power's and a super power's detail, Add | 7 |

Board files are at `screens/<name>.dc.html`.

**The build is greenfield.** Nothing here is built yet; build every page new, on the component library and the SDK. The order above is a suggestion: the pages a browser must show first, then the app, then the editors. The design agent keeps drawing ahead of it.

## Building it

### How the build must be made

A clean UI build: small, well-formed, reusable components, and screens made only by composing them.

- **No inline styles.** No `style={…}` and no style attributes, anywhere: not in components, not in screens. The boards are full of inline styles because that is how the canvas draws; that is never the build's shape.
- **No big stylesheets.** Each component has its own small `ComponentName.module.css`, written only in tokens. The only global CSS is `tokens.css` and the base reset in `base.css`. No page or screen stylesheets, no utility-class frameworks, no one-off CSS.
- **Screens compose; they don't style.** A screen is components and layout components (Page, Section, Stack, Row) with props. If a screen seems to need its own CSS, a component is missing.
- **A missing component is a request,** added under Requests, below. It is never patched in a screen. The design agent styles it; you build its behaviour.
- **Variants and states are props,** not new components or class overrides: `<Button variant="primary" size="lg" busy>`, `<Alert tone="danger" traceId="…">`.
- **Tokens only.** No raw colour, size, font, radius, shadow or duration in any file but `tokens.css`.
- **Small files, one job each.** A component folder holds its `.tsx`, its `.module.css` and its test, and nothing that belongs to a screen.
- **Use the brand; never invent a style.** Every look comes from the brand and the boards:
  - the logo and the cats come from `design/brand/`, used as given;
  - colour, type, radius, shadow and motion come from the tokens;
  - each component's look comes from the design agent.

  Never make up a colour, gradient, shadow, border, icon, illustration, animation or layout the boards don't show. If a screen needs a look that isn't drawn, ask, or add a request; don't improvise one.
- **Ask Chris before adding any image, logo, icon or other asset.** That includes a new icon set, a third-party logo, a stock photo or illustration, a font, or any file in `public/`. Use only what's in `design/brand/` and what the boards already show, until he says yes.
- **Repeated patterns become components the first time they repeat.** For example: the trace id block, the logo tile, the list row with a status chip, and the pager.

### Components each page needs

The component library, `@glyphh-ai/ui` (in `glyphh-ai/platform`, `ui/`): Alert, Avatar, Badge, Button, Card, Checkbox, Code, CodeBlock, CopyButton, Dialog, EmptyState, Field, Form, FormError, Heading, IconButton, Link, Menu, Page, ProgressSteps, RadioGroup, Row, Section, Select, Skeleton, Slider, Spinner, Stack, StatusDot, SubmitButton, Switch, Table, Tabs, Text, TextArea, TextInput, Toast.

Still requested (see Requests, below): LogoTile, a Button icon slot, a TextInput `code` variant, DescriptionList, more Avatar kinds (person, org, ring), AuthLayout, Menu radio items, **Pagination**, **SegmentedControl**, a themed **Stripe Payment Element**, **ConnectFrame**, a **bars-by-day chart**.

| Page | Built from | Waits on |
|---|---|---|
| Sign-in pages | Page, Heading, Text, Button, Alert (trace id), CopyButton, Spinner, TextInput, Avatar (the cat) | AuthLayout, Avatar ring, Button icon slot, TextInput `code`, DescriptionList |
| Machines | Card, Avatar, StatusDot, Badge, Button, Dialog, TextInput, Tabs, Skeleton, EmptyState, ProgressSteps, Menu | Pagination, Menu radio items, LogoTile |
| Account | Section, Avatar, Button, Switch, Card | SegmentedControl (Light, Dark, System), LogoTile (Claude, Codex) |
| Billing | Card, Badge, Button, Dialog, TextInput, Switch, Table, Alert, Spinner | Stripe Payment Element, bars-by-day chart, Pagination |
| Plugin cards | Card, Avatar, StatusDot, Button, ProgressSteps, RadioGroup, Alert, Skeleton | LogoTile, bars-by-day chart, Pagination |
| Powers | Tabs, Card, Badge, Dialog, TextInput, Button, Alert, Spinner, EmptyState | ConnectFrame, LogoTile, SegmentedControl, Pagination |
| Super power editor | Avatar, Select, TextInput, TextArea, Slider, Button, Dialog, Tabs, Menu | a power-map canvas (not requested yet), Pagination |
| Task flow | Tabs, Button, Select, TextInput, Switch, Dialog | the editable flow canvas (React Flow, `@xyflow/react`), Pagination |
| Custom powers, Marketplace | Tabs, Card, Badge, Button, Menu, Dialog, TextInput, TextArea, EmptyState | Pagination, LogoTile |

The power map and the editable flow canvas are new. They need their own component requests before the design agent styles them.

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
- **Components:** each lives in its own folder (`Name.tsx`, `Name.module.css`, `Name.test.tsx`). Class names and props are the code agent's; the look is the design's. A need nobody has drawn is a request (below), never a one-off.

## Requests

From the design agent, after sketching app.glyphh.ai's sign-in pages and machines against the brief. Each is something those screens need that the library list above does not cover yet.

- **LogoTile** (the brief's "provider logo tiles"): a square tile holding a third-party logo or, without one, its initials. For model providers, connections, AI hosts (Claude, ChatGPT, Codex), sign-in providers (Google, GitHub) and deploy hosts (Fly, AWS, ...). Sizes small, medium, large; states default, disabled, loading (skeleton).
- **Button: a leading icon or logo slot.** For "Continue with Google", "Continue with GitHub" and "Add a machine". Every existing variant, size and state.
- **TextInput: a `code` variant** for one-time codes (`WDJB-MJHT`): monospace, large, centred, uppercased, the dash added as you type, pasting a whole code works. States default, focus, error, disabled.
- **DescriptionList:** label and value pairs, two columns on wide screens and stacked on phones. For "Is this code on your new machine?" (machine, OS, location, when) and for account and machine details.
- **Avatar: three more kinds** beside the cats: a person (initials or photo), an org (letter tile) and a `ring` option, the glowing ring with its comet, for heroes, sign-in pages and empty states. Ring states: still, turning, comet.
- **AuthLayout** (or a Page variant): a brand panel beside the content on desktop (logo, Glyphh in its ring showing the page's mood, one line), collapsing to logo, small ring and content on a phone. For every page "only a browser can show".
- **Menu: radio and check items**, for the org switcher in the account menu (Personal, Acme, ...), plus a danger item (Sign out).

From the design agent, after billing, Powers (connections, tool permissions) and the plugin cards:

- **Pagination:** "Showing 1–5 of 23", then Previous, page numbers (shortened with "…") and Next on wide screens, and Previous, "Page 1 of 5" and Next on phones. All buttons 44 px; the current page marked. A `cursor` mode with only Previous and Next, for lists served by cursor (Pipedream's app catalog). Every list that can grow uses it: connections, the catalog, a connection's tools, invoices, machines, super powers, the plugin's cards.
- **SegmentedControl** (or a RadioGroup variant): three or more options in one bar, one chosen. For a tool's permission (Allow, Ask, Deny; Deny in the danger colour), a group's "Set all", and the theme (Light, Dark, System). Keyboard: arrows move the choice.
- **Stripe's Payment Element, themed:** checkout inside the page that takes the tokens for its colours, font and radius, and follows light and dark. Embedded Checkout (server-old's choice) can only set a background and a button colour, so it can't match.
- **ConnectFrame:** a dialog that holds Pipedream's sign-in page in a frame, falling back to "Open the sign-in" in its own window when a provider refuses frames, then "Checking with Pipedream…" and done or error with a trace id.
- **Chart: bars by day:** one bar a day across the period, past days filled, today marked, days to come outlined; a title per bar on hover. The same component on the Billing page and in the usage card, at every width.
