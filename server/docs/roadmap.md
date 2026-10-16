# Roadmap

What is decided but not built, in one place; `architecture.md` holds only what works today. Moved here on
2026-10-16 when the platform became the one door.

## To build

| Area | What |
|---|---|
| The platform's pages | To the design: Home, Keys, Approvals, Models, Billing, Org, Account, and the flow pages the server sends a browser to (architecture.md, The platform) |
| One OAuth for a runtime | rrotor's `/mcp` as an OAuth protected resource: `GET /.well-known/oauth-protected-resource` on the machine naming the server as its authorization server; the server issues tokens bound to `https://<machine>.glyphh.app/mcp` and answers `POST /v1/runtime/introspect` for the runtime (its own token as auth), cached a minute by rrotor. Then Claude's connectors UI adds a runtime with one Allow click and no key. Started in rrotor (`api/oauth.py`), not wired |
| Routines as the runner | A Claude routine (schedule, API trigger, GitHub event) calling the runtime's MCP; a `needs_approval` with nobody watching waits for the person: the platform's Approvals page, Claude's band, an email |
| Approvals email | When no Claude and no platform page is open: a mail provider (`approvals.notified_at` stays empty until then) |
| The live panel | A run as it happens (steps, log, approvals) as an MCP App served by the runtime's own MCP |
| Hosted storage | `POST /v1/runtime/storage` (grow the volume); storage billed at $0.50 per GB-month on the volume's size, prorated, with a cap the person sets |
| Hours beyond the plan | `GET /v1/hours` (balance and ledger), `POST /v1/hours/top-up` (Stripe Checkout), auto top-up and a spend cap on `PATCH /v1/org`; today a runtime past its hours is paused until the month turns |
| Solo plan | Its price and limits; not seeded until decided |
| Windows and Linux for the local runtime | WSL2 (rrotor ships as a WSL distribution) and Docker or Podman (rrotor's docs, section 11) |

## To prove

- **Fly's replay to a stopped machine:** `fly-replay: instance=` from the doorman to a machine that is stopped starts it and lands the request within a tool call's patience; `*.glyphh.app` as one wildcard certificate on the runtimes app.
- **Apple's `container`** running rrotor on macOS 26 (detected and started, not yet tested).
- **Dependencies through the marketplace**, and **a built mod loading** as its source does.

## To decide (Chris)

- Every add-on's price, per seat or flat (placeholders in `db/seed_addons.py`); Ada's limits are set (`models` 3 and `precedents` 10,000 on Free and Pro, unlimited on Team).
- The marketplace's home: the release builds write `glyphh-ai/glyphh`, which also holds the `glyphh` mod's source.
- What the hosted runtime costs Glyphh, for pricing: about $0.019 an hour running on 2 GB ($0.035 on 4 GB) and $0.15 per GB-month of volume, held or not.
