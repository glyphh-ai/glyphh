# glyphh

The Glyphh plugin for Claude Code, 1.1.5: your Ada Cloud account, the Ada skill and the file ledger. Ada Cloud is
Ada as an API that Glyphh runs: nothing to install or host.

```
/plugin marketplace add glyphh-ai/glyphh
/plugin install glyphh@glyphh
```

| Part | What |
|---|---|
| The account (a hooks module, `hooks/register.tsx`) | `/glyphh`: sign in, the account, org, plan and billing panel. Needs `CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1` (function hooks are early access in Claude Code 2.1) |
| The sign-in card (MCP server, `.mcp.json`) | Ask Claude *"sign in to Glyphh"* |
| Ada (a skill, [`skills/ada/SKILL.md`](skills/ada/SKILL.md), with `references/`) | Claude agrees a case with you, writes its spec, loads your history, backtests, tunes and asks Ada models in Ada Cloud, and makes an API key for your code, through the Glyphh connector's `ada_*` tools (`https://api.glyphh.ai/mcp`, added once in Claude's Connectors) |
| The file ledger (command hooks, `hooks/ledger.py`) | What Claude last changed in each file and why, handed back when it reads the file again |

The skill, the card and the ledger work without the variable.

## Commands

| Command | Does |
|---|---|
| `/glyphh [section]` | The panel: Sign in, Account, Org, Plan, Billing. Where another command or skill has the name, it is `/glyphh-account` |
| `/glyphh signin`, `/glyphh signout` | Sign in by device flow (the code and link are also printed); sign this device out |
| *"sign in to Glyphh"* | The sign-in card in the chat (the `glyphh-sign-in` skill) |

After the plugin adds a command, the desktop app may need **View › Reload** before it recognises it.

## The panel (`/glyphh`)

Signed out, every section shows **Sign in**. The API is the server's (`GLYPHH_SERVER_URL`, default
`https://api.glyphh.ai`); every call but the device flow's and `/v1/plans` carries `Authorization: Bearer <install
token>`.

| Section | Does |
|---|---|
| Sign in | `POST /v1/device/code {name, surface, mod_version, machine_id}`; shows the code and link (opened in the browser pane on the desktop, printed in a terminal); polls `POST /v1/device/token` at `interval`, 5 s slower on `slow_down`, until the token, `expired_token` or `access_denied`. Copy link, Cancel |
| Account | Name (Enter renames), email, sign-in providers (link, unlink), installs (revoke one; revoking this one signs out), Sign out |
| Org | Name (an admin renames), members and roles (an admin removes, never the admin), invites: send (the link to copy), revoke |
| Plan | The plan and the org's Ada Cloud use this month (`/v1/me`'s `cloud`): precedents held of the plan's, reads of the plan's, the reads past it (metered), and the day the count starts again; every plan by price with its precedents, reads a month and what reads past the month cost (`/v1/plans`'s `cloud`) |
| Billing (admin) | Stripe Checkout for Basic, Pro or Team without a subscription (`POST /v1/billing/checkout`), else a change of plan (`POST /v1/billing/plan`); **Talk to us** for Enterprise (`sales@glyphh.ai`, copied); card and invoices (`POST /v1/billing/portal`). Stripe opens in the browser pane, or as a link in a terminal |

The plans (members, installs and models unlimited on each; reads are decide, query, probabilities and facts calls,
counted by calendar month, UTC):

| Plan | Price | Precedents | Reads a month | Calls a second | Reads past the month |
|---|---|---|---|---|---|
| Free | $0 | 5,000 | 10,000 | 5 | Refused until the month turns |
| Basic | $20/month | 10,000 | 50,000 | 10 | $1 per 10,000 |
| Pro | $99/month | 100,000 | 1,000,000 | 50 | $1 per 10,000 |
| Team | $299/month | 1,000,000 | 5,000,000 | 200 | $1 per 10,000 |
| Enterprise | By contract | By contract | By contract | By contract | By contract |

Every action ends in one line under the tabs: what it did, or why not. A refusal is `{"error": {code, message,
trace_id}}`; `E_LIMIT` names the limit, the use and the plan that lifts it. A 401 means this install was revoked:
the device signs out.

**Device id.** Each device-code request carries `machine_id`, so a device signing in again reuses its install:
sha256(`"glyphh:" + value`) in hex, the value never sent. The value (`hooks/glyphh/machine.ts`, shared with the MCP
server): macOS's IOPlatformUUID, Linux's `/etc/machine-id`, Windows' MachineGuid (or `wmic csproduct get uuid`);
else the default route's MAC; else a random id kept in `~/.glyphh/machine.json`.

## The sign-in card

The `glyphh-sign-in` skill has Claude call `glyphh_sign_in` on the plugin's MCP server (`.mcp.json`: `node
${CLAUDE_PLUGIN_ROOT}/mcp/dist/server.mjs`, stdio). Signed in already, it says who. Otherwise it starts the device
flow and returns the card `ui://glyphh/sign-in/6` (`text/html;profile=mcp-app`, the ext-apps bridge inlined, no
network of its own): the code and **Sign in**, which asks the host to open the page. The card polls
`glyphh_sign_in_status` (app-only) every 3 s; the server polls `/v1/device/token` no faster than `interval`, writes
`~/.glyphh/install.json` and the card says *Signed in as …*, or that the code expired or was declined, with **Start
again**. Without cards, the tool's text has the code and link, and calling it again finishes once approved.

