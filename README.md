# glyphh

The Glyphh mod for Claude Code: the Glyphh account. Sign in, the account,
org, plan and billing panels, and the licence every other Glyphh mod reads.
Every other mod depends on it.

## Commands

| Command | Does |
|---|---|
| `/glyphh [section]` | The Glyphh panel: Account, Org, Plan, Billing (signed out, each is Sign in). See [Glyphh account](#glyphh-account-glyphh) |
| `/glyphh signin`, `/glyphh signout` | Sign in by device flow (the code and link are also printed), or sign this machine out |
| *"sign in to Glyphh"* (ask Claude) | The sign-in card in the chat, from the mod's MCP server. See [The sign-in card](#the-sign-in-card-mcp-app) |

After the mod adds a command, the desktop window may need **View › Reload**
before it recognises it.

## Glyphh account (`/glyphh`)

`/glyphh` opens one panel with four sections; `/glyphh <section>` opens it on
one. Signed out, every section shows **Sign in**. Where Claude Code refuses
the name (a command or skill already has it), the command is `/glyphh-account`.

| Section | What it does (API in `server/docs/architecture.md`) |
|---|---|
| Sign in | Device flow: shows the code and the link; on the desktop opens `verification_uri_complete` in Claude's browser pane, in a terminal prints it; polls `/v1/device/token` at `interval`, 5 s slower on `slow_down`, until the token, `expired_token` or `access_denied`. Copy link, Cancel |
| Account | Name (Enter renames), email, sign-in providers, installs (revoke one; revoking this one signs out), Sign out |
| Org | Name (admin renames), members with roles (admin removes, never the admin), invites: send (the link is shown to copy), revoke, pending |
| Plan | The plan, its limits and what is used (`/v1/me`), the license this machine holds (valid, until, RPA on/off), every plan (`/v1/plans`) |
| Billing (admin) | Checkout (not subscribed) or switch plan (subscribed), seats, Card and invoices (Stripe's portal); Stripe's pages open in the browser pane, or as a link in a terminal |

Every action ends in one line under the tabs: what it did, or why not. A
refusal reads `{"error": {code, message, trace_id}}`; `E_LIMIT` names the
limit, what is used and the plan that lifts it. A 401 from
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
Code starts it with the plugin as `plugin:glyphh:glyphh`). Signed in
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

```bash
CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1 claude --plugin-dir ~/development/glyphh/glyphh
```

In the Claude desktop app, link the folder into the session's mods folder
(`~/.claude/dev-mods/<session id>/glyphh`) and accept *Enable hot reloading
for this session*. Edits then reload by themselves.

To let the mod open the sign-in page in the browser pane itself, allow the
two tools in `~/.claude/settings.json` (otherwise auto mode refuses the mod's
call and the mod asks Claude to open it, a turn slower):

```json
"permissions": {
  "allow": ["mcp__Claude_Browser__preview_start", "mcp__Claude_Browser__tabs_select"]
}
```

## Pieces

| File | What it is |
|---|---|
| `hooks/register.tsx` | The hooks module: registers the account |
| `hooks/glyphh/index.tsx` | Glyphh's hooks: `/glyphh`, its panel, the session start (`~/.glyphh`). The one file holding `$` and the account atoms; hands the rest a `Host` |
| `hooks/glyphh/host.ts` | The `Host` interface the account code works on (the engine's scan follows `$` only within the file that received it) |
| `hooks/glyphh/api.ts` | The API client: base URL, bearer, refusals, `E_LIMIT` |
| `hooks/glyphh/device.ts` · `account.ts` | Device-flow sign-in and polling · install.json, `/v1/me`, sign out, revoked installs |
| `hooks/glyphh/identities.ts` | The ways a person signs in (Google, GitHub): listed, linked, removed |
| `hooks/glyphh/license.ts` · `ed25519.ts` | The license: fetch, check, keep, gate · Ed25519 on BigInt |
| `hooks/glyphh/home.ts` | `~/.glyphh` paths and JSON files, the 0600 writer |
| `hooks/glyphh/actions.ts` | What the Account, Org, Plan and Billing sections do |
| `hooks/glyphh/panel.tsx` · `sections/*.tsx` · `ui.tsx` · `shape.ts` | The panel and its sections; elements and links; reading the server's answers |
| `hooks/glyphh/inline.tsx` | The sign-in drawn inline in the chat |
| `hooks/glyphh/command.ts` · `open.ts` · `openreq.ts` · `state.ts` | `/glyphh`; opening pages in the browser pane; the card's open requests; the panel's note |
| `hooks/glyphh/machine.ts` | The machine id: its sources, fallbacks and hash (also bundled into the MCP server) |
| `.mcp.json` · `mcp/src/server.ts` | The MCP server's declaration · the server: the tools and the card resource |
| `mcp/src/flow.ts` · `install.ts` | The card's device flow, no Node in it · install.json and the machine probe over Node |
| `mcp/card/sign-in.html` · `mcp-app.js` | The card · `@modelcontextprotocol/ext-apps` 2.0.3's bridge, vendored |
| `mcp/build.sh` · `dist/server.mjs` | The build · its output, committed |
| `skills/glyphh-sign-in/SKILL.md` | Tells Claude to call `glyphh_sign_in` when asked to sign in |
| `types/index.d.ts` | The account's types and the mod's `$.state` contract |
| `tests/glyphh-*.test.ts` | Tests on a fake server (`fake-server.ts`) and a fake host (`fake-host.ts`), no network: the client, the license, device-flow polling, limit errors, each section's actions, the machine id, the card's flow, and the panel through the engine on both surfaces |
| `mcp/test/install.test.mjs` | `node --test mcp/test`: install.json's mode and atomic write, the machine probe on this machine |

## Test

```bash
CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1 claude plugin test ~/development/glyphh/glyphh
claude plugin validate ~/development/glyphh/glyphh
node --test mcp/test
```

## What we learned

**`$` stays in its file.** The engine reads a module's source before it runs
it, and follows `$` only into functions declared in the file whose hook
received it: passing `$` to an imported function, or reading state through an
atom declared in another file or handed in as an argument, is refused at load.
`on` may be passed across files. So a mod split into modules keeps every `$`
call and atom in one file and hands the rest an interface of closures
(`hooks/glyphh/host.ts`).
