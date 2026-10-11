# Build plan

Each phase is built in the house order: the database (drawn first), the API, the SDK, with MCP on the same operations, 100% test coverage, in Docker. A phase is done when its checks pass in CI and it works end to end.

## Phase 1: sign in from Claude and Codex

Day one supports two agent hosts: **Claude** (Claude Code, and Claude Desktop and claude.ai through the same connector) and **Codex**. A member adds Glyphh's MCP server, signs in with Google or GitHub, and the host is connected.

**Database**

- `sign_in_identities`: Google and GitHub accounts, found by the provider's own id.
- `oauth_clients`, `oauth_codes`: the agent hosts and their one-time codes (PKCE).
- `tokens.oauth_client_id`: the host a token was issued to.
- First sign-in with no invite creates the user and a new org on Free.

**Server**

- Sign-in pages: **Sign in** (Google or GitHub) and **Allow** ("Claude wants to use your Glyphh").
- Google and GitHub sign-in, with the callbacks.
- OAuth for MCP, as the MCP authorization spec asks: the protected-resource and authorization-server metadata, `authorize`, `token` (code with PKCE, refresh), client registration (dynamic, and client metadata documents), `revoke`.
- `/mcp` answers only with a valid token, and points an unsigned caller at the sign-in.
- API and MCP: `me` (who am I, my org), and the member's connected hosts (list, revoke).

**SDK and plugin**

- SDK (TypeScript and Python): `me`, connected hosts, token refresh.
- Claude: the plugin's MCP config pointing at `https://api.glyphh.ai/mcp`.
- Codex: the same server in Codex's config, signed in with `codex mcp login`.

**Checks**

- Sign in with Google and with GitHub, from Claude Code and from Codex; `me` answers as the member.
- A second sign-in finds the same person; a changed email does not break it.
- A revoked host stops at once; a code works once; an expired token refreshes.
- Every path tested, races included (two first sign-ins at once make one user).

**Needed before it can go live**

- A Google OAuth client and a GitHub OAuth app for Glyphh (their ids and secrets as server secrets).
- `api.glyphh.ai` pointed at the server, and the server deployed.

## Later phases

2. **Orgs and billing:** members, invites, plans, Stripe (subscriptions, seats, credit packs, auto top-up), the limits enforced by the database.
3. **Machines:** machine sign-in, one-click hosting (Fly first), machine tokens, Redis for live state, deploy status.
4. **rrotor:** the image, the app server and Glyphh's UI, the main assistant on its three loops, rrotor's MCP surface, launch tickets, the player.
5. **Powers and super powers:** the catalog, models on the member's keys, grants, slots, tool permissions, the editor and its configuration, voice.
6. **Connections:** Pipedream connect, the connection relay, credits and usage, teams and limits.
7. **Runs and schedules:** the server's clock, runs and their history, the browser and RPA.
8. **Machine to machine:** SSH through the relay, the gate, fence events.
9. **Discover:** dependencies and listings.
