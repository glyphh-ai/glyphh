---
name: rrotor
description: Install, start and connect rrotor, the local Glyphh runtime that hosts the person's programs and CLIs in a container on their machine, and drive it from Claude Code (deploy, call, approvals, secrets, schedules, CLIs). Use when the person asks to install or set up rrotor or "the runtime", to run a program or a CLI locally in a sandbox, to schedule a program, or when rrotor's tools (programs_list, program_call, cli_run, ...) are missing or rrotor is not answering. Not for Ada: Ada models live in Ada Cloud (the ada skill).
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

`status` says whether the container runs and answers, and its version; `start` and `stop` do what they say;
`uninstall` removes the container and the MCP entry and keeps the volume; `uninstall --purge` also deletes the volume
(every program, run, schedule and secret) and the token: only when the person asks for exactly that.

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
| `clis_list`, `cli_run {cli, args, stdin?, files?}` | The CLIs; one command: exit code, stdout, stderr, or `needs_approval` |
| `audit_query` | The audit log (Enterprise) |

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
