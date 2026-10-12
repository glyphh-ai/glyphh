# Backlog

Everything open in one place: decisions still to make, things to draw, work found but not started. Where an item was first written elsewhere, that place now points here. When something starts, it moves to [status](status.md).

## Decisions

- **Billing: dollars or credits**, and the monthly spend cap (a limit on auto top-ups, or none). Billing (phase 2b) waits on both.
- **Plans:** price per credit and monthly credits per plan, pack sizes and prices, included and extra machines for Solo, Basic and Pro, whether runs themselves spend credits, whether Free is held to one connected service. The billing boards leave these as `[BRACKETS]`.
- **Tasks are powers:** rename tasks to powers everywhere (proposed, not confirmed).
- **"Also use my Claude or ChatGPT connectors":** a switch per super power, letting its loop use the member's own connectors beside Glyphh's (proposed, not decided).
- **Navigation:** where Powers lives. The boards put Super powers, Powers and Marketplace in the top nav.
- **Conversations:** where they live. Proposal: the server keeps each conversation's record (title, super power, machine, run, status, times), rrotor keeps the messages, and rrotor's UI opens them through the relay.
- **Status page:** a hosted service (Better Stack, Instatus, OpenStatus) or our own on Cloudflare; never on Fly, so it stays up when we're down. The sign-in screens already link to `status.glyphh.ai`.
- **Codex hosting terms:** confirm OpenAI's terms for hosting Codex signed in with a member's ChatGPT subscription; Glyphh accepts Anthropic's Commercial Terms for Claude Code.
- **Super powers in Discover:** one more power type (`super_powers` folds into `powers`), or its own table listed the same way.
- **Usage detail:** how long each call's row is kept.
- **Teams:** whether a user can be in more than one (drawn as at most one).
- **Old prod:** stopped on Fly, not destroyed (database and Redis kept); when to cut over or drop it.

## To draw

- **Many orgs per person** (decided 2026-10-11): everyone has a Personal org plus any orgs they join; a memberships table (person × org × role); the host picks the org at Allow ("Use with"); tokens carry the chosen org; seats count memberships; an invite adds a membership instead of moving the person.
- **The rrotor definition:** what a super power's definition holds (its workflows, pipelines and screens), how one super power's data is kept apart from another's in rrotor's Postgres, and how its screens are laid out inside Glyphh's UI.
- **Requirements and listings:** the tables for power dependencies and the Discover catalog.
- **Power bundles:** whether saving a skill or task keeps each version, and how edits made in a machine's folder get back to the server.

## To build

- **Sign-in screens on the design** (in progress): tokens, Red Hat, the ported cat, the trace id alert, logo tiles, the theme toggle, the brand orbit, then the sign-in frame and the four flows.
- **Allow, after the answer:** "You're connected / Back to Claude" and "Claude wasn't connected"; today the server returns straight to the host.
- **Join while signed in:** accept or decline (the board's default state), the inviter and the expiry on the invite, "You're in" with the org's machines.
- **Approve a code:** the machine and CLI sign-in (enter the code, confirm the machine, approved with its start-up steps), server and screens.
- **Connections through Glyphh's MCP:** the member's connected accounts served as tools to any host through Pipedream; connecting by a card's button, the link in the answer, and URL elicitation where the host supports it. The tested pieces are on the server's `card-test` branch.
- **Catalog descriptions:** the old list has none for its 3,900 models; write or import them.

## Deploy

- **The server** runs only on the Mac behind ngrok; nothing is deployed.
- **The platform on Fly:** its app, `app.glyphh.ai` pointing at it, and `GLYPHH_PLATFORM_URL` set on the server.
- **Codex** is added but not signed in: run `codex mcp login glyphh` on the Mac.

## Design

- **The design agent's requests** (`glyphh-ai/glyphh`, `design/collaboration.md`): Pagination, SegmentedControl, a themed Stripe Payment Element, ConnectFrame, a bars-by-day chart, Menu radio items, DescriptionList, a person and an org avatar.
- **Requests still to write:** the power map and the editable flow canvas (React Flow) for the editors.
- **Perplexity's logo** is on the sign-in board's models ring but not in `design/screens/assets`; the ring shows six models until it's added.
- **`/design-sync` goes from code to design:** it uploads `@glyphh-ai/ui` into a Claude Design project so the design agent draws with the real components. `collaboration.md` says it brings the design back; correct it. It needs `/design-login` run once from an interactive session on the Mac.
- **The ui README** says rrotor's UI uses the library; rrotor gets a UI of its own.
