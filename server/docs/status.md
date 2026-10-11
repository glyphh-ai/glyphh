# Where we are

As of 2026-10-11. The rule: the data model is drawn first, then built in the order database, API, SDK, with MCP on the same service functions, 100% test coverage, everything in Docker.

## Built

- **Server** (`glyphh-ai/server`): Python, FastAPI, SQLAlchemy over asyncpg, Postgres 17. One schema applied at boot under an advisory lock (no migrations until relaunch). `GET /v1/health` and the stateless MCP endpoint at `/mcp`. CI runs ruff and the tests in Docker on every push and publishes the image on main.
- **Tables:** `plans` (seeded: Free, Solo, Basic, Pro, Enterprise, with their Stripe prices), `orgs` (Glyphh, the parent org, seeded), `users`, `tokens`.
- **SDKs** (`glyphh-ai/glyphh`): TypeScript and Python, generated from the server's OpenAPI spec, with health as the first call; both suites run in Docker against the server.
- **Not in Glyphh for now:** memory (a member adds it as a power if they want it) and Ada (later).
- **Docs:** this site (architecture, data model, this page).

The repos `glyphh-ai/app` and `glyphh-ai/platform` are no longer needed: the UI lives in rrotor, the sign-in pages in the server.

## Drawn, not built

On the [data model](data-model.md), in the order they were drawn:

- **Powers:** `powers` and one table per kind (`models`, `connections`, `folders`, `skills`, `tasks`, `plugins`, `loops`). Every power is one user's own, with a disabled mark for when a limit leaves it out.
- **Catalog:** `providers` (with logos) and `catalog_models` (name, description, type), the list rrotor's UI picks models from.
- **Super powers:** `super_powers` (one loop each; the member's Glyphh has everything), `grants` (folders, connections, models, skills, tasks, plugins, machines, other super powers), `slots` (a task's steps, each filled with a model), `tool_permissions` (allow, ask, deny per tool, with a super power's override for autonomous runs).
- **Teams and limits:** `teams`, `allowed_models`, `allowed_connections`, and the two limit switches on orgs and teams.
- **Schedules and runs:** `schedules` (the server's clock, sent to a machine) and `runs` (the history).
- **Billing and usage:** the plan's credit and machine columns, `subscriptions`, `credit_ledger`, `usage_events` (logged by the server's connection relay, one per call).
- **Browsers and hosting:** `browsers` (a browser profile on one full rrotor, granted like a folder), and one-click sign-ins on `machine_sign_ins` for new hosts.
- **Configuration:** a super power's full edit-screen configuration on `super_powers`, Glyphh's taken-away powers as denied grants, the member's settings (`user_settings`), org settings and auto top-up.
- **People and machines:** `invites`, `machines` (with where they run, their SSH key, fingerprint and shell switch), `machine_sign_ins`, `fence_events` (what rrotor reports when a run reaches past its fence), `api_keys`; folders are on a machine, and folder grants are read or write.
- **Signing in and Stripe:** `sign_in_identities` (Google and GitHub by the provider's own id), `oauth_clients` and `oauth_codes` (the plugin's sign-in), `launch_tickets` (open one machine's UI, once, for a minute), `stripe_events` (each webhook handled once).

On the [architecture](architecture.md): voice (speech in and out on the member's own models, streamed between the browser and rrotor), the main assistant, Glyphh, in rrotor on one of three loops (Claude Code or Codex on the member's subscription, or the Glyphh loop on their own key; none priced by Glyphh), orchestrating through rrotor's MCP, no desktop app and no platform (every rrotor serves Glyphh's UI, opened in Claude or any browser through the player; sign-in once on the server; four sign-in pages), tasks with Jev (a model on the member's key), dependencies and Discover, one full rrotor everywhere (a laptop is just another Docker host), Redis for live state (which process holds each machine, heartbeats, messages between processes), rrotor as a Linux VM (everything Glyphh runs is inside it, reached only by grants), usage and billing pages in rrotor's UI, adding a model in rrotor's UI, what rrotor carries (Postgres with pgvector, a Next.js server, the loop), and machine to machine over SSH through the relay.

## Open

Decisions still to make. Where a proposal is written, it is a proposal, not a decision.

- **Conversations:** not drawn. Proposal: the server keeps each conversation's record (title, super power, machine, run, status, times), rrotor keeps the messages, and rrotor's UI opens them through the player through the relay.
- **Codex hosting terms:** confirm OpenAI's terms for hosting Codex signed in with a member's ChatGPT subscription; Glyphh accepts Anthropic's Commercial Terms for Claude Code.
- **Super powers in Discover:** whether a super power becomes one more power type (`super_powers` folds into `powers`) or keeps its own table and is listed the same way.
- **Requirements and listings:** the tables for power dependencies and the Discover catalog, drawn when built.
- **The rrotor definition:** what a super power's definition holds (its workflows, pipelines and screens), how one super power's data is kept apart from another's in rrotor's Postgres, and how its screens are laid out inside Glyphh's UI.
- **Power bundles:** whether saving a skill or task keeps each version, and how edits made in a machine's folder get back to the server.
- **Plans:** price per credit and monthly credits per plan, included and extra machines for Solo, Basic and Pro, whether runs themselves spend credits, and whether Free is held to one connected service.
- **Usage detail:** how long each call's row is kept.
- **Teams:** whether a user can be in more than one (drawn as at most one).
- **Catalog descriptions:** the old list has no descriptions for its 3,900 models; they are to be written or imported.

## Next

Building the drawn tables when the word is given, with their limits enforced in the database and race tested; then the API (Google and GitHub sign-in, tokens, machine sign-in) and the SDK, in that order.
