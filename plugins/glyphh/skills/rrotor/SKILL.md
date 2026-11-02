---
name: rrotor
description: Install, update, start and connect rrotor, the local Glyphh runtime that hosts the person's programs, CLIs and apps in a container on their machine, and drive it from Claude Code (deploy, call, approvals, secrets, schedules, CLIs, publishing). Use when the person asks to install, set up or update rrotor or "the runtime", to run a program or a CLI locally in a sandbox, to schedule a program, or when rrotor's tools (programs_list, program_call, cli_run, app_publish, ...) are missing, some of them are missing (an older rrotor: update it), or rrotor is not answering. Not for Ada: Ada models live in Ada Cloud (the ada skill).
---

# rrotor, the local runtime

rrotor is a runtime the person installs on their own machine: one container (`ghcr.io/glyphh-ai/rrotor`), its API on
`127.0.0.1:7777` only, everything it keeps on one named volume. It hosts two things:

- **Programs**: a folder with a `glyphh.json` manifest and `program.py`, deployed by commit, run in a sandbox
  (bubblewrap, seccomp, Landlock, an egress proxy that allows only the hosts the manifest names), with a local
  secrets vault, cron schedules the runtime fires itself, a SQLite database (`ctx.db`) and approvals that wait for
  the person.
- **CLIs**: a kind of program (`"kind": "cli"`): a pinned command-line tool (gh, the glyphh command, a team's own)
  installed into the runtime and run one command at a time in the same sandbox.

How to write either is the `rrotor-programs` skill. Programs are not Ada models and rrotor runs no Ada: Ada is Ada
Cloud's (the `ada` skill). Glyphh's server only grants rrotor a licence; with none it runs as Community (one node),
and nothing a licence does refuses a run. Nothing of a run goes through Glyphh.

## Install and connect

Everything goes through `scripts/rrotor.sh` in this skill's folder (`${CLAUDE_SKILL_DIR}`; in the plugin,
`skills/rrotor/scripts/rrotor.sh`); every answer is one JSON line. Run it with Bash:

```sh
sh "${CLAUDE_SKILL_DIR}/scripts/rrotor.sh" install
```

It finds a container runtime (Apple's `container` on macOS 26 on Apple silicon, then OrbStack, then Docker; or
`--runtime container|orbstack|docker`), makes a local token once (kept 0600 in `~/.glyphh/rrotor/token`, never
printed: the container gets only its SHA-256), pulls `ghcr.io/glyphh-ai/rrotor:<the version this plugin pins>`,
and runs it as `glyphh-rrotor`, published on `127.0.0.1:7777` only, with the volume `glyphh-rrotor-data` at `/data`
and, under Docker or OrbStack, the security options rrotor's sandbox needs (`seccomp=unconfined`,
`systempaths=unconfined`, and `apparmor=unconfined` on Linux; a read-only root and a tmpfs `/tmp`). Then it waits
for rrotor to answer and checks its token. Running it again changes nothing that is right; a new token or image makes
the container again and keeps the volume. `--port N` moves the port; `--image IMAGE` runs a local build (`--image
pinned` goes back).

- `{"ok": false, "error": ...}`: say the error in one line. No container runtime: it names what to install; the
  person installs it, never you. A pull refused: the image may not be public yet (say so; `--image` takes a local
  build).
- `"sandbox_ready": false` or a `hint`: rrotor answers but refuses runs until the host is fixed; say the hint.

Then connect it to Claude Code, which adds rrotor's MCP server for the person (user scope), the token read from its
file:

```sh
sh "${CLAUDE_SKILL_DIR}/scripts/rrotor.sh" connect
```

That runs exactly:

```sh
claude mcp add --transport http --scope user rrotor http://127.0.0.1:7777/mcp \
  --header "Authorization: Bearer $(cat ~/.glyphh/rrotor/token)"
```

If `claude` is not on the PATH, give the person that line to run themselves (`mcp-command` prints it). Never print
the token or put it in the chat. Then ask them to restart Claude Code (or open `/mcp`) so rrotor's tools load.

**The link to Glyphh.** `connect` (and `start`) also link the rrotor to Glyphh when this machine is signed in
(`~/.glyphh/install.json`, from `/glyphh signin` or the sign-in card): the server issues the local runtime's token to
this sign-in (`POST /v1/runtime/local`), the script hands it to rrotor (`PUT /v1/runtime/token`, on loopback, never
printed) and waits up to twenty seconds for the link to come online; the answer's `link` is `linked`, `connecting`
(it will show once online), `skipped` (not signed in: say to run `/glyphh signin`, then `link`), or a stop state to
say plainly. `link` does only that, any time (asking again rotates the token). Linked, the rrotor shows on the
platform's Runtimes page, the apps published to it reach the organisation's catalogue (the `publish` skill), and
it gets the organisation's licence key; unlinked, it still runs everything locally. The mod does the same with
`/glyphh link` and the Account section's **link**.

`status` says whether the container runs and answers, its version, the release this plugin pins (`pinned`) and
whether the running one is behind it (`update_available`), the link's state (`online`, `no_token`, `connecting`, …)
and its runtime id; `start` and `stop` do what they say; `uninstall` removes the container and the MCP entry and
keeps the volume; `uninstall --purge` also deletes the volume (every program, run, schedule and secret) and the
token: only when the person asks for exactly that.

