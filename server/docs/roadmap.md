# Roadmap

What is decided but not built, in one place; `architecture.md` holds only what works today. Moved here on
2026-10-16 when the platform became the one door.

## To build

| Area | What |
|---|---|
| The platform's pages | To the design: Home, Keys, Approvals, Models, Billing, Org, Account, and the flow pages the server sends a browser to (architecture.md, The platform) |
| Routines as the runner | A Claude routine (schedule, API trigger, GitHub event) calling the runtime's MCP; a `needs_approval` with nobody watching waits for the person: the platform's Approvals page, Claude's band, an email |
| Approvals email | When no Claude and no platform page is open: a mail provider (`approvals.notified_at` stays empty until then) |
| The live panel | A run as it happens (steps, log, approvals) as an MCP App served by the runtime's own MCP |
| Hosted storage | `POST /v1/runtime/storage` (grow the volume); every GB is metered already at Fly's volume rate with the plan's markup |
| What Pro, Team and Enterprise are sold on | Precedent-store sync across instances (the licence's `sync`), background re-indexing, multi-node HA (`ha`), SSO/SAML, RBAC and audit logs (`sso`), an SLA: only the licence's flags ship ([pricing.md](pricing.md)) |
| Reconciling hosting | Each month, what was metered against Fly's invoice for the runtimes app; a gap means a rate row is out of date |
| Windows and Linux for the local runtime | WSL2 (rrotor ships as a WSL distribution) and Docker or Podman (rrotor's docs, section 11) |

## To prove

- **Fly's replay to a stopped machine:** `fly-replay: instance=` from the doorman to a machine that is stopped starts it and lands the request within a tool call's patience; `*.glyphh.app` as one wildcard certificate on the runtimes app.
- **Apple's `container`** running rrotor on macOS 26 (detected and started, not yet tested).
- **Dependencies through the marketplace**, and **a built mod loading** as its source does.

## To decide (Chris)

- The hosted machines each plan allows and the markups on Fly's rates (placeholders marked TBD in `db/seed.py`).
- The marketplace's home: the release builds write `glyphh-ai/glyphh`, which also holds the `glyphh` mod's source.
