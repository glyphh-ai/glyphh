# The glyphh plugin's changelog

Newest first. The version is `.claude-plugin/plugin.json`'s and the marketplace's.

## 1.18.1 — 2026-11-04

For Anthropic's directory: `.claude-plugin/icon.png`, and the README's *What it does on your computer* says what the
plugin sends and where, what it reads, runs and writes, and how it touches tool calls. The hook's User-Agent is
`glyphh-hook/1.18.1`.

## 1.18.0 — 2026-11-04

The beam: the Ada skill names the connector's `ada_beam {start, hops, width?, values?, miss?}`, a chain of models
where one model's outcome is the next model's question, says when it suits (a state machine of gates, a pipeline
where one answer is the next input) and how to read `outcome`, `p`, `ends`, `paths` and `lost`; it counts as one
read per hop. The glyphh-cli skill names `glyphh beam START --hops JSON` (SDK 3.10). The hook's User-Agent is
`glyphh-hook/1.18.0`.

## 1.17.0 — 2026-11-03

`/dip` left the plugin: it is its own plugin now, `dip@dip` from `timmetim/dip`. The command, the Dip pane, the layout
brief, `hooks/dip_arrange.py` and the permission answers for a dip's calls are gone from here. The hook's User-Agent is
`glyphh-hook/1.17.0`.

## 1.16.0 — 2026-11-03

A dip builds the grid. No tool of the app places a pane, but each tile has a keyboard Move handle, and the new
`hooks/dip_arrange.py` works those through macOS accessibility: Claude can sit on the right, a pane can span the top,
and where every tile landed is checked against the grid. It needs `python3` and Accessibility permission, and takes
the keyboard focus for a few seconds. A shape with no tile on an edge of the rest (a plain 2 × 2) can't be built; the
editor says so. `/dip save` and From this workspace now read the grid off the panes as they sit, so a layout can be
dragged into place and saved. The hook's User-Agent is `glyphh-hook/1.16.0`.

## 1.15.0 — 2026-11-03

A dip arranges what the app lets it. The app places a pane by when it opens (the first beside Claude, the second under
it, the third in a new column), so a dip now closes every pane and opens the layout's down each column, a pane's tabs
or terminal tabs at its turn. Claude stays on the left and sizes stay the app's; the editor says so. Every use reads
the layouts from the store first: a session that started before a layout was saved missed it, and saving from there
would have lost it. The hook's User-Agent is `glyphh-hook/1.15.0`.

## 1.14.1 — 2026-11-03

The Dip pane draws at three columns. A third of a row was a width of 33.33…%, which a Box refuses, and the whole pane
went with it ("glyphh has not drawn in this pane"). The hook's User-Agent is `glyphh-hook/1.14.1`.

## 1.14.0 — 2026-11-03

A dip is the mod's alone: no prompt to Claude, ever. Auto mode refused the mod's tool calls because a slash command
gives its classifier no request to read, so the mod now answers the permission check (`tool.check`) for its own calls
to the app's panes, browser tabs, the layout's folder and a bare terminal tab; Claude's own calls are untouched, and a
command typed into a terminal tab is put to the person. The Files pane opens from the View menu, since `show_pane`
needs a file. What could not be done is said in the reply and the pane. The hook's User-Agent is `glyphh-hook/1.14.0`.

## 1.13.1 — 2026-11-03

A dip whose steps were refused now reaches Claude. Its prompt opened with `/dip`, and the engine refuses a prompt
that opens on a slash, so the steps were dropped while the pane said Claude was finishing them. Why each step was
refused goes to `~/.glyphh/dip-log.txt`. The hook's User-Agent is `glyphh-hook/1.13.1`.

## 1.13.0 — 2026-11-03

Dip layouts have a grid. The Dip pane's editor draws the layout as the desktop app's layout editor does: columns and
rows up to 4, press a cell to choose what fills it (Claude, a pane, or nothing), merge and split, a pane moving rather
than doubling. This replaces the pane toggles, whose state never showed on the desktop. The editor has one Save and
one Cancel, with no save beside each field. Layouts saved before grids get one from their panes: Claude on the left,
the panes beside it. The app's tools open panes but cannot place them, so a dip shows the grid's panes in reading
order. The hook's User-Agent is `glyphh-hook/1.13.0`.

## 1.12.0 — 2026-11-03

Dip: `/dip <layout>` bounces the session between workspaces. A layout holds Claude's folder, the browser pane's tabs
(one in front), the side panes, the terminal tabs (each with a folder and a command) and a brief Claude reads while it
is active. Dipping calls the desktop app's own tools (folder, browser, panes, terminal) through the permission check,
closes the tabs the last dip opened, and hands any refused step to Claude as one prompt. `/dip` opens the Dip pane to
make and edit layouts; `/dip save <name>` keeps the session as it is; `rm` and `off`. Layouts live in the plugin's
store. No sign-in needed. The hook's User-Agent is `glyphh-hook/1.12.0`.