**Updating.** Each plugin release pins the rrotor release it was made against; a rrotor behind it lacks what the
newer plugin and skills expect (a rrotor before 0.2.0 has no `app_publish`, before 0.3.0 no React pages, documents,
diagrams or images, before 0.4.0 no sign-in from an app's page, no `run_as`, no `cli_login {shared}` and no `env`
for `ctx.cli`). When the person asks to update rrotor, when `status` says `update_available`, or when a tool
this skill names is missing from `mcp__rrotor__*` while others are there:

```sh
sh "${CLAUDE_SKILL_DIR}/scripts/rrotor.sh" update
```

It pulls the pinned release, makes the container again on the same volume, port and token (every program, run,
schedule, secret and app stays), drops any developer `--image` override, waits for it to answer and links it again.
The answer says `from` and `to`. Then say that Claude Code loads rrotor's tools again at `/mcp` or its next start:
the session that ran the update still holds the old tool list. The Account section of `/glyphh` shows the same:
"Update to <version>" beside this machine's rrotor, with **update** doing exactly this.

## Using it

Once connected, rrotor's tools are `mcp__rrotor__*`:

| Tool | Does |
|---|---|
| `programs_list` | Programs and CLIs, their versions, the active one, functions |
| `program_deploy {repo, commit, token?}` | A commit of a GitHub repo (`owner/name`, the full 40-character SHA) as the next version |
| `program_call {program, function?, inputs?}` | Opens a run; the first Result: `done` (data), `needs_input`, `needs_approval` (step, prompt), `failed` (step, reason) |
| `program_continue {run_id, answer}` | Answers a waiting run: `{"approved": true}` or `false` for an approval, the value for an input |
| `program_cancel`, `run_status`, `run_log` `{run_id}` | Stop a run; its state; its log |
| `approvals` | Runs waiting for the person |
| `secrets_list {program}`, `secret_set {program, name, value}`, `secret_delete` | A program's secrets: names back, never a value |
| `schedules_list`, `schedule_pause`, `schedule_resume` `{program, name}` | The schedules rrotor fires itself |
| `clis_list`, `cli_run {cli, args, stdin?, files?}` | The CLIs (each with `signed_in` for the caller and `shared_signed_in` for its shared HOME); one command: exit code, stdout, stderr, or `needs_approval` |
| `cli_login {cli, shared?}` | Signs a CLI in from the person's phone, into their own HOME on the rrotor (each signed-in person signs in as themselves). `shared: true` signs it in to the CLI's own shared HOME instead, for apps that run as the app, schedules and runtime keys: an admin's act (`E_FORBIDDEN` for a member; the local token may) |
| `apps_list {type?}` | The apps published to this rrotor: name, title, type, version, roles, `run_as`, review state, Open URL; `type` keeps one of page, dashboard, doc, diagram, deck, design |
| `app_publish {name, title, description, type?, roles?, run_as?, files, entry?, functions?, program?, ...}` | One file (a page, a document, a diagram, an image; a PDF or an image as `{"base64": …}`) as a new version of an app, awaiting review in the organisation's catalogue (the `publish` skill); `type` one of the six, else the entry's own (never `dashboard` or `deck`); `run_as` `viewer` (the default: its functions run as the person viewing it) or `app` (as the app itself, with its shared sign-ins and its vault) |
| `audit_query` | The audit log (Enterprise) |

The organisation's catalogue of apps is the Glyphh connector's (`https://api.glyphh.ai/mcp`): `apps {q?, page?,
state?, type?}` lists them as cards (search, a type filter, Open; a reviewer sees Awaiting review with Approve and
Reject), `app_approve`, `app_reject {reason}` and `app_retire` act on one by id; `whoami` says whether the person is
a reviewer (`reviewer`) and their groups.

**An app's sign-ins.** An app whose page calls functions runs them as the viewer (each person signs the app's CLIs
in once, from the page's sign-in card or with `cli_login`) or as the app (`run_as: app`: an admin signs each CLI
in once with `cli_login {cli, shared: true}`, or the app hands a declared secret to the CLI with `ctx.cli(...,
env=...)` and no one signs in; `secret_set` sets it). The catalogue's card says which and names a secret not yet
set. Choosing between them, the page's `rrotor.js` and the keys are the `publish` skill's.

- **A folder on this machine** deploys with the script (the MCP tool takes a GitHub repo): commit first, then
  `sh "${CLAUDE_SKILL_DIR}/scripts/rrotor.sh" deploy /abs/path/to/program` (HEAD, or a commit after
  the folder). It sends a git bundle of that commit; nothing else of the machine goes to rrotor.
- **Approvals are the person's.** On `needs_approval`, show them the `prompt` word for word and continue only with
  what they said. Never approve on your own, and never to get past a step. A waiting run expires after 15 minutes.
- **Secrets come from the person.** Ask them for a value only when a run fails `E_SECRET_MISSING` (it names the
  missing ones) or they offer it; set it with `secret_set` and never repeat it back, write it to a file or put it in
  a repo.
- **A CLI command** runs only if its arguments match the CLI's `allow` patterns (else `E_CLI_DENIED`: say which
  patterns it takes); one matching `approvals` waits for the person like a program's approval.
- A refusal is `{error: {code, message}}`: say the message. `E_AUTH`: the token in Claude's MCP entry is not
  rrotor's (run `connect` again). Not answering: `status`, then `start` or `install`.

From code, the SDKs have the same calls: `from glyphh import Runtime` (Python) or `import { Runtime } from
"@glyphh-ai/glyphh"`, which read the same token file.
