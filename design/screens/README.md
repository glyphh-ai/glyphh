# Screens

Every board from the Glyphh Design canvas, exported into the repo so you can read them without the canvas. Read `../HANDOFF.md` first: it says what each page is, the build order, the components each needs, and how the build must be made.

## What's here

- `*.dc.html`: one file per board. Each lays out a page in all its states, at desktop (1200 wide) and phone (390 wide) sizes; the state's name is above each frame.
- `canvas.json`: the canvas index, listing pages, boards and their titles.
- `assets/`: the files the boards use.
  - `glyphh-logo-black.png`, the one logo.
  - The full-colour third-party logos, with a `-dark` copy where the mark is black.
  - `glyphh-icons*.json`, the older single-colour icon paths, kept only so the boards still resolve.

## How to read a board

- **The markup is the layout.** It uses `<sc-for>` (a repeat) and `<sc-if>` (a branch), with `{{holes}}` filled from the script.
- **The script at the bottom is the content.** `STATES` (or `PAGES`, `CARDS`) lists every state. The helper functions build the rows, labels, copy and numbers each state shows. Read the two together.
- **The copy is the copy to ship.** `[BRACKETS]` are undecided; names like Northwind and studio-mac are example data.
- **Cats** are drawn by the `cat()` helper from `design/brand/cats` paths: black and white, colour only in the eye.
- **They don't open in a browser.** They need the canvas's runtime (`support.js`), which isn't here. Read them as source.
- **The inline styles are how the canvas draws.** Never copy them into the build. Build from `@glyphh-ai/ui` and its tokens (see `../HANDOFF.md`, "How the build must be made").

## Which file is which page

| Page | Files |
|---|---|
| Brand | `Main`, `Palettes`, `Type`, `LogoInUse` |
| Sign in | `SignInFlow` |
| Allow a host | `AllowFlow` |
| Approve a code | `CodeFlow` |
| Join an org | `JoinFlow` |
| Machines | `PlayerFlow` |
| Light theme, Account, sign out | `LightAccount` |
| Billing | `BillingFlow` (dark), `BillingLight` |
| Plugin cards | `PluginCards` |
| Powers: connections and permissions | `PowersFlow`, `PowersMobile`, `PowersLight`, `PowersLightMobile` |
| Super power editor | `SuperPowerEdit`, `SuperPowerEditLight` |
| Task flow | `TaskCanvas`, `TaskCanvasLight` |
| Custom powers | `CustomPowers`, `CustomPowersLight` |
| Marketplace | `Marketplace`, `MarketplaceLight` |

## Keeping it current

The canvas is where the design happens; this folder is a copy. The design agent re-exports it after each round of changes, and the commit says which boards changed. If a board here and the handoff disagree, ask.
