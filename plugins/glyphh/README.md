# glyphh

The Glyphh plugin for Claude Code, 2.0.0 (release notes: [CHANGELOG.md](CHANGELOG.md)): Ada. Your Ada Cloud account,
the Ada skill, the glyphh command, and the file ledger. Ada Cloud is Ada as an API that Glyphh runs: nothing to
install or host. It speaks contract 5 of Ada Cloud (Ada versions); a server that speaks a newer one is said plainly
in the panel and by the skill, with how to update the plugin.

```
/plugin marketplace add glyphh-ai/glyphh
/plugin install glyphh@glyphh
```

| Part | What |
|---|---|
| The account (a hooks module, `hooks/register.tsx`) | `/glyphh`: sign in, the account, org, plan and billing panel. Needs `CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1` (function hooks are early access in Claude Code 2.1) |
| Sign-in from the chat (a skill, [`skills/glyphh-sign-in/SKILL.md`](skills/glyphh-sign-in/SKILL.md)) | Ask Claude *"sign in to Glyphh"*: Claude calls the account mod's `glyphh_login` |
| Ada (a skill, [`skills/ada/SKILL.md`](skills/ada/SKILL.md), with `references/`) | Claude agrees a case with you, writes its spec, loads your history, backtests, tunes and asks Ada models in Ada Cloud, and makes an API key for your code, through the Glyphh connector's `ada_*` tools (`https://api.glyphh.ai/mcp`, which the plugin adds as `glyphh-cloud` in `.mcp.json`; you sign in to it once by OAuth, and a Glyphh connector you already added stands in for it). It says which Ada version a model runs, offers a newer stable with a backtest first (`ada_backtest` with `ada`, then `ada_upgrade` only when you agree, and how to roll back), explains betas, and warns of deprecations |
| The glyphh command (a skill, [`skills/glyphh-cli/SKILL.md`](skills/glyphh-cli/SKILL.md)) | The same Ada work through the shell: `glyphh` from `pip install glyphh`, JSON out, on an API key (`glyphh login` keeps one for the machine, or `GLYPHH_API_KEY`) |
| The file ledger (command hooks, `hooks/ledger.py`) | What Claude last changed in each file and why, handed back when it reads the file again |

The skills and the ledger work without the variable; without it, sign-in from the chat points you to `/mcp` and the
`glyphh-cloud` connector.

