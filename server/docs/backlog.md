# Backlog

Work that is decided or found but not started, newest first. When something starts, it moves to [status](status.md).

## Platform and sign-in

- **Status page at status.glyphh.ai.** The sign-in screens already link to it (Status in the header, "Check Glyphh status" on errors). It must live outside Fly so it stays up when we're down: a hosted service (Better Stack, Instatus, OpenStatus) checking the API, the platform and `/mcp` every minute, or our own on Cloudflare. Not chosen yet.
- **Many orgs per person** (decided 2026-10-11). Everyone has a Personal org plus any orgs they join: a memberships table (person × org × role), the host picks the org at Allow ("Use with"), tokens carry the chosen org, seats count memberships, and an invite adds a membership instead of moving the person. Draw it in the data model first.
- **Allow, after the answer:** the board shows "You're connected / Back to Claude" and "Claude wasn't connected"; today the server returns straight to the host.
- **Join while signed in:** accept or decline an invite (the board's default state), the inviter's name and the expiry on the invite, "You're in" with the org's machines.
- **Approve a code:** the machine and CLI sign-in (enter the code, confirm the machine, approved with its start-up steps). Server and screens.
- **Perplexity's logo** is on the sign-in board's models ring but not in `design/screens/assets`; the ring shows six models until it is added.

## Design

- **The design agent's requests** in `glyphh-ai/glyphh` `design/collaboration.md`: Pagination, SegmentedControl, a themed Stripe Payment Element, ConnectFrame, a bars-by-day chart, Menu radio items, DescriptionList, a person and an org avatar.
- **`/design-sync` goes from code to design:** it uploads `@glyphh-ai/ui` into a Claude Design project so the design agent draws with the real components. `collaboration.md` says it brings the design back; that needs correcting. It needs `/design-login` run once from an interactive session on the Mac.

## Connections

- **Connections through Glyphh's MCP:** the member's connected accounts served as tools to any host, through Pipedream; connecting by a card's button, the link in the answer, and URL elicitation where the host supports it. The tested pieces are on the server's `card-test` branch.

## Billing

- **Dollars or credits**, and the monthly spend cap (a limit on auto top-ups, or none). Billing (phase 2b) waits on both.

## Hosts

- **Codex** is added but not signed in: run `codex mcp login glyphh` on the Mac.
