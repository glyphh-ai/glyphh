# Working together: the design agent and the code agent

Two agents build Glyphh's UI. This page is the contract between them. Read it before starting, and keep to your side of it.

## Who owns what

| | Design agent (Claude Design) | Code agent (Claude Code, this repo) |
|---|---|---|
| **Owns** | How it looks | How it works |
| Brand | Logo use, the cat avatars and their motion, colour, type, voice | Using the brand assets as given |
| Tokens | Every value: colours, fonts, sizes, spacing, radius, shadows, motion | The token **names** and where they are used |
| Components | How each one looks, in every variant and state | The React components: behaviour, accessibility, forms and validation, hooks, error handling, tests |
| Screens | The layouts, composed from the components | Building the screens from the components and wiring them to the SDK |
| Never | Writes React, invents components outside the library, changes behaviour | Picks colours or fonts, restyles on its own |

## The order

1. **The code agent builds the component library** in `ui/` (the package `@glyphh-ai/ui`): every component, every variant and state, with bare styling on placeholder tokens.
2. **The library goes to Claude Design** through "Create using Claude Code" (`/design-sync`), so the design system starts from the real components, not a parallel set.
3. **The design agent designs on those components:** token values first, then each component's look, then the screens.
4. **`/design-sync` brings the design back** into `ui/`: token values and component styles. The code agent's tests guard behaviour, so a restyle cannot break a form.
5. **Repeat** as screens are added: a new need is raised as a component request (below), never drawn as a one-off.

Until step 2, the design agent explores direction only: palette, typefaces, the brand, motion, mood, using `design/BRIEF.md` and `design/brand/`.

## The contract

### Tokens

One file, `ui/src/tokens.css`: CSS custom properties on `:root` (dark) and `[data-theme="light"]`. The code agent defines the names; the design agent sets every value and may propose new names.

- **Colour:** `--color-bg`, `--color-surface`, `--color-surface-raised`, `--color-line`, `--color-text`, `--color-text-muted`, `--color-accent`, `--color-on-accent`, `--color-ok`, `--color-warn`, `--color-danger`, `--color-focus`
- **Type:** `--font-display`, `--font-body`, `--font-mono`, `--text-xs` … `--text-3xl`, `--weight-regular`, `--weight-medium`, `--weight-bold`, `--leading-tight`, `--leading-normal`
- **Space:** `--space-1` … `--space-10`
- **Shape:** `--radius-sm`, `--radius-md`, `--radius-lg`, `--radius-full`, `--shadow-sm`, `--shadow-md`, `--shadow-lg`
- **Motion:** `--duration-fast`, `--duration-normal`, `--ease-out`, `--ease-spring`

Components use only tokens: never a raw colour, size or font.

### Components

Each component lives in its own folder: `ComponentName.tsx`, `ComponentName.module.css`, `ComponentName.test.tsx`. The design agent changes only the `.module.css` files and `tokens.css`. Class names and props stay as the code agent wrote them.

The library:

- **Actions:** Button (primary, secondary, ghost, danger; small, medium, large; busy, disabled), IconButton, Link, CopyButton
- **Forms:** Form, Field (label, hint, error), TextInput, TextArea, Select, Checkbox, Switch, RadioGroup, Slider, SubmitButton, FormError (with trace id)
- **Content:** Heading, Text, Code, CodeBlock, Badge, StatusDot (online, offline, working, waiting, failed), Avatar (the cats, with mood and blink), Card, Table
- **Feedback:** Alert (info, ok, warn, danger, with trace id), Toast, Spinner, Skeleton, EmptyState, ProgressSteps (deploy status: waiting, registered, starting, ready)
- **Overlays and navigation:** Dialog, Tabs, Menu
- **Layout:** Stack, Row, Page, Section

Every component has these states where they apply: default, hover, focus, active, disabled, busy, error, empty, loading.

### Where the components run

The same components serve all three surfaces, so each must look right in all three:

1. **app.glyphh.ai:** the web front door (sign-in, machines, deploy, account).
2. **rrotor's UI:** each machine's own app (the old desktop app, reworked).
3. **Cards in Claude and ChatGPT:** small, inside the chat, following the host's light or dark theme.

### Asking for something

- **The design agent needs a component that does not exist:** add it under "Requests" below, with what it is for and its variants and states. The code agent builds it, then it comes back through `/design-sync`.
- **The code agent needs a value or a look:** it asks here too; it never picks one itself.

## Where we are

- **Step 1 is done (2026-10-11):** the whole library above is built in `ui/`, with bare styling on placeholder tokens, tested at 100%. See `ui/README.md`.
- **Next, step 2:** start `/design-sync` in the code agent's session to bring it into Claude Design.

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
