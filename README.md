# workspaces

A Claude Code mod that brings Glyphh desktop workspaces into Claude Code:
layouts you define, switch between with `/dip`, that open web pages, files,
an editor, a git diff and a terminal. It runs on two surfaces, and they work
differently, because each can do different things (see [What we learned](#what-we-learned)).

| | In a terminal (Ghostty or kitty) | In the Claude desktop app |
|---|---|---|
| The grid | Drawn by the mod in a pane: drag `│` `─` to resize | The app's **own panes**: Files, Diff, Terminal, Browser |
| Web pages | Live, inside the grid cells (headless Chrome, streamed as frames) | Tabs of the app's browser pane (pop it out with ⤢) |
| Files / editor | The mod's file browser + editor, Save, ctrl+s | The app's Files pane, as a browser (no file opened) |
| Diff | The mod's diff cell: real `git diff` | The app's Changes pane |
| Terminal | The mod's cell: runs commands to the end | The app's Terminal pane |
| Folder | — | A layout moves the session to its folder |

## Commands

| Command | Does |
|---|---|
| `/dip` | Lists the layouts, numbered |
| `/dip 1`, `/dip IDE` | Switches to a layout by number or name (a prefix is enough) |
| `/dip back` | The layout before; again, and you are back (it bounces) |
| `/layouts [name]` | Opens the mod's grid pane (on desktop too) |
| `/stream [layout]` | Desktop: the layout as **one live page** in the browser pane (see below) |
| (tool) `page_read` | For Claude: list the layout page's open pages, or read one page's text |
| `/layouts-probe` | Checks which of the desktop app's controls the mod can reach |
| `/files` | Desktop: the Files pane, as a browser |
| `/diff` | Desktop: the Changes pane |
| `/term` | Desktop: the Terminal pane |
| `/browser [url]` | Desktop: the Browser pane, or a page opened in it |
| `/editor <name>` | Desktop: a file in the Files pane, by path or file name (several matches are listed) |
| `/glyphh [section]` | The Glyphh panel: Account, Org, Plan, Billing, Workspaces (signed out, each is Sign in). See [Glyphh account](#glyphh-account-glyphh) |
| `/glyphh signin`, `/glyphh signout` | Sign in by device flow (the code and link are also printed), or sign this machine out |
| *"sign in to Glyphh"* (ask Claude) | The sign-in card in the chat, from the mod's MCP server. See [The sign-in card](#the-sign-in-card-mcp-app) |

`off` after a pane command hides it (`/files off`). The long names answer too:
`/terminal`, `/changes`, `/edit`. A name Claude Code already ships is refused,
so the pane keeps its other name; a toast at load says when that happened.
After the mod adds a command, the desktop window may need **View › Reload**
before it recognises it.

Pages of the layout you leave stay alive (parked): switching back reuses them.

## The layouts

1. **Comms**: Gmail full height on the left, Slack top right, Calendar bottom
   right. Desktop: the Browser pane shown with those three as tabs, Gmail in
   front; the other panes close; the session goes to `~/development/yo`.
2. **Browse + file**: a browser beside a file.
3. **Two browsers**: two browsers above two files.
4. **IDE**: file browser over the git diff (left), editor over the terminal
   (centre), Claude (right, a mock: the real conversation is the chat).
   Desktop: sidebar collapsed; the app's Terminal, Changes and Files (browser)
   panes open in that order (Files last keeps its list), the rest close; the session moves to `~/development/yo/app`.
5. **Files**: the file browser alone. Desktop: just the app's Files pane, as a
   browser.

A layout is the Glyphh workspace grid (`GridLayout` in yo/app's
`layout-manager.ts`): `cols`, `rows`, `colWidths`, `rowHeights` (fractions), and
cells at `col`/`row` with an optional `rowSpan`. A cell is a `browser` (`url`),
`file` (`path`), `tree`, `editor`, `terminal`, `diff` or `claude`. On the
desktop a layout also names the app panes it opens and its folder:

```ts
desktop: { panes: ['files', 'changes', 'terminal'], collapseSidebar: true, folder: '/Users/timmetim/development/yo/app' }
```

`panes` takes `files` (the Files pane as a browser), `changes`, `terminal`,
`browser`, and `editor` (the Files pane opened at the file being edited). They
open in the order listed; every other pane closes. `/dip` prints a line per
pane: `Files ✓ · Changes ✓ · Terminal ✗ <why>`.

The layouts live in `~/.glyphh/workspaces/<slug>.json`, one file per workspace
(below). On the first run (no `~/.glyphh/workspaces` folder yet) the built-in
layouts above, with any sizes dragged before, are written there; from then on
the files are the source of truth for `/dip`, `/stream` and the grid. Dragged
sizes are written back to the workspace's file (and kept in `$.store` too,
the fallback where `~/.glyphh` cannot be read). A folder emptied on purpose
stays empty.

## Glyphh account (`/glyphh`)

`/glyphh` opens one panel with five sections; `/glyphh <section>` opens it on
one. Signed out, every section shows **Sign in**. Where Claude Code refuses
the name (a command or skill already has it), the command is `/glyphh-account`.

| Section | What it does (API in `server/docs/architecture.md`) |
|---|---|
| Sign in | Device flow: shows the code and the link; on the desktop opens `verification_uri_complete` in Claude's browser pane, in a terminal prints it; polls `/v1/device/token` at `interval`, 5 s slower on `slow_down`, until the token, `expired_token` or `access_denied`. Copy link, Cancel |
| Account | Name (Enter renames), email, sign-in providers, installs (revoke one; revoking this one signs out), Sign out |
| Org | Name (admin renames), members with roles (admin removes, never the admin), invites: send (the link is shown to copy), revoke, pending |
| Plan | The plan, its limits and what is used (`/v1/me`), the license this machine holds (valid, until, RPA on/off), every plan (`/v1/plans`) |
| Billing (admin) | Checkout (not subscribed) or switch plan (subscribed), seats, Card and invoices (Stripe's portal); Stripe's pages open in the browser pane, or as a link in a terminal |
| Workspaces | List (with "local only" for names the server never had, and Register), create (the name goes to `POST /v1/workspaces` first: refused past the limit, nothing made), and for the one picked: rename, model, folder, permission mode, effort, delete |

Every action ends in one line under the tabs: what it did, or why not. A
refusal reads `{"error": {code, message, trace_id}}`; `E_LIMIT` reads as
*Limit reached: workspaces. 2 of 2 used. The Pro plan lifts it.* A 401 from
any call means this install was revoked: the machine signs out.

**Signing in, end to end:** `/glyphh signin` (or **Sign in** in the panel) →
`POST /v1/device/code {name, surface, mod_version, machine_id}` → the panel shows the code,
and the desktop opens the sign-in page in the browser pane (a terminal prints
the link) → the person continues with Google or GitHub and approves → the
mod's poll gets `{access_token, install_id}` → `~/.glyphh/install.json`
(0600) → `/v1/me` and the license are fetched and the panel shows the account.

**Machine id:** every device-code request carries `machine_id`, so the server
keys installs by machine and a machine signing in again reuses its install.
It is sha256(`"glyphh:" + value`) in hex; the value never leaves the machine.
The value (`hooks/glyphh/machine.ts`, shared with the MCP server): macOS's
IOPlatformUUID (`ioreg`), Linux's `/etc/machine-id`, Windows' MachineGuid (or
`wmic csproduct get uuid`); else the default route's interface's MAC; else a
random id kept once in `~/.glyphh/machine.json`. Worked out once per process.

**Server:** `GLYPHH_SERVER_URL`, default `http://localhost:8080`. Every call
but the device flow's and the plans list carries `Authorization: Bearer
<install token>`.

### The sign-in card (MCP App)

Ask Claude *"sign in to Glyphh"*: the `glyphh-sign-in` skill has it call
`glyphh_sign_in`, from the MCP server the mod ships (`.mcp.json` at the
plugin root: `node ${CLAUDE_PLUGIN_ROOT}/mcp/dist/server.mjs`, stdio; Claude
Code starts it with the plugin as `plugin:workspaces:glyphh`). Signed in
already, it answers who. Otherwise it starts the device flow and returns the
card, `ui://glyphh/sign-in/1` (`text/html;profile=mcp-app`, the ext-apps
bridge inlined, no network of its own, the host's theme variables): the code,
large, and **Sign in**, which asks the host to open the page. The card polls
`glyphh_sign_in_status` (app-only) every 3 s; the server asks
`/v1/device/token` no faster than `interval` (+5 s on `slow_down`), writes
`~/.glyphh/install.json` as the mod does (0600, renamed into place) and the
card says *Signed in as …*, or that the code expired or was declined, with
**Start again**. Without cards the tool's text has the code and link; asking
again finishes a sign-in once approved. `/glyphh` picks up an install.json
written meanwhile. Change the card: edit `mcp/card/sign-in.html` and bump the
`ui://` address (hosts cache a card by it). Change the server: edit
`mcp/src`, then `mcp/build.sh` (installs the build tools outside the plugin,
type-checks, bundles everything into `dist/server.mjs`, which is committed:
the plugin needs only `node`, 20 or later).

### `~/.glyphh`

| File | What |
|---|---|
| `machine.json` | `{id}`: a random machine id, made only where no hardware id or MAC can be read |
| `install.json` | `{install_id, token}`, mode 0600: written by `sh` under `umask 077` to a temporary file and moved into place, the token on stdin, never on a command line or in a log |
| `license.json` | The server's signed license answer and the key it was checked with. Refreshed from `GET /v1/license` at session start and sign-in; its Ed25519 signature is checked against `GET /v1/license/key` before it is kept (a bad one never is), and again offline at each start. An expired license is not valid. RPA is gated on `features.rpa` |
| `workspaces/<slug>.json` | One workspace: `name`, `model`, `folder`, `permission_mode`, `effort`, `cols`, `rows`, `col_widths`, `row_heights`, `desktop_panes`, `collapse_sidebar`, `cells` (`panel`, `col`, `row`, `row_span`, `tab` for a browser cell, `path`), `tabs` (`url`, `name`, `no_redirect`, `rpa: {commands, sequences}`) |

The workspaces' order is kept in the mod's store. Only names go to the server.

The license may come in any of three shapes: a compact JWS (`{token}`, EdDSA),
`{payload, signature}` (the signature over the payload's bytes), or
`{license, signature}` (over the canonical JSON: keys sorted, no spaces,
non-ASCII as `\u` escapes, as Python's `json.dumps(..., sort_keys=True,
separators=(",", ":"))`). The key: `{key}` or `{public_key}` as raw 32 bytes in
base64 or base64url, PEM (SPKI), or a JWK (`kty: OKP`, `crv: Ed25519`, `x`).
The hooks environment's `crypto.subtle` has `digest` alone (no `importKey`,
no `verify`), so Ed25519 is checked in `hooks/glyphh/ed25519.ts` on BigInt and
SHA-512 (RFC 8032's test vector and Node's own signatures check out).

## Run it

Mods ("function hooks") are early access in Claude Code 2.1.x, hence the
variable.

**In a terminal**, with live pages: the terminal must be Ghostty or kitty
(they draw pictures; macOS Terminal and iTerm2 do not), and Google Chrome must
be installed.

```bash
CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1 claude --plugin-dir ~/development/glyphh/workspaces
```

In any other terminal a browser cell says so and offers **Open in Ghostty**,
which relaunches the same session there.

**In the Claude desktop app**: link the folder into the session's mods folder
(`~/.claude/dev-mods/<session id>/workspaces`) and accept *Enable hot reloading
for this session*. Edits then reload by themselves.

The panes are opened through the app's **View** menu (see below), clicked with
`osascript` through System Events: the Claude app needs Accessibility
permission (System Settings › Privacy & Security › Accessibility). It already
has it when computer use is on.

To let `/dip` open browser-pane tabs itself, allow the two tools in
`~/.claude/settings.json` (otherwise auto mode refuses the mod's call and the
mod asks Claude to open the tabs, a turn slower):

```json
"permissions": {
  "allow": ["mcp__Claude_Browser__preview_start", "mcp__Claude_Browser__tabs_select"]
}
```

## The layout page (`/stream`)

The desktop app has one browser per session and no way to place its panes, so
`/stream` draws a whole layout as one page in the browser pane: tabs for the
layouts (alt+1…9), the grid with draggable dividers (the shape is saved back
to the mod), and every browser cell a live page: headless Chrome
(`helper/chrome.mjs`) renders it and its picture arrives as **WebRTC video**;
clicks, scrolls, keys and paste go back over CDP. A badge in each cell's bar
says `webrtc`, or `jpeg` when it fell back.

How the video is made: headless Chrome will not capture its own tabs (below),
so a hidden **bridge page** in the same Chrome (`helper/bridge.html`) reads
each cell's screencast frames, draws them on a canvas, and sends the canvas
as a WebRTC track (`canvas.captureStream`, up to 8 Mbit/s, 30 fps). Chrome
encodes it; DTLS-SRTP carries it; no ICE server is named, so it never leaves
the machine. The server only passes the offer and answer along (no trickle).
The cell shows the JPEG stream (`multipart/x-mixed-replace` in an `<img>`)
until the video plays, then drops it; if WebRTC fails it stays on JPEG. Pages of a layout you leave are
parked (no frames) and come back as they were. Non-browser cells point at the
app's own panes (`/files`, `/diff`, `/term`).

Tested 2026-10-13: Comms (Gmail, Slack, Calendar) live in one pane, all three
cells on WebRTC, scrolling reaches the page, switching layouts and back keeps
each page's state and comes back on WebRTC.

Locked to the machine and the page: `127.0.0.1` only, a random port, a random
token on every request (`?t=` or `X-Token`, compared in constant time), `Host`
must be `127.0.0.1:<port>` (no DNS rebinding), any `Origin` must be the page's
own, CSP `frame-ancestors 'none'`, no referrer. The token is the key to the
signed-in Chrome; it is never written to a file or log.

Chrome itself is driven over a **private pipe** (`--remote-debugging-pipe`),
not a debugging port: no other program on the machine can attach to the
signed-in pages. (A port would let any local program drive them.) What stays
open to programs running as you is what is open for any Chrome: its profile
files on disk.

**Claude reads a page only through `page_read`**, a tool the mod registers:
`page_read` lists the open pages, `page_read { cell }` returns one page's
text. It is a step you see, under the permission rules; the page text is
treated as untrusted content. Claude can also see the cells in a screenshot
of the browser pane, like anything on screen.

What we hit building it:
- **Chrome cannot capture its own tab here**: `getDisplayMedia` with
  `preferCurrentTab` and `--auto-accept-this-tab-capture` fails with "Could not
  start video source", headless and windowed alike. Hence the bridge page
  (above); the other way would be ffmpeg + werift, as yo/app's
  `panel-webrtc.ts`.
- **WebRTC between two browsers on one machine**: the helper's Chrome runs
  with `--allow-loopback-in-peer-connection` and without mDNS host names
  (`--disable-features=WebRtcHideLocalIpsWithMdns`), so the pane's peer can
  reach it with no ICE server. A static page sends no new frames, so the
  bridge redraws the last one every second for the encoder's keyframes.
- **Background tabs go blank**: headless Chrome stops painting every tab but
  the front one. Each cell is its own window, focus is emulated, and the
  backgrounding switches are off.
- **Six connections per server**: a removed `<img>` keeps its stream open, so
  switching layouts starved the page's own requests; the old streams are
  closed first. Up to about four browser cells fit on one layout.
- **Twitchy video**: the bridge's canvas first followed each frame's size, so
  the video's resolution kept changing and the picture jumped; and every
  re-measure of a cell restarted its screencast, flashing a frame. The canvas
  is now the cell's size (frames scaled in, resized only when the cell is),
  sizes move in 2-pixel steps after 250 ms of quiet, and a page already live
  at the same size is left alone. Measured after: one video size per cell
  over five seconds of sampling.
- **A stream never finishes loading**: started before the page's own load, it
  held the page (and the pane's navigation) open; streams start after load.

## Pieces

| File | What it is |
|---|---|
| `hooks/register.tsx` | The hooks module: layouts and state, `/dip` `/layouts` `/layouts-probe`, the grid pane, the desktop app's panes, git diff, commands |
| `hooks/divider.tsx` | A draggable divider (a `Client`): posts the running drag delta |
| `hooks/surface.tsx` | The input layer over a terminal browser cell: clicks and keys in page pixels, batched per frame |
| `hooks/editor.tsx` | The text editor (a `Client`): cursor, typing, arrows, page keys, ctrl+s |
| `helper/chrome.mjs` | Headless Chrome over CDP, shared: one page per cell (own window, never backgrounded), screencast frames, input |
| `helper/browser.mjs` | The terminal's host: PNG frames to files the terminal draws, commands over a Unix socket |
| `helper/viewer.mjs` + `viewer.html` | The layout page: local server behind a token, WebRTC signalling, JPEG fallback, the grid page, `page_read`'s text |
| `helper/bridge.html` | Runs hidden in the helper's Chrome: cell frames → canvas → WebRTC video |
| `helper/windows.mjs` | A layout as real Chrome windows tiled on screen (an experiment; not wired to `/dip`) |
| `hooks/layouts.ts` | The built-in layouts (migrated to `~/.glyphh/workspaces` on first run) |
| `hooks/glyphh/index.tsx` | Glyphh's hooks: `/glyphh`, its panel, the session start (`~/.glyphh`), dragged sizes on to the files. The one file holding `$` and the account atoms; hands the rest a `Host` |
| `hooks/glyphh/host.ts` | The `Host` interface the account code works on (the engine's scan follows `$` only within the file that received it) |
| `hooks/glyphh/api.ts` | The API client: base URL, bearer, refusals, `E_LIMIT` |
| `hooks/glyphh/device.ts` · `account.ts` | Device-flow sign-in and polling · install.json, `/v1/me`, sign out, revoked installs |
| `hooks/glyphh/license.ts` · `ed25519.ts` | The license: fetch, check, keep, gate · Ed25519 on BigInt |
| `hooks/glyphh/home.ts` | `~/.glyphh` paths and JSON files, the 0600 writer |
| `hooks/glyphh/wsmodel.ts` · `wsfiles.ts` | A workspace file ⇄ a layout · the files read, written, migrated, mirrored into the layouts |
| `hooks/glyphh/actions.ts` · `wsactions.ts` | What the Account, Org, Plan, Billing and Workspaces sections do |
| `hooks/glyphh/panel.tsx` · `sections/*.tsx` · `ui.tsx` · `shape.ts` | The panel and its sections; elements and links; reading the server's answers |
| `hooks/glyphh/command.ts` · `open.ts` · `state.ts` | `/glyphh`; opening pages in the browser pane; the panel's note |
| `hooks/glyphh/machine.ts` | The machine id: its sources, fallbacks and hash (also bundled into the MCP server) |
| `.mcp.json` · `mcp/src/server.ts` | The MCP server's declaration · the server: the tools and the card resource |
| `mcp/src/flow.ts` · `install.ts` | The card's device flow, no Node in it · install.json and the machine probe over Node |
| `mcp/card/sign-in.html` · `mcp-app.js` | The card · `@modelcontextprotocol/ext-apps` 2.0.3's bridge, vendored |
| `mcp/build.sh` · `dist/server.mjs` | The build · its output, committed |
| `skills/glyphh-sign-in/SKILL.md` | Tells Claude to call `glyphh_sign_in` when asked to sign in |
| `types/index.d.ts` | The layout and workspace-file types and the mod's `$.state` contract |
| `tests/layouts.test.ts` | 11 tests: drawing, switching, dragging, the IDE editor's save, `/dip`, the terminal check |
| `tests/glyphh-mcp.test.ts` · `glyphh-machine.test.ts` | The card's flow on the fake server · the machine id's sources, fallbacks and hash |
| `mcp/test/install.test.mjs` | `node --test mcp/test`: install.json's mode and atomic write, the machine probe on this machine |
| `tests/glyphh-*.test.ts` | 27 tests on a fake server (`fake-server.ts`) and a fake host (`fake-host.ts`), no network: the client, storage, the license, device-flow polling, limit errors, each section's actions, workspace files and migration, and the panel through the engine on both surfaces |

The Chrome profile (sign-ins) lives at
`~/Library/Application Support/glyphh-workspaces/chrome`, apart from your own
Chrome. A second session running at once gets a throwaway profile.

## Test

```bash
CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1 claude plugin test ~/development/glyphh/workspaces
claude plugin validate ~/development/glyphh/workspaces
node --test mcp/test
```

## What we learned

What a Claude Code mod can and cannot do, found while building this (Claude
Code 2.1.285–2.1.295, 2026-10-13).

**A mod can**: draw panes, a band above the prompt, toasts and status text;
register slash commands and tools the model can call; hook tool calls, prompts
and the system prompt; run processes, read and write files, fetch over HTTP or
a Unix socket; keep state per session and across sessions; call any MCP server
the session has connected (`$.mcp.call`), the desktop app's own controls
included.

**Pictures exist only in a terminal.** The `Image` element (and `Raster`) is
the terminal's alone, drawn with the kitty graphics protocol: Ghostty, kitty,
partly WezTerm. The desktop app's pane has no picture element; its `Svg` runs
in a frame with scripts off, so no video or WebRTC either. A program inside a
terminal can only send that terminal escape codes it understands, so no code
in the mod (Ghostty's included) makes macOS Terminal draw pictures.

**The desktop app's panes can be driven, not placed.** The mod reaches
`Claude_Browser` (tabs), `ccd_view`, `ccd_window` (sidebar, split view,
pop-out windows) and `ccd_directory` (move the session's folder). None of them
sets a pane's position or size: the app arranges its panes, so a layout there
is *which* panes are open with what in them. The browser pane cannot be popped
out by a call: the person presses ⤢ once.

**The View menu is the door the tools don't have.** `ccd_view`'s `show_pane`
takes only `diff`, `file`, `terminal`, `pr`, `tasks`, `plan`, `artifact`; its
`file` needs a `path` to a file (a folder is refused), so it can open the
Files pane only at a file, never as the browser, and nothing shows the browser
pane. The app itself has more (read from its code, `app.asar`, 2026-10-13): a
`files` pane apart from `file`, toggled by **View › Show Files**
(Cmd+Shift+F). The View menu lists `Show Terminal`, `Show Changes` (Cmd+Shift+D),
`Show Browser`, `Show Files`, `Show Side Chat` (Cmd+;) and `Close Pane`; each
turns to `Hide …` while open, which is how the mod tells what is open. The
mod clicks them with:

```bash
osascript -e 'tell application "System Events" to tell process "Claude" to click menu item "Show Files" of menu 1 of menu bar item "View" of menu bar 1'
```

and reads them with `get name of every menu item` in place of `click …`.
The **Split View** submenu (Move Split View Left/Right/Up/Down) moves whole
sessions shown side by side, not the side panes. Menu labels are the app's
English ones; another language or a renamed item breaks the click.

**One browser per session.** The browser pane belongs to its session (its
tools are bound to it); the app has no second browser in a session. Several
browsers natively means several sessions in Split View, each with its own
pane, and that does not get far: the `start_session` tool is behind a
feature flag (off here: "Starting sessions is not enabled here"), View ›
Split View › New Session on the Right opens only a *draft*, which has no
browser until someone sends it a message, and a session's browser can be
driven only by that session's own Claude or mods. Tried 2026-10-13.

**`$` stays in its file.** The engine reads a module's source before it runs
it, and follows `$` only into functions declared in the file whose hook
received it: passing `$` to an imported function, or reading state through an
atom declared in another file or handed in as an argument, is refused at load.
`on` may be passed across files. So a mod split into modules keeps every `$`
call and atom in one file and hands the rest an interface of closures
(`hooks/glyphh/host.ts`). Only one `session.start` hook per plugin may have no
matcher; a second one is split into `{ isInteractive: true }` and `{ isInteractive: false }`.

**A `Link` must be `https:` (or `http://localhost`).** Any other address
refuses the whole tree, not just the link; the panels draw other addresses as
text.

**No text field on mobile, no theme fonts.** The desktop and terminal tables
have `Input` and `Select`; mobile has neither. Colors can follow the theme
(theme keys such as `error`, `success`, `claude`); fonts cannot be set.

**Auto mode checks the mod's calls.** Opening a web page from the mod
(`preview_start`) was refused by the auto-mode check; an allow rule for the
tool fixes it (see Run it). Moving the folder asks the person to approve it.

**Live pages in a terminal work** but are pictures: headless Chrome's
screencast as PNG files the terminal draws, clicks and keys relayed back. Fine
for a demo; real use wants real pages, which is the case for the next step.

**Streaming WebRTC into Claude was not possible**: no surface of Claude Code
plays video. The Glyphh desktop app's panel host (`panel-host.ts`,
`panel-webrtc.ts`) remains the way to stream a page with the person's logins.

## Where it goes next

- A **standalone app** (Electron) needs no mod at all: real web views, the
  layout grid, `.dip` and `.drip`, and Claude Code itself in a terminal cell
  (xterm.js + node-pty) or headless (`claude -p --input-format stream-json
  --output-format stream-json`, which is how the Claude desktop app runs it).
  The CLI bridge removed from yo/app on 2026-09-28 is in its git history.
- **Licensing**: built (`/glyphh`, above). A local check only keeps honest
  people honest; what must be paid for lives on the server.
- **Claude builds the layouts**: tools the mod registers (`layout_list`,
  `layout_save`, `layout_open`, `cell_set`, `page_read`), no MCP server needed.
- **Distribution**: the plugin marketplace for the mod; PyPI for a launcher
  that checks Chrome and Ghostty and starts the session.
