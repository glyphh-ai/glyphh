# Where we are

As of 2026-10-11. The rule: the data model is drawn first, then built in the order database, API, SDK, with MCP on the same service functions, 100% test coverage, everything in Docker.

## Built

- **Server** (`glyphh-ai/server`): Python, FastAPI, SQLAlchemy over asyncpg, Postgres 17. One schema applied at boot under an advisory lock (no migrations until relaunch). `GET /v1/health` and the stateless MCP endpoint at `/mcp`. CI runs ruff and the tests in Docker on every push and publishes the image on main.
- **Tables:** `plans` (seeded: Free, Solo, Basic, Pro, Enterprise, with their Stripe prices), `orgs` (Glyphh, the parent org, seeded), `users`, `tokens`.
- **SDKs** (`glyphh-ai/glyphh`): TypeScript and Python, generated from the server's OpenAPI spec, with health as the first call; both suites run in Docker against the server.
- **Docs:** this site (architecture, data model, this page).

## Drawn, not built

On the [data model](data-model.md), in the order they were drawn:

- **Powers:** `powers` and one table per kind (`models`, `connections`, `folders`, `skills`, `tasks`, `plugins`, `loops`). Every power is one user's own, with a disabled mark for when a limit leaves it out.
- **Catalog:** `providers` (with logos) and `catalog_models` (name, description, type), the list the app picks models from.
- **Super powers:** `super_powers` (one loop each; the member's Glyphh has everything), `grants` (folders, connections, models, skills, tasks, plugins, machines, other super powers), `slots` (a task's steps, each filled with a model), `tool_permissions` (allow, ask, deny per tool, with a super power's override for autonomous runs).
- **Teams and limits:** `teams`, `allowed_models`, `allowed_connections`, and the two limit switches on orgs and teams.
- **Schedules and runs:** `schedules` (the server's clock, sent to a machine) and `runs` (the history).
- **Billing and usage:** the plan's credit and machine columns, `subscriptions`, `credit_ledger`, `usage_events` (logged by the server's connection relay, one per call).
- **Browsers and hosting:** `browsers` (a browser profile on one full rrotor, granted like a folder), and one-click sign-ins on `machine_sign_ins` for new hosts.
- **People and machines:** `invites`, `machines` (with their edition, SSH key, fingerprint and shell switch), `machine_sign_ins`, `machine_connections` (which server process holds each machine), `fence_events` (what rrotor reports when a run reaches past its fence), `api_keys`; folders are on a machine, and folder grants are read or write.
- **Signing in and Stripe:** `sign_in_identities` (Google and GitHub by the provider's own id), `oauth_clients` and `oauth_codes` (the plugin's sign-in), `key_links` (the platform's one-time key links), `stripe_events` (each webhook handled once).

On the [architecture](architecture.md): rrotor as a Linux VM (the app you drive unsandboxed, remote control only through rrotor by grants), the platform's usage and billing pages, adding a model in the app, what rrotor carries (Postgres with pgvector, a Next.js server, the loop), and machine to machine over SSH through the relay.

## Open

Decisions still to make. Where a proposal is written, it is a proposal, not a decision.

- **Conversations:** not drawn. Proposal: the server keeps each conversation's record (title, super power, machine, run, status, times), rrotor keeps the messages, and the app and web open them over SSH through the relay.
- **Where the org admin's pages live:** members, teams, and the allowed models and connections, in the app or on the platform.
- **Redis for live state:** proposed (which process holds each machine, heartbeats, control messages), replacing the `machine_connections` table; not yet agreed.
- **RPA on a desktop:** the full rrotor has the virtual screen and Chromium; whether the desktop's lite rrotor gets them too, or desktop RPA stays in the app's own browser.
- **App settings** (workspaces, tabs, layout, appearance): not drawn; on hold.
- **The rrotor definition:** what a super power's definition holds (its workflows, pipelines and screens), how one super power's data is kept apart from another's in rrotor's Postgres, and how its screens reach the app and the web from a remote machine.
- **Power bundles:** whether saving a skill or task keeps each version, and how edits made in a machine's folder get back to the server.
- **Plans:** price per credit and monthly credits per plan, included and extra machines for Solo, Basic and Pro, whether runs themselves spend credits, and whether Free is held to one connected service.
- **Usage detail:** how long each call's row is kept.
- **Teams:** whether a user can be in more than one (drawn as at most one).
- **Catalog descriptions:** the old list has no descriptions for its 3,900 models; they are to be written or imported.
- **Platform stack:** a very small web app in `glyphh-ai/platform`, stack not chosen.

## Next

Building the drawn tables when the word is given, with their limits enforced in the database and race tested; then the API (Google and GitHub sign-in, tokens, machine sign-in) and the SDK, in that order.
