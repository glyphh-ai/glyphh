# The glyphh plugin's changelog

Newest first. The version is `.claude-plugin/plugin.json`'s and the marketplace's.

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