## 1.11.0 — 2026-11-03

Bots' gates (SDK 3.9). The glyphh-bots skill says which gate suits which job (per-item gates for lists, ladders for
cost, learned approvals for outward actions, world-answered gates for outcomes that arrive later, hard limits
always), how a gate asks (`ask_below`, `min_precedents`, `audit`, `shadow`, `max_questions`, `default`), and the new
commands: a batch of items answered at once (`glyphh bot continue <slug> 1=read 2=skip rest=skip`), `outcome` (what
really happened), `wrong --item`, `gates` (what each gate learned), `report` (an HTML page with the ask rate falling
run by run), and `pause` / `resume` (the kill switch). The demo: make the Hacker News reader through the
orchestrator, answer its batches, watch the report. Claude still never answers a gate, a batch or an approval for
the person. The glyphh-cli skill's pointer names the new commands; the hook's User-Agent is `glyphh-hook/1.11.0`.

## 1.10.0 — 2026-11-03

Glyphh bots: programs that run a Claude agent behind gates that learn, made and trained from Claude (SDK 3.8's
`glyphh bot`).

- The glyphh-bots skill: "make me a bot that ..." goes through the orchestrator (`glyphh bot new`: its make_bot gate,
  then its builder writes the bot, checked and installed, trusted `ask_all`); Claude runs a bot, asks the person each
  gate's or approval's question and carries the run on with their answer (`glyphh bot continue`), records a run a
  gate got wrong (`wrong`), reviews trust and keep from each bot's record (`review`, `verdict`) and installs a
  routine (launchd on a Mac). Hard gates are program code (`{"_end": why}`), learned gates are Ada; no bot acts
  outward (sends, posts, pays, deletes) without the person's yes until its trust is `autonomous`, and Claude never
  answers a gate or an approval for the person.
- The glyphh hooks reach the server again (the fix of 1.9.2, which was not released on its own). Cloudflare in front
  of api.glyphh.ai refused urllib's own `Python-urllib` User-Agent with error 1010 (a 403), and a refused hook says
  nothing, so no personality, rules or recall reached Claude. `hooks/glyphh_context.py` now sends
  `User-Agent: glyphh-hook/1.10.0`.

## 1.9.1 — 2026-11-02

Jobs can be stopped. The Ada skill names the connector's `ada_job_cancel` (a job not started ends at once, a running
one at its next step, failed `E_CANCELLED`) and the stage `ada_job` now answers (what a job is doing now); the
glyphh-cli skill names `glyphh cancel ID` (SDK 3.7).

## 1.9.0 — 2026-11-02

Your glyphh: a memory of you that any AI on the Glyphh connector shares, built from the server's new template
library (glyphh-ai/server `docs/specs/templates.md`).

- The glyphh-memory skill: "build my glyphh" installs the Agentic memory template through the connector
  (`templates`, `template_install`), seeds it with what the person wants every AI to know, and from then on keeps
  what they tell Claude, their rules and corrections, and how they like it to be (`glyphh_remember`), recalls before
  acting (`glyphh_recall`) and forgets on their word (`glyphh_forget`).
- Two command hooks (`hooks/glyphh_context.py`): `SessionStart` puts the person's personality and rules before
  Claude, `UserPromptSubmit` what their glyphh holds that bears on the prompt. Signed out, with nothing installed,
  offline or slow (4 s), they add nothing.

## 1.8.0 — 2026-11-02

rrotor shelved: the plugin is Glyphh's account, Ada and the ledger again. Nothing is deleted.

- The rrotor, rrotor-programs and publish skills move to `shelved/skills/`, where Claude Code does not load them:
  "install rrotor" and "publish this to my org" no longer reach a skill.
- The panel has no Apps section, the Account section no rrotor row, and `/glyphh publish`, `/glyphh link` and
  `/glyphh apps` answer the usage line. The mod no longer asks after a local rrotor. `GLYPHH_RROTOR=1` in Claude
  Code's environment brings all of it back (`hooks/glyphh/shelved.ts`).
- `/glyphh`'s description and argument hint name the sections it has.

## 1.7.2 — 2026-11-02

rrotor kept at the release this plugin was made against. Until now the rrotor skill's script pinned 0.1.0 while
the plugin shipped apps for 0.2.0 and every type for 0.3.0, so "install rrotor" gave a rrotor without
`app_publish` and a session could not publish at all.

- The script pins rrotor 0.3.0, and CI holds that pin, the compose file's default and the Helm chart's `appVersion`
  to one value; `rrotor.sh update` pulls the pinned release and makes the container again on the same volume, port
  and token, then links it; `status` says `pinned` and `update_available`.
