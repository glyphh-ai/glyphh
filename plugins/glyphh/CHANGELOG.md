# The glyphh plugin's changelog

Newest first. The version is `.claude-plugin/plugin.json`'s and the marketplace's.

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
