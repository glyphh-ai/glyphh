# Drips

Drips plays visual effects over Claude, with sound: confetti, fireworks, hearts,
stars, bubbles, a matrix rain, an aurora and more. Play one with a
command, save your own recipes, and let Claude play them too.

```
/drips confetti
/drips 3 hearts stars
/drips -1 aurora
/drips stop
```

Drips works in Claude Code on a Mac. It's a one-time $8 per machine:
`/drips unlock` buys it. For games, see Games (`/games`).

## Requirements

- **macOS** and the **Xcode Command Line Tools**, which bring Swift
  (`xcode-select --install`). Drips builds its small overlay program with
  them, to play effects over Claude's window or the whole screen. Without
  them, effects don't play: Drips tells you once what to install.
- **Node.js 18 or newer** (https://nodejs.org). It runs the Drips page: your
  saved drips and the editor.

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
| `/drips <recipe>` | Plays a recipe, or one of your saved drips by name |
| `/drips list` | Lists the effects and your saved drips |
| `/drips save <name> <recipe>` | Saves a recipe under a name |
| `/drips delete <name>` | Deletes a saved drip |
| `/drips stop` | Stops every effect that keeps playing |
| `/drips page` | Opens the Drips page: your saved drips and an editor |
| `/drips unlock` | Buys Drips: $8, once, for this machine |
| `/drips key <licence>` | Unlocks Drips with a licence bought on another Mac |

`/drips` runs straight away, even while Claude is working.

## The Drips button

A **💧 Drips** button sits by the prompt: in the terminal, in the hint line
under it; in the desktop app, in the prompt's footer. Press it and a row opens just above the
prompt: **fireworks**, **confetti**, **hearts**, **stars**, and **gunfight**, then your
saved drips, then **■ Stop** while something keeps playing, and **✕** to
close the row. A press plays the effect the way `/drips` does, where your
**Where effects play** setting says. Until Drips is bought, the row
says so and **Open Drips** opens the page to buy it. To hide the
button, turn off **Drips button** under Drips in `/config`.

## Recipes

A recipe is a few words, in any order:

- **An effect**: `fireworks`, `hearts`, `confetti`, `stars`, `rain`,
  `bubbles`, `sparkle`, `spiral`, `emoji`, `wave`, `thumbsup`, `peace`,
  `cat`, `gunfight`, and the backgrounds `matrix`, `aurora`, `nebula`, `plasma`,
  `fireflies`, `starfield`. Name several and they play one after another.
- **A number from 1 to 10**: how many times to play them. Each effect
  starts 1.5 seconds after the one before.
- **A number between 0 and 1**: how see-through the effect is (`0.4`).
- **`-1`**: keep playing. The effect stays until you play the same
  recipe again, run `/drips stop`, or press Stop in the Drips page. Nothing
  plays for longer than 30 minutes.
- **A saved drip's name**: its effects join in.

`/drips` alone plays fireworks.

## Where effects play

Open `/config` and find **Where effects play** under Drips:

- **claude-window** (the default) plays effects over the window Claude is
  running in: the Claude desktop app's window, or the terminal window
  running Claude Code (Ghostty, Terminal, iTerm2, kitty, WezTerm, the
  VS Code and Cursor terminals, and others). The effect sits just above
  that window and moves and resizes with it. Windows in front of Claude,
  menus and notifications stay in front. If Drips can't find the window, it
  plays over the screen under the pointer and says so once.
- **fullscreen** plays effects over the whole screen under the pointer,
  above every app and on every Space.

Effects never take the pointer or the keyboard: you can keep working
through them. The first effect over Claude's window or the screen takes a
few seconds longer, while Drips builds its small overlay program with
Swift. It's built once and kept in `~/Library/Caches/glyphh-overlay`. Drips
needs no extra permission for this: it reads only where Claude's window is
and how big, never what's in it, so macOS doesn't ask for Screen Recording.

Before version 1.1, **claude-window** meant the page in the Browser pane. If
you chose it then, effects now play over Claude's window itself. Version 1.1
had a third choice, **browser-pane**, that played effects in the Drips page;
it's gone since 1.2, and a stored browser-pane plays over Claude's window.

Previews from the Drips page play where every effect plays, and a preview
that keeps playing stops by itself after 12 seconds.


## Sounds

Every effect has its own sound: rockets whistle up and boom in
`fireworks`, a popper goes off in `confetti`, the cat meows, and the
backgrounds play something soft and slow for as long as they stay. Every
sound is made as it plays; none is a recording. To turn them off, open
`/config` and turn off **Sounds** under Drips. The faint matrix that plays
while Claude's tools run is always silent.

## The Drips page

`/drips page` opens the page. **Your drips** lists each saved drip with its
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

## Buying it

Drips is a one-time $8 for each machine: no account, no subscription,
no trial. Until you buy it, effects don't play (`/drips list`, `delete` and
`stop` still work).

**Buy.** Run `/drips unlock` (or press **Unlock — $8** in the Drips page).
Stripe's checkout opens in your browser; pay there, and Drips unlocks
on its own a few seconds later. **Cancel** in the page stops it waiting.

**Another Mac.** In the Drips page of the Mac you bought it on, press
**Copy licence key**, then on the other Mac run `/drips key <licence>`.

**Offline.** Your licence is checked on your Mac, with a signature, and
Drips never calls home once it holds one.

## Where things are kept

Everything stays on your machine. Your saved drips are kept in Claude
Code's store for Drips, and so is your licence. The overlay program is kept in
`~/Library/Caches/glyphh-overlay`, shared with Games.

## Security

- The Drips page is served only on `127.0.0.1`, on a random port. Every
  request must carry a random key made for that session. The server
  refuses any other host name or origin, and the page can't be framed by
  another site.
- The session key is never written to a file or a log. The page is opened
  with a one-time address that stops working once it has been used.
- Each effect runs in a sandboxed frame that can run its own animation and
  nothing else: it can't reach the page, your files or the network.
- The overlay is built on your Mac from the source in the plugin
  (`native/overlay.swift`). It shows one effect, ignores the pointer,
  closes when the effect ends or after its time limit (never more than 30
  minutes), and quits if Claude Code goes away. To find Claude's window it
  reads only each window's owner, layer and position, never a title or what
  a window shows.
- Drips talks to Glyphh only while you unlock it: it asks glyphh.ai whether
  this install's purchase has gone through, sending the mod's name and a
  random install ID, never your drips or anything about your Mac. The
  licence is never shown to the page or written to a log.

## For developers

This mod is built from the private source repository to the Glyphh mod standard
(`docs/mod-standard.md` there). Its account code in `hooks/licence/` is a copy of the
shared module: change the source and sync, never the copy.

Each drip is one file in `hooks/drips/effects/` that builds its whole
document, listed once in `hooks/drips/effects/index.ts`. A new drip is a new
file there and a line in that list.