- The Account section marks this machine's rrotor "Update to 0.3.0" when it is behind, with **update** doing the
  same from the panel; `/glyphh publish` to a rrotor without apps says to update rather than Not Found.
- The rrotor skill triggers on "update rrotor" and on a tool missing from rrotor's set; the publish skill says what
  to do when `app_publish` is not among the tools, instead of handing the person a file.

## 1.7.1 — 2026-11-02

The panel redrawn in Claude's own look, every section on one kit. Nothing of what it does changes.

- One kit (`hooks/glyphh/ui.tsx`) draws every section: a title with one line under it, groups under small labels,
  rows with the thing first, a dim line under it and its actions at the right, labelled fields that line up, chips
  for a state or a kind (This device, Admin, Your plan, Awaiting review, the app's type), one quiet line for an empty
  list, the panel's last word in a bordered note, and the section tabs as text with the open one in Claude's colour.
  The terminal gets the same shapes on one line each.
- Apps: a card's title row carries the type chip and the state, the rrotor and version sit at the right, the
  roles and who published it on one dim line with the actions beside them; a rejected app says its reason in red;
  an empty list says so once, and the page line shows only when there is something to page.
- Account, Org, Plan and Billing: the same rows and fields; a member's row says Admin or You; the plan the org is on
  is marked on Plan and Billing alike; Billing's standing (status, renewal) reads as fields.

## 1.7.0 — 2026-11-02

One word everywhere: **app**. What Claude makes and publishes to the organisation is an app, whatever it is, and
publishing now takes every kind. Nothing of the Ada skills, the account panel or the ledger changes.

- **Artifacts is now Apps.** `/glyphh artifacts` is `/glyphh apps`, the panel's tab says Apps, and the server's API it
  reads is `/v1/apps` (nothing answers at the old address, and there is no alias). "Artifact" is Claude's word for
  the file in the session; what sits on your rrotor, in the catalogue, in Claude's `apps` tools and on the platform's
  Apps page is an app, and the ruling of 2026-11-02 is one word for it everywhere.
- Every app has a **type**: page, dashboard, doc, diagram, deck or design. Each card's first line says it (`Dashboard
  · acme-prod · v3`), and a **type filter** beside the search cycles All types → Pages → Dashboards → Docs → Diagrams
  → Decks → Designs → All types.
- `/glyphh publish <file>` takes every file rrotor serves: a page (`.html`, `.jsx`, `.tsx`), a document (`.md`,
  `.pdf`), a diagram (`.mmd`, `.svg`) or an image (`.png`, `.jpg`, `.jpeg`, `.webp`, `.gif`). The type follows the
  extension unless `--type` says it (a `dashboard` or a `deck` is always said, never inferred); a PDF or an image goes
  as base64; any other file is refused before rrotor is called, in rrotor's words. The reply names the type.
- The `publish` skill finds the file for each source (a Claude Code artifact; a path; a Claude Doc exported to
  Markdown; a Claude Slides deck or a Claude Design exported to PDF or PNG by the person; a Claude Dashboard, which
  has no export, rebuilt as a dashboard app with one function per chart, run as the viewer with their own CLI
  sign-ins and cached with a schedule when the source is slow), knows rrotor's React shell (one `.jsx` or `.tsx`,
  the packages claude.ai's React artifacts import, Tailwind classes, a default export) and offers `app_approve` to a
  reviewer. The rrotor skill names the tools as they are now: `apps`, `app_approve`, `app_reject`, `app_retire`,
  `app_publish` (with `type`) and `apps_list`.
- Two more example apps under `programs/`: `app_react` (one `.tsx`, a recharts bar chart) and `app_diagram` (one
  `.mmd`, a sequence diagram); `app_dashboard` says `"type": "dashboard"`.

## 1.6.1 — 2026-11-01

The local rrotor linked to Glyphh. Nothing else changes.

- `/glyphh link`, and **link** beside "This machine's rrotor" in the Account section: the server issues the local
  runtime's token to this install (`POST /v1/runtime/local`, rotated each time it is asked), rrotor takes it
  (`PUT /v1/runtime/token`) and connects out; the reply says when it is online, or that it is still connecting, or
  why not, in the server's or rrotor's words. Linked, the rrotor shows on the platform's Runtimes page, the apps
  published to it reach the organisation's catalogue, and it gets the organisation's licence key. Until now nothing
  in the plugin made this link, so a local rrotor never appeared on the platform.
- The rrotor skill's `connect` (and `start`) link the rrotor the same way once it answers, when this machine is
  signed in; `status` says the link's state; `link` does it alone.

## 1.6.0 — 2026-11-01

Pages published to the organisation. Nothing of the Ada skills or the ledger changes.

- The panel gains **Artifacts** (`/glyphh artifacts`): the organisation's published pages as cards (title,
  description, the rrotor and version, roles, who published it and when, Open at the rrotor), a search field and
  Previous/Next over pages of 24; a reviewer sees Published, Awaiting review and Rejected, and approves, rejects
  (with a reason) or retires from the card. The server's refusals are shown in its words.
- `/glyphh publish <file> [--name n] [--title t] [--description d] [--roles a,b]`: the page Claude wrote (one
  `.html` or `.md` file) goes to the local rrotor (`POST /v1/apps`, the token from `~/.glyphh/rrotor/token`) as an
  app awaiting review; the reply says the version, who reviews it and the Open link. No rrotor, rrotor not running,
  or rrotor refusing is each said plainly.

- A new skill, `publish`: *"publish this to my org"* takes the page Claude made in the session (a Claude Code
  artifact, one `.html` or `.md` file), agrees its name, title, description and the roles that may open it,
  rewrites any claude.ai connector call into a function of the app (`program.py`, called by the page at
  `/apps/<name>/call/<function>` and run as the person viewing it) or leaves it out with a note, and publishes it
  with the rrotor's new `app_publish` tool as an app (`"kind": "app"`), awaiting review in the organisation's
  catalogue. It then says who reviews (the admin and the reviewer groups), gives the Open link, and offers
  `artifact_approve` when the person is a reviewer.
- The rrotor skill names the rrotor's `apps_list` and `app_publish`, `cli_login` (each person's CLIs signed in as
  themselves), and the Glyphh connector's `artifacts` (the organisation's apps as cards: search, Open, and for a
  reviewer Approve and Reject), `artifact_approve`, `artifact_reject` and `artifact_retire`; the sign-in skill, that
  `whoami` now answers `groups` and `reviewer`.
- Two example apps under `programs/`: `app_static` (a page with nothing behind it) and `app_dashboard` (a page with
  one function, roles and a declared host, with tests).

## 1.5.0 — 2026-10-31

rrotor, your local runtime, from Claude. Nothing of the Ada skills, the account panel or the ledger changes.

- A new skill, `rrotor`, installs and connects a local rrotor with `skills/rrotor/scripts/rrotor.sh`: it finds a
  container runtime (Apple's `container` on macOS 26 on Apple silicon, then OrbStack, then Docker), makes a local
  token once (`~/.glyphh/rrotor/token`, 0600, never printed; the container gets its SHA-256), pulls
  `ghcr.io/glyphh-ai/rrotor:0.1.0`, runs it as `glyphh-rrotor` on `127.0.0.1:7777` with the volume
  `glyphh-rrotor-data`, waits for it and checks the token. `connect` adds rrotor's `/mcp` to Claude Code (`claude
  mcp add --transport http --scope user rrotor http://127.0.0.1:7777/mcp --header "Authorization: Bearer $(cat
  ~/.glyphh/rrotor/token)"`); `status`, `start`, `stop`, `uninstall [--purge]`, and `deploy <folder> [commit]` (a
  program's folder as a git bundle). The skill then drives rrotor's tools: programs, runs, approvals (always the
  person's), secrets (never shown back), schedules and CLIs.
- A new skill, `rrotor-programs`: how to write a program (`glyphh.json`, `program.py`, its tests) and a CLI manifest
  (`"kind": "cli"`), from rrotor's examples.

## 1.4.0 — 2026-10-29

The glyphh command. A new skill, glyphh-cli, does the Ada skill's work through the shell with `glyphh` (the Python
SDK 3.5.0's command, `pip install glyphh`) when the connector's `ada_*` tools are not there, or when a file, a
script or many cases from a file suit a command better. It runs on an API key: the skill asks you to run
`glyphh login` and paste one yourself, never in the chat.

## 1.3.0 — 2026-10-28

Typed outputs and discriminated unions (Ada kernel 3.15.0, on `ada-1-2-beta`).

- The Ada skill writes a named output's `kind` when the case calls for one: `score` for ordered levels, `noul` for
  yes or no, `number` for an amount (`number: {min, max, step}`), `many` for several labels at once, `choice` (the
  default) otherwise. It uses `when: {output, in}` for a question that only applies on one branch of another (a
  discriminated union), so the branch not taken answers `applies: false` instead of a guess.
- It reads each kind's answer to you: a noul's `p`, a number's expected `value`, a score's expected `level`, a many
  output's list. These specs run on `ada-1-2-beta` only; the skill says so and offers a backtest first.
- `references/spec.md`: the kinds, `when`, and how they count against the cloud's limits.

## 1.2.0 — 2026-10-23

Ada versions (contract 5): the skill says which Ada version a model runs, offers a newer stable with a backtest
first (`ada_backtest` with `ada`, then `ada_upgrade` only when you agree, and how to roll back), explains betas and
warns of deprecations; the panel shows each model's Ada version.