Other plugins and skills for Claude are at [github.com/glyphh-ai/plugins](https://github.com/glyphh-ai/plugins).

## Commands

| Command | Does |
|---|---|
| `/glyphh [section]` | The panel: Sign in, Account, Org, Plan, Billing. Where another command or skill has the name, it is `/glyphh-account` |
| `/glyphh signin`, `/glyphh signout` | Sign in by device flow (the code and link are also printed); sign this device out |
| *"sign in to Glyphh"* | The same sign-in from the chat (the `glyphh-sign-in` skill and the mod's `glyphh_login` tool) |

After the plugin adds a command, the desktop app may need **View › Reload** before it recognises it.

## The panel (`/glyphh`)

Signed out, every section shows **Sign in**. The API is the server's (`GLYPHH_SERVER_URL`, default
`https://api.glyphh.ai`); every call but the device flow's and `/v1/plans` carries `Authorization: Bearer <install
token>`. Every section is drawn from one kit (`hooks/glyphh/ui.tsx`) in Claude's own type scale and theme colours:
a title with one line under it, groups under small labels, rows (the thing, a dim line under it, its actions at the
right), fields whose labels line up, chips for a kind or a state, one quiet line for an empty list, the panel's last
word in a bordered note, and tabs as text with the open one in Claude's colour; the terminal gets the same shapes on
one line each.

| Section | Does |
|---|---|
| Sign in | `POST /v1/device/code {name, surface, mod_version, machine_id}`; shows the code and link (opened in the browser pane on the desktop, printed in a terminal); polls `POST /v1/device/token` at `interval`, 5 s slower on `slow_down`, until the token, `expired_token` or `access_denied`. Copy link, Cancel |
| Account | Name (Enter renames), email, sign-in providers (link, unlink), installs (revoke one; revoking this one signs out), Sign out |
| Org | Name (an admin renames), members and roles (an admin removes, never the admin), invites: send (the link to copy), revoke |
| Plan | The plan and the org's Ada Cloud use this month (`/v1/me`'s `cloud`): precedents held of the plan's, reads of the plan's, the reads past it (metered), and the day the count starts again; the org's models by Ada version (`cloud.ada`, the shape of the Ada host's `GET /v1/ada`): the latest stable, each version's status (a beta labelled, a deprecated one with its end date) and models, and for a deprecated one what happens on that date and what to do; a newer contract than the plugin's 5 is one line saying to update it; every plan by price with its precedents, reads a month and what reads past the month cost (`/v1/plans`'s `cloud`) |
| Billing (admin) | Stripe Checkout for Basic, Pro or Team without a subscription (`POST /v1/billing/checkout`), else a change of plan (`POST /v1/billing/plan`); **Talk to us** for Enterprise (`sales@glyphh.ai`, copied); card and invoices (`POST /v1/billing/portal`). Stripe opens in the browser pane, or as a link in a terminal |

The plans (members, installs and models unlimited on each; reads are decide, query, probabilities and facts calls,
counted by calendar month, UTC):

| Plan | Price | Precedents | Reads a month | Calls a second | Reads past the month |
|---|---|---|---|---|---|
| Free | $0 | 1,000 | 5,000 | 5 | Refused until the month turns |
| Basic | $20/month | 10,000 | 50,000 | 10 | $1 per 10,000 |
| Pro | $99/month | 100,000 | 1,000,000 | 50 | $1 per 10,000 |
| Team | $299/month | 1,000,000 | 5,000,000 | 200 | $1 per 10,000 |
| Enterprise | By contract | By contract | By contract | By contract | By contract |

Every action ends in one line under the tabs: what it did, or why not. A refusal is `{"error": {code, message,
trace_id}}`; `E_LIMIT` names the limit, the use and the plan that lifts it. A 401 means this install was revoked:
the device signs out.

**Device id.** Each device-code request carries `machine_id`, so a device signing in again reuses its install:
sha256(`"glyphh:" + value`) in hex, the value never sent. The value (`hooks/glyphh/machine.ts`): macOS's IOPlatformUUID, Linux's `/etc/machine-id`, Windows' MachineGuid (or `wmic csproduct get uuid`);
else the default route's MAC; else a random id kept in `~/.glyphh/machine.json`.

## Signing in from the chat

The `glyphh-sign-in` skill has Claude call `glyphh_login`, a tool the account's mod registers and answers itself
(nothing runs on its own). Signed in already, it answers `signed_in` with the email. Otherwise it starts the same
device flow as `/glyphh signin`, opens the approval page in the browser pane, shows the code in the chat and answers
`pending` with the code and link; the mod polls `/v1/device/token` and says when it is signed in. The plugin ships no
local MCP server.

## The file ledger

`~/.glyphh/ledger/ledger.sqlite` (`GLYPHH_HOME` moves `~/.glyphh`), Python's standard library, nothing sent
anywhere. Three command hooks in `hooks/hooks.json`, beside the account's module:

| Hook | Does |
|---|---|
| `PostToolUse` on Edit, Write, MultiEdit (`ledger.py record`) | Records each change with the request it served |
| `PostToolUse` on Read (`ledger.py recall`) | Hands back the file's last three changes as context |
| `UserPromptSubmit` (`ledger.py prompt`) | Lists the files this session changed in its last three turns |

It needs `python3`. Why the last touch of each file: [`benchmarks/session`](../../benchmarks/session) (180 real sessions)
found that is what a turn needs from earlier turns; recency recovers a third to a half of it, a search by the
request a seventh.

## `~/.glyphh`

| File | What |
|---|---|
| `install.json` | `{install_id, token}`, mode 0600, written to a temporary file under `umask 077` and moved into place; the token never on a command line or in a log |
| `machine.json` | `{id}`, the device id, only where no hardware id or MAC can be read |
| `ledger/ledger.sqlite` | The file ledger |

Signing out removes `install.json` (and a `license.json` an older plugin left).

## What it does on your computer

**Where it sends things.** The mod talks to one host, `https://api.glyphh.ai` (`GLYPHH_SERVER_URL` changes it, for
development). Nothing else leaves the machine.

| When | What is sent to `api.glyphh.ai` |
|---|---|
| Signing in (`/v1/device/code`, `/v1/device/token`) | The computer's short host name, the surface (desktop or terminal), the plugin's version and `machine_id`, a sha256 hash of this machine's id; the id itself never leaves |
| Using the panel | Your install's token, and the account, org, member and billing requests you make there |

**What it reads to identify the machine.** `machine_id` keys installs by machine, so one computer counts once. It comes
from the hardware id (`ioreg` on macOS, `/etc/machine-id` or `/var/lib/dbus/machine-id` on Linux, the `MachineGuid`
registry value or `wmic csproduct` on Windows), else the primary network interface's MAC, else a random id kept in
`~/.glyphh/machine.json`. Only the hash is sent.

