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

## Requests

None yet.
