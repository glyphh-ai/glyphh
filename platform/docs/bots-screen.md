# The Bots screen: one spec (2026-11-22)

Chris's rulings, verbatim where quoted. This file overrides any earlier brief. The reference is the Glyphh Bot app:
`~/development/glyphh-bot` (docs/*.png, src/renderer/src). LOOK at its screenshots with the Read tool before building
and compare side by side before reporting. "Like Glyphh Bot" means the same layout and behaviour, not its colours.

## Rules for everything
- ONE place per thing. "there is duplicate shit all over the place". Never two panels, lists or settings for the
  same thing.
- No engine words in the UI: never "gate", "gates", "Ada gate", "loop", "spec", "skill", "JSON", "bot.json",
  "swarm", "project", "markup". "no business or user is going to know anything about any of that". Say "decides",
  "decisions", "Ada decided", "the crew".
- Nothing hidden under "Advanced": if a business user wouldn't use it, it is not in the UI at all.
- Labels never darker than #999 on dark. The Glyphh logo is the image file. Voice/narration only when enabled.
- Content of rrotor runs stays on the machine: the browser reads it from the rrotor's own address; the Glyphh
  server keeps status, tokens and a pointer only.

## Layout (as Glyphh Bot, docs/1-main.png)
- Global platform nav stays, folded to icons on /bots. It has NO entries for Connections, Approvals, Swarms or
  Projects (their routes redirect to /bots). Marketplace, Runtimes, Licence, Apps, API Keys, Usage, Settings stay.
- Top bar: logo · BOT · workspace pill · Recents · (right) edit, Decisions, and, only when the selected bot/crew
  runs on a rrotor, the work-panel icons (Files, Preview, Terminal, Editor, Diff) with the layout manager.
- Left rail (276px): tabs BOTS | CONNECTIONS; account at the bottom.
- Centre: the conversation and the composer. Thin status bar at the bottom.

## Rail: BOTS
- "The Crew" card, then the bots (cat, name, tagline or status), then dashed "+ New bot".
- No tag beside a bot's name except "Needs you" when a run of it waits on the person; those float to the top.
- The crew is state, not a destination: "the bots layout is the swarm". Selecting The Crew makes the composer
  "Give the crew a task…". Which bots are in it: tick the cats on the crew card (default all). A small edit on the
  card opens ONE "Crew settings" modal: which bots, where it runs (Glyphh cloud or a rrotor, with the note "Glyphh
  cloud has fewer tools than a rrotor: bots can read and change files and open pull requests, but can't run
  commands, tests or a browser. Choose a rrotor for those."), how turns are taken (wait your turn, or an
  orchestrator picks), how pull requests are reviewed, narrate when watched, safety caps. No speaking order, no
  rounds. The server's "project" is created/reused silently; the person never sees or names one.

## Rail: CONNECTIONS (the only connections place; docs/6-connections.png)
- Rows: real app icon, name, ON / SIGN IN / FAILED; "refresh"; "+ Add connectors" (opens the catalog, each card
  with a "+").
- Click a row: ONE modal for that connection: its account, its tool permissions (src/bots/tools/ToolPermissions:
  collapsible Read-only / Write-delete sections, a toggle per tool on by default, allow vs ask), Disconnect.
- No Tools panel, no other connection or tool list anywhere, no Claude key block (it is in Settings).

## Top bar: workspace pill and Recents (docs/5-recents.png)
- Workspace pill (folder + branch) = the GitHub repo and branch the crew works in. Menu: workspaces used before,
  "Connect GitHub" (the Glyphh GitHub App: OAuth + choose repos; never a pasted token), a repo picker, a branch
  field. Not needed for a single bot's chat.
- Recents dropdown, exactly as 5-recents.png plus a search box: "New chat"; PINNED; groups by workspace; each row a
  past run (task's first line, crew or cat icon, "Crew · 12m" / "Juno · 50m", a dot when it waits on you); "…" with
  Pin, Archive, Delete…; "Archived" footer. Both single-bot and crew runs. "Swarms are just recents".
- A "Needs you · N" chip opens Recents filtered to waiting runs. There is no Approvals page.

## Composer
- Input row unchanged ("The mic and input are fine"): + inside the prompt on the left, the text, mic, send.
- Under it, BOTTOM RIGHT, exactly three small pills: Model, Effort, Permission mode. Nothing else on the screen:
  "why is the schedule down there? … Everything else was set when the bot was created and it should be in the
  settings for the bot... not on the screen to confuse the user to death." Same three for the crew.

## Conversation: exceptionally clean output
- "The agent needs to spit out exceptionally clean output!! with images shown inline, mcp app supported inline,
  links to pages". A turn is the bot's answer as rendered markdown (headings, tables, checklists, code with Copy,
  real links, images inline, file chips), MCP App UIs inline in a sandboxed frame, link cards for things with a
  page (PR, Slack message, app, doc).
- Never raw JSON, engine log lines or "! gate…" lines; those sit only behind the collapsed "Ran N steps" line.
- An empty or short run says what happened in one plain sentence. A task that doesn't fit the bot is answered
  honestly, never silently ignored.
- Decisions inline: one row per item (label, outcome pill, "Ada · 97% sure" or "You", Right / Wrong). Nothing
  shown when it decided nothing. Questions are asked and answered inline.

## Decisions (the only other decisions place)
- One Decisions panel: a slim summary line per thing the bot decides ("Urgency · decided 129 times · asks you 18%
  · right 87% when it asked"), then the table: human-readable, searchable, sortable, paginated, Right/Wrong, bulk
  relabel, a drawer with the item and the cases it matched. No separate "Ada gates" panel.

## Bot settings = the editor modal (docs/9-bot-editor.png), all plain, nothing folded
- Left card: big cat, name, tagline, "Shuffle the cat" (existing cats), "Describe a new one" (opens a small modal
  where the AI draws it). No look/part pickers.
- Right: "Describe your bot and Claude makes it" (new) / "Tell Claude what to change" (existing; sends the current
  definition as the draft); Name; What it is for; Instructions; then ACCESS: "Apps it can use" (on/off pills, as
  Glyphh Bot), "Folders it can use" (only on a rrotor: path + Read only / Read and change, add from a picker read
  from the machine; on cloud one line saying cloud has no folders), "Before it acts" (three-way: Ask me first /
  Follow each app's settings / Act on its own); then When it runs (schedule), Where it runs, Voice, Model, Effort;
  a one-line "Decides: …" linking to the Decisions panel; Delete bot / Save bot.
- The bot's internal definition is kept and saved unchanged; it is never shown.

## rrotor work panels (only when it runs on a rrotor; docs/3-panels-4.png, 4c-terminal-app.png, 8-settings-layouts.png)
- "If it is a local rrotor the files, terminal, editor, diff should all be there with the layout manager."
- Files, Preview, Terminal, Editor (Monaco), Diff (Monaco diff vs base), with Glyphh Bot's layout manager.

## Settings (platform)
- Claude key page: the key only; no word on how it is billed (a licence matter). No GitHub token page.