**What it runs.** The mod runs these programs, each with fixed commands, and no others:

| Program | Why |
|---|---|
| `hostname -s` | The name your install shows in your account |
| `/usr/sbin/ioreg`, `reg query`, `wmic csproduct get uuid`, `getmac`, and a fixed `/bin/sh` script calling `route`, `ip` and `ifconfig` | The machine id above |
| `/bin/sh` with a fixed script of `umask`, `mkdir`, `cat`, `chmod` and `mv` | Writes `install.json` with mode 0600; the token goes on stdin, never on a command line |
| `/bin/rm -f` | Removes `install.json` when you sign out |
| `osascript` | On the desktop, clicks View > Show Browser in Claude so the sign-in page can be seen; without Accessibility permission nothing happens |

The command hooks run `python3` on `hooks/ledger.py`. The plugin ships no local MCP server and no built or bundled
code: every file is the readable source that runs. `.mcp.json` names one server, `glyphh-cloud`, the remote Glyphh
connector at `https://api.glyphh.ai/mcp`, which runs nothing on your computer: what you ask of it goes to that
address once you have signed in to it by OAuth.

**What it writes.** Only under `~/.glyphh`: the files above and two small logs, `open-log.txt` (whether a page opened)
and `ask-log.txt` (a prompt that could not be submitted). It edits no build, start-up, settings or instructions file.
It reads its own `plugin.json` for its version.

**What it asks of Claude.** The mod calls one tool itself, `preview_start` on Claude's browser pane, to open the Glyphh
sign-in page. If that is refused it submits one prompt asking Claude to open that page in the pane; the prompt holds
that instruction and the page's address, nothing else.

**How it touches tool calls.** The mod registers one tool, `glyphh_login`, and answers it itself: it starts the sign-in
and returns its state; it sees no other tool call. The ledger's `PostToolUse` hooks read
Edit, Write, MultiEdit and Read calls and keep what they record on your computer.

## Run it locally

```bash
CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1 claude --plugin-dir plugins/glyphh
```

In the Claude desktop app, link the folder into the session's mods folder (`~/.claude/dev-mods/<session id>/glyphh`)
and accept *Enable hot reloading for this session*.

To let the plugin open the sign-in page in the browser pane itself, allow two tools in `~/.claude/settings.json`;
otherwise it asks Claude to open it, a turn slower:

```json
"permissions": {
  "allow": ["mcp__Claude_Browser__preview_start", "mcp__Claude_Browser__tabs_select"]
}
```

## Test

```bash
CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1 claude plugin validate --strict plugins/glyphh
CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1 claude plugin test plugins/glyphh
```

`tests/` runs on a fake server (`fake-server.ts`) and a fake host (`fake-host.ts`), no network: the client,
device-flow polling, limit errors, each section's actions, the plan's cloud caps and use, the device id and the panel
through the engine on both surfaces.

## Files

| File | What |
|---|---|
| `hooks/register.tsx` | The hooks module: registers the account |
| `hooks/glyphh/index.tsx` | `/glyphh`, its panel, the session start. The one file holding `$` and the account's atoms; hands the rest a `Host` (`host.ts`) |
| `hooks/glyphh/api.ts` | The API client: base URL, bearer, refusals, `E_LIMIT` |
| `hooks/glyphh/device.ts`, `account.ts`, `identities.ts` | Device-flow sign-in; install.json, `/v1/me`, sign-out, revoked installs; linked providers |
| `hooks/glyphh/home.ts`, `machine.ts` | `~/.glyphh` and the 0600 writer; the device id |
| `hooks/glyphh/actions.ts`, `panel.tsx`, `sections/`, `ui.tsx`, `shape.ts`, `ada.ts`, `inline.tsx` | What each section does; the panel and its sections; reading the server's answers; the Ada versions' lines; the inline sign-in |
| `hooks/glyphh/command.ts`, `open.ts`, `state.ts` | `/glyphh`; opening pages in the browser pane; the panel's note |
| `hooks/ledger.py` | The file ledger's command hooks |
| `skills/` | `ada/SKILL.md` (with `references/spec.md` and `references/tuning.md`), `glyphh-sign-in/SKILL.md`, `glyphh-cli/SKILL.md` |
| `types/index.d.ts` | The account's types and the `$.state` contract |

**`$` stays in its file.** The engine reads a module's source before running it and follows `$` only into functions
declared in the file whose hook received it: passing `$` to an imported function, or reading state through an atom
from another file, is refused at load (`on` may cross files). So every `$` call and atom is in
`hooks/glyphh/index.tsx`, and the rest works on the `Host` interface.
