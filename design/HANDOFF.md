# Design handoff: where the screens are and what to build them from

For the code agent building app.glyphh.ai in `glyphh-ai/platform`. Read this with `DECISIONS.md` (the settled rules) and `collaboration.md` (who owns what, and the component requests).

## Where the screens are

All screens live on one Claude Design canvas, **Glyphh Design**:

**https://claude.ai/artifact/DMiUf6vx7u61MNLDd4anLq**

It is private to Chris; you run as Chris, so you can read it. Read it with the Artifact tool, never a web fetch:

- the whole canvas: `{ "action": "read", "url": "<the link>" }`
- one board's source: `{ "action": "read", "url": "<the link>", "path": "project/BillingFlow.dc.html" }`
- the page and board list: `path: "project/canvas.json"`

Each board is a `.dc.html` file: plain HTML with inline styles, and a script at the bottom that holds the screen data (states, rows, labels). The copy in it is the copy to ship. Images are `/_blob/<id>` URLs on the canvas; the real files are in `design/brand/`, and third-party logos are the full-colour sets from Iconify `logos` and Lobe icons.

**The canvas keeps moving.** The design agent and Chris are still adding to it while you build. Read a board again before you start on it, rather than working from an old copy.

## How to read a board

- **Sketches, not specs.** The boards were drawn before the component library existed. Build every screen from `@glyphh-ai/ui` components; never copy a board's raw colours, sizes or fonts. The values in the boards are what `tokens.css` will carry once `/design-sync` runs (Ink & Violet, Red Hat; see `DECISIONS.md`).
- **One board, every state.** Each board lays out one page in all its states (default, loading, empty, error with trace id, success, validation), at 1200 wide (desktop) and 390 wide (phone). The state name is printed above each frame.
- **Light and dark.** Where a page has both, they are separate canvas pages. The light board is the dark one with `[data-theme="light"]` values: no layout differences.
- **Dialogs** are drawn over a copy of the page beneath them.
- **Placeholders** in `[BRACKETS]` are not decided (prices, credits per plan, the install command). Leave them visible or ask; don't invent them.
- **Example data** (Northwind, studio-mac, Sam Rivera, Inbox Zero, …) is only example data.

## The pages

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

Board files are at `project/<name>.dc.html` on the canvas.

**The build is greenfield.** Nothing here is built yet; build every page new, on the component library and the SDK. The order above is a suggestion: the pages a browser must show first, then the app, then the editors. The design agent keeps drawing ahead of it.

## Components each page needs

The component library, `@glyphh-ai/ui` (in `glyphh-ai/platform`, `ui/`): Alert, Avatar, Badge, Button, Card, Checkbox, Code, CodeBlock, CopyButton, Dialog, EmptyState, Field, Form, FormError, Heading, IconButton, Link, Menu, Page, ProgressSteps, RadioGroup, Row, Section, Select, Skeleton, Slider, Spinner, Stack, StatusDot, SubmitButton, Switch, Table, Tabs, Text, TextArea, TextInput, Toast.

Still requested (see `collaboration.md`, Requests): LogoTile, a Button icon slot, a TextInput `code` variant, DescriptionList, more Avatar kinds (person, org, ring), AuthLayout, Menu radio items, **Pagination**, **SegmentedControl**, a themed **Stripe Payment Element**, **ConnectFrame**, a **bars-by-day chart**.

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

## Rules that apply to every screen

From `DECISIONS.md`; repeated here because they are easy to miss:

- **Buttons are 48 px** (44 px for small and icon buttons) and never squeezed. On a phone a pair stacks full width, the main action on top.
- **Every list that can grow is paginated.**
- **Third-party logos are the real full-colour marks.** Black marks get an off-white copy on dark.
- **Cats stay black and white;** colour lives only in the eye. On light grounds, nothing dark is drawn behind a cat or a logo.
- **Every error says what happened and what to do,** with its trace id and a copy button.
- **Light and dark, phone and desktop,** and everything still for people who turn motion off.
- **The web edits, it doesn't run.** Super powers, tasks and apps run on the member's machines; the web saves and the machines sync.

## Open questions

- **Billing currency:** server-old bills in dollars (funds); the server's docs bill in credits for connection calls only. The billing copy follows whichever is current.
- **Undecided numbers:** credits per plan, pack sizes and prices, and the machines included per plan.
- **Navigation:** where Powers lives. The boards put Super powers, Powers and Marketplace in the top nav.