- Change the card: edit `mcp/card/sign-in.html` and bump the `ui://` address (hosts cache a card by it).
- Change the server: edit `mcp/src`, then run `mcp/build.sh` (type-checks and bundles into `mcp/dist/server.mjs`,
  committed, so the plugin needs only `node` 20 or later).

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
(cd plugins/glyphh && node --test mcp/test/*.test.*)
```

`tests/` runs on a fake server (`fake-server.ts`) and a fake host (`fake-host.ts`), no network: the client,
device-flow polling, limit errors, each section's actions, the plan's cloud caps and use, the device id, the card's flow and the panel
through the engine on both surfaces. `mcp/test` checks install.json's mode and atomic write and the device id's probe.

## Files

| File | What |
|---|---|
| `hooks/register.tsx` | The hooks module: registers the account |
| `hooks/glyphh/index.tsx` | `/glyphh`, its panel, the session start. The one file holding `$` and the account's atoms; hands the rest a `Host` (`host.ts`) |
| `hooks/glyphh/api.ts` | The API client: base URL, bearer, refusals, `E_LIMIT` |
| `hooks/glyphh/device.ts`, `account.ts`, `identities.ts` | Device-flow sign-in; install.json, `/v1/me`, sign-out, revoked installs; linked providers |
| `hooks/glyphh/home.ts`, `machine.ts` | `~/.glyphh` and the 0600 writer; the device id |
| `hooks/glyphh/actions.ts`, `panel.tsx`, `sections/`, `ui.tsx`, `shape.ts`, `inline.tsx` | What each section does; the panel and its sections; reading the server's answers; the inline sign-in |
| `hooks/glyphh/command.ts`, `open.ts`, `openreq.ts`, `state.ts` | `/glyphh`; opening pages in the browser pane; the card's open requests; the panel's note |
| `mcp/src/` | The MCP server: `server.ts` (the tools and the card), `flow.ts` (the device flow), `install.ts` (install.json, the device id's probe) |
| `mcp/card/` | `sign-in.html`, and `mcp-app.js`: `@modelcontextprotocol/ext-apps` 2.0.3's bridge, vendored |
| `skills/` | `ada/SKILL.md` (with `references/spec.md` and `references/tuning.md`), `glyphh-sign-in/SKILL.md` |
| `types/index.d.ts` | The account's types and the `$.state` contract |

**`$` stays in its file.** The engine reads a module's source before running it and follows `$` only into functions
declared in the file whose hook received it: passing `$` to an imported function, or reading state through an atom
from another file, is refused at load (`on` may cross files). So every `$` call and atom is in
`hooks/glyphh/index.tsx`, and the rest works on the `Host` interface.
