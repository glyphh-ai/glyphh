# Design decisions

What the brand exploration settled, in the Claude Design canvas "Glyphh Design" (https://claude.ai/artifact/DMiUf6vx7u61MNLDd4anLq). Values here are the direction; the token values themselves land in `ui/src/tokens.css` through `/design-sync`, as `collaboration.md` says.

## Logo

- **One logo, on every ground:** `brand/logo/glyphh-logo-black.png`, the ink mark in its white sticker border. No light, dark or white version, no recolouring.
- The cat alone is the favicon and the small app icon.

## The cats

- **Black and white.** A super power's colour lives only in its eye; the body is ink, the sticker border white. Glyphh's own eye is white.
- **Moods change the eye:**
  - Done: a small check as the eyeball.
  - Playful, and the Wink face: a heart for an eye, lashes on the eye's outline; the whole eye closes on the blink.
  - The rest as drawn in `brand/moods/`.
- **On a status page, Glyphh's eye takes the status colour:** violet on success, red on failure, pink when it needs you, cyan while thinking.
- **On light grounds:** no black fill behind a cat or a logo tile; only a thin outline.

## Colour: Ink & Violet

| Role | Dark | Light |
|---|---|---|
| Ground | Ink `#0B0A0F` | Paper `#F5F5F7` |
| Accent (main action, the ring, running) | Violet `#7C4DFF`, white text on it | the same |
| Accent as text | `#B49CFF` | `#6A3DF0` |
| Thinking, info | Ion `#6FD8FF` | |
| Needs you | Pink `#F062D0` | |
| Stuck, errors | Red `#FF4D4D` | `#C21D3C` as text |

Yellow, lime, green and orange were tried and dropped.

## Type: Red Hat

- Red Hat Display for headlines.
- Red Hat Text for everything you read and press.
- Red Hat Mono for trace ids, codes and logs.

## Buttons

One height everywhere (48–52 px). On a phone, a pair stacks full width. A layout never squeezes a button; the container grows instead.

## Sign-in pages: the brand panel ("rrotor in motion")

The left half on desktop, collapsing to a small ring above the content on a phone:

- **Glyphh in its ring**, winking now and then.
- **Three rings around it,** alternating direction, each slower than the one inside:
  - super powers (cats with varied faces, a new one popping into an empty slot);
  - models;
  - connections.
- **Logo tiles:** neutral boxes with a light outline; only the logo is in its brand colour.
- **Headline:** "Create AI super powers." Line: "Glyphh combines your models, connections and agents into super powers you run on Glyphh machines, anywhere."
- **Footer:** "© 2026 Glyphh AI".

## app.glyphh.ai

- **Machine cards** show up to 8 super powers, each in an outlined square with its name under it (two lines, then an ellipsis), then "+N / See all".
- **See all** opens a dialog with search, status filters and pages.
- **Clicking a super power** opens it on its machine in rrotor. The web app stays a front door; nothing is edited there.
- **Every header has the light/dark toggle.** The account menu and the Account page offer Light, Dark or System.

## Logos of other companies

Always the real, full-colour artwork, never a one-colour silhouette. Black marks (OpenAI, GitHub, Grok, Cursor, Anthropic, the AWS wordmark) get an off-white copy for dark grounds. Claude shows the Claude mark; Codex shows OpenAI's.

## Lists

Everything that can grow is paginated, in the designs as in the build: "Showing 1–5 of 23", Previous, page numbers, Next; on a phone, Previous, "Page 1 of 5", Next.

## Billing

- **One Billing page,** server-old's flow and copy:
  - Current plan, then Budget with auto top-up and spend by day, then Plans, then Invoices (View, PDF).
  - Every action opens a dialog: Add funds, Auto top-up, Switch plan.
- **Paying happens inside the page** and matches it: dark on dark, light on light, our fields and violet button. That needs Stripe's Payment Element (requested in `collaboration.md`).
- **Open question:** server-old bills in dollars (funds, "Glyphh usage"); the server's docs bill in credits for connection calls only. The copy follows whichever is current.

## Powers: connections and permissions

- **Where it lives:** Powers sits in the top nav beside Machines, with tabs Loops, Connections, Models, Folders, Skills.
- **A connection is always the member's own account.** Pipedream holds the sign-in, which happens on Pipedream's page in a dialog (or its own window when a provider refuses frames). There is no shared org account.
- **Every tool is Allow, Ask or Deny,** grouped by risk: Read, Create and update, Delete. A tool with no setting asks. A super power can carry its own Allow or Deny for runs nobody watches, where Ask is refused.
- **Phones get a compact row per connection:** logo, name, account, one status line, and a chevron (or Reconnect).

## The plugin

The app's screens as cards in the chat, following the host's theme:
- My machines
- Deploy (pick a host, then live status)
- Usage
- The swarm
- Needs you (a question, or a permission)
- Empty, loading and error states
