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
