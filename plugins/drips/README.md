# Drips

Drips plays visual effects over Claude: confetti, fireworks, hearts,
stars, bubbles, a matrix rain, an aurora and more. Play one with a
command, save your own recipes, and let Claude play them too.

```
/drip confetti
/drip 3 hearts stars
/drip -1 aurora
/drip stop
```

Drips works in Claude Code on a Mac.

## Requirements

- **Node.js 18 or newer** (https://nodejs.org). It runs the small local
  page that plays effects in Claude's window and holds the Drips editor.
- For **fullscreen** effects: the **Xcode Command Line Tools**, which bring
  Swift (`xcode-select --install`). Without them, Drips plays effects in
  Claude's window and tells you so.

## Install

In Claude Code, run:

```
/plugin marketplace add glyphh-ai/glyphh
/plugin install drips@glyphh
```

To let Drips open its page in the desktop app's Browser pane without
asking you each time, allow this call in `~/.claude/settings.json`:

```json
"permissions": {
  "allow": ["mcp__Claude_Browser__preview_start"]
}
```

If you don't, and the app refuses the call, Drips asks Claude to open the
page for you.

## Commands

| Command | What it does |
|---|---|
| `/drip <recipe>` | Plays a recipe, or one of your saved drips by name |
| `/drip list` | Lists the effects and your saved drips |
| `/drip save <name> <recipe>` | Saves a recipe under a name |
| `/drip delete <name>` | Deletes a saved drip |
| `/drip stop` | Stops every effect that keeps playing |
| `/drips` | Opens the Drips page: your saved drips, and an editor |
| `/drips key <licence>` | Unlocks Drips with a licence key |

`/drip` runs straight away, even while Claude is working.

## Recipes

A recipe is a few words, in any order:

- **An effect**: `fireworks`, `hearts`, `confetti`, `stars`, `rain`,
  `bubbles`, `sparkle`, `spiral`, `emoji`, `wave`, `thumbsup`, `peace`,
  `cat`, and the backgrounds `matrix`, `aurora`, `nebula`, `plasma`,
  `fireflies`, `starfield`. Name several and they play one after another.
- **A number from 1 to 10**: how many times to play them. Each effect
  starts 1.5 seconds after the one before.
- **A number between 0 and 1**: how see-through the effect is (`0.4`).
- **`-1`**: keep playing. The effect stays until you play the same
  recipe again, run `/drip stop`, or press Esc in the Drips page. Nothing
  plays for longer than 30 minutes.
- **A saved drip's name**: its effects join in.

`/drip` alone plays fireworks.

## Where effects play

Open `/config` and find **Where effects play** under Drips:

- **claude-window** (the default) plays effects over Claude's window, in
  the Drips page in the desktop app's Browser pane. The first effect opens
  the page. Outside the desktop app, the page opens in your own browser.
- **fullscreen** plays effects over the whole screen under the pointer,
  above every app and on every Space. Effects never take the pointer or
  the keyboard: you can keep working through them. The first fullscreen
  effect takes a few seconds longer, while Drips builds its small overlay
  program with Swift. It's built once and kept in
  `~/Library/Caches/glyphh-drips`.

Previews from the Drips page always play in the page, and a preview that
keeps playing stops by itself after 12 seconds.

## The Drips page

`/drips` opens the page. **Your drips** lists each saved drip with its
recipe and a **Play** button. Search by name or recipe, or click **+ Add**
to make one. Click a drip to edit it:

- **Name**
- **Mode**: **One-shot**, **Counted** (2 to 10 times) or **Persistent
  (toggle on/off)**
- **Effects**: pick one or more; **+ Add effect** adds another
- **Recipe preview**: the recipe your choices make
- **▶ Play** and **■ Stop**, **Save**, **Cancel**, and **Delete** (it asks
  first)

Leaving the editor stops whatever it played.

## Claude can play them too

Claude has two tools: `play_drip` plays a recipe (or stops them), and
`list_drips` lists the effects and your saved drips. Ask Claude to
celebrate and it may.

## Just for fun

Two more rows in `/config`, both off until you turn them on:

- **Confetti after a long turn**: confetti when Claude finishes a turn
  that ran longer than two minutes.
- **Matrix while tools run**: a faint matrix rain while Claude's tools
  run. It goes a moment after the last one finishes. A matrix you started
  yourself is left alone.

## Trial and unlock

Drips is free for 7 days. While the trial runs, the Drips page shows the
days left and an **Unlock — $5** button.

When the trial ends, effects stop playing until you unlock (your saved
drips stay, and `/drip list`, `save`, `delete` and `stop` still work).
Open the page with `/drips` and press **Unlock — $5**. Checkout opens in
your browser, and Drips unlocks by itself once you've paid. It's a one-off
payment, not a subscription.

The licence is checked on your machine, so after you unlock, Drips never
needs to contact a server again. To use it on another machine, run
`/drips key <licence>` there.

## Where things are kept

Everything stays on your machine. Your saved drips are kept in Claude
Code's store for Drips. The fullscreen overlay program is kept in
`~/Library/Caches/glyphh-drips`.

## Security

- The Drips page is served only on `127.0.0.1`, on a random port. Every
  request must carry a random key made for that session. The server
  refuses any other host name or origin, and the page can't be framed by
  another site.
- The session key is never written to a file or a log. The page is opened
  with a one-time address that stops working once it has been used.
- Each effect runs in a sandboxed frame that can run its own animation and
  nothing else: it can't reach the page, your files or the network.
- The fullscreen overlay is built on your Mac from the source in the
  plugin (`native/overlay.swift`). It shows one effect, ignores the
  pointer, closes when the effect ends or after its time limit (never more
  than 30 minutes), and quits if Claude Code goes away.

## For developers

This mod is built from the private source repository to the Glyphh mod standard
(`docs/mod-standard.md` there). Its licence code in `hooks/licence/` is a copy of the
shared module: change the source and sync, never the copy.
