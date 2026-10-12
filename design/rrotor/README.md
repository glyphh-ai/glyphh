# rrotor's UI: the design, for the agent that builds it

rrotor's UI is the screen every Glyphh machine serves: you open a machine and watch its super powers work. It is a separate app from app.glyphh.ai (the platform), with its own look on the same brand. This folder is everything the build needs from the design. Pull `glyphh-ai/glyphh` before you start, and again before each screen: the design keeps moving.

## Read first

1. **This file**, all of it.
2. **`../DESIGN.md`**, the brand and the decisions. Read the brief, every section under Decisions, Brand assets, "How the build must be made" and the section headed "rrotor's UI is the business version". It holds the colours, type, cats, logo, buttons, lists, the rules for logos and icons, and the build rules (no inline styles, tokens only, small components). They apply here exactly as they do on the platform.
3. **The server's `docs/architecture.md`** (`glyphh-ai/server`). Read these sections: "rrotor is a Linux VM", "Platform and rrotor", "Browsers and RPA on rrotor", "Machine to machine", "Usage" (power_events), "Schedules and runs", "Access" (launch tickets) and "Each machine has its own address". Under Open, read Decisions and Design. It has the data behind every screen, and you never contradict it.

## What rrotor's UI is

- **Served by the machine:** a Next.js server inside rrotor, at the machine's own address `<machine-id>.glyphh.ai`, reached through Glyphh's relay. It opens in a browser tab, or from Claude.
- **Opened with a launch ticket:** one member, one machine, one page, valid for a minute and usable once. rrotor checks the ticket with the server and starts its own session. A member signs in on the server, never on a machine.
- **The business version:** no terminal anywhere. Work shows as **Activity** in plain words and as **Outputs**. Developers get their own terminal later, as a separate way in.
- **Its own app, one shared library:** rrotor's UI takes its tokens, fonts, cats, logo tiles, icons and every shared component from **`@glyphh-ai/ui`**, the package published from its own repo `glyphh-ai/ui` (decided by Chris, 2026-10-12; see "One component library" in `../DESIGN.md`). Pin a version. Never copy a component out of it. rrotor's own pieces (the rail, the stage, the drawer, the workbench tiles) live in rrotor. A piece both apps need that the library lacks is a request, added under Requests in `../DESIGN.md`, and it lands in the library, not in rrotor.

## The words

- **Glyphh:** the orchestrator. It is always first in the rail and always leads a crew.
- **Super power:** one agent with one job. It has inputs, outputs, where its work lands, schedules, and a voice. It is not a chat bot.
- **Crew:** the super powers working one thread together. **Glyphh always leads a crew**; there is no switch to turn it off. A super power can be in many crews and threads at once.
- **Thread:** one job being worked, either by a crew or by one super power on its own. Each thread has a goal, its crew, a status and its outputs.
- **Output:** what a job makes (a reel, a carousel, a document). rrotor hosts each output on the machine as an artifact with its own address. The caller (Glyphh, or the Claude that asked) gets it as the job's output, to open and to use.
- **Schedule:** how a crew's thread or a super power's job runs again: every Friday at 9:00, when a new video is posted, and so on.

## The screens

Boards are in `screens/` (the logos they use are in `screens/assets/`). How to read them is in `../screens/README.md`. In short: the markup is the layout, the script at the bottom holds every state, the copy is the copy to ship, and the inline styles are only how the canvas draws (never copy them).

A tall board is split into parts that share one script. `RrotorDesktop` to `RrotorDesktop4` are one board in four parts; read them in order.

| Board | What it is |
|---|---|
| `RrotorSplash`, `RrotorSplashLight` | The first screen on a machine. It names the machine before anything else (name, where it runs, its address, who is signed in) and lists start-up steps in plain words. Ten states: starting, opening, ready, on a laptop (Docker), waking, updating, a failed step, an expired link, someone else's machine, offline. |
| `RrotorDesktop` (1 of 4) | The shell: the **rail** (the machine; Glyphh; super powers with live status; you at the bottom), the **stage**, and the **drawer**. States: watching the crew; Glyphh's thread as the orchestration (a live row per super power, lit while it works); a super power's thread opened from it (Glyphh › Inbox Zero); the thread expanded over the stage with the rail collapsed; **voices** (the speaker forward with sound rings, turn order, live captions, the transcript's live turn); **your turn**. |
| `RrotorDesktop2` (2 of 4) | A super power picked: **Overview** (its job; In → Out → Lands in; schedules; recent jobs); a **long job** (the job pinned in the drawer, the work folded into blocks, Messages or Every step, Jump to latest; the **Workbench** with Outputs, a preview and **Activity**); an **output opened** as an artifact (play it, what made it, its version, **Get it**: its address, Send to Claude, Download, Copy link); a super power picked on the stage; the Workbench with its live browser and **Take control**; **someone needs you** (Allow once, Always allow, Deny); the drawer closed; the rail collapsed. |
| `RrotorDesktop3` (3 of 4) | **Recents** (the history button, top right): every thread, grouped Pinned, Today, Yesterday, Older; search; a filter by super power; each thread's menu (Pin to top, Open in the drawer, Archive). Also the rail's search and filters, and a **new thread**: the getting-started screen for a crew, and building the crew (+ on a rail row, drag a row in, Run once or on a schedule). |
| `RrotorDesktop4` (4 of 4) | A **new thread with one super power** (its inputs as the form, what it makes, where it lands, Run, Start); **Recents › Scheduled** (every schedule for crews and single super powers, and when each runs next); **the picker** (search across thousands of super powers, Recently used, results in pages). |
| `RrotorEdit` | **Edit a super power.** It is the platform's editor (`../screens/SuperPowerEdit`): the same screen, the same states, the same markup and script, placed in rrotor's layout. It has the rail on the left, and **Edit** beside Overview, Crew and Workbench in the header. The power map runs across the top; the form is on the left (identity: cat, voice, name; when to use it; the four sliders; the brief, with Write it with AI; Delete, Cancel, Save); Powers are on the right, by kind, with + Add a power. States: the editor, the avatar picker, the voice picker, Add a power (Custom powers, Super powers), can't save without a brief, saved, and Glyphh in the drawer editing with you (the rail collapses and the map fits the narrower centre). Build it from the **same components as the platform's editor**, from `@glyphh-ai/ui`, never a second version. It is generated from `SuperPowerEdit`, so when the platform's editor changes, this board changes with it. |

**Desktop only, dark only so far.** The light theme and phone layouts are still to draw. Build so that they drop in later: tokens for every colour, and layouts that collapse.

## The layout

- **Rail:** 272 px open, 72 px collapsed (remembered per person). From the top: the logo and the machine; the Glyphh card; Super powers with +, search and filter chips (All, Working, Needs you, Idle); the list (cat with a status dot, name, a live line, a pink You when it needs you); the account at the bottom. Clicking the account opens rrotor's Settings, which is not drawn yet.
- **The centre's views:**
  - **Crew:** Glyphh in its ring with this thread's crew around it, lines between whoever is working or talking, and the Now feed underneath.
  - **Workbench:** the layout manager. The picked super power's live surfaces as tiles: its browser, Activity, Outputs, a preview. Tiles resize by dragging the gaps, open full screen, and the layout is remembered per super power.
  - **Overview:** shown only when a super power is picked.
  - **A new thread:** the getting-started screen.
  - **An opened output:** the artifact view.
- **Header, right to left:** the drawer button, **Recents** (history), and pause.
- **Drawer:** 400 px, one thread at a time. It expands to cover the stage, and the rail collapses when it does.
- **Picking a super power** turns everything to it: the rail row, the stage (others fade), the drawer (its thread) and the view tabs (Overview appears).

## Motion

- The comet on Glyphh's ring.
- The blink.
- Lines that flow between agents (faster when they are talking).
- A pulse on live status.
- Sound rings and waveform bars while someone speaks.
- Spinners on steps that are running.

All of it stops for people who turn motion off.

## Icons

**Lucide**, approved by Chris (stroke 2, 20 px; 14–18 px in small places). Use only the names the boards use: server, sparkles, zap, store, chart-column, building-2, users, users-round, brain-circuit, plug, clipboard-check, key-round, scroll-text, credit-card, shield-check, building, layers, panel-left-close, panel-left-open, panel-right, menu, chevrons-up-down, chevron-right, chevron-down, user, life-buoy, sun, moon, monitor, log-out, mic, arrow-up, arrow-down, arrow-left, arrow-right, globe, layout-grid, orbit, pause, play, maximize-2, minimize-2, search, plus, ellipsis, check, loader, x, volume-2, hand, film, image, file-text, hash, download, link, send-horizontal, list-collapse, list-filter, grip-vertical, history, pin, archive, calendar-clock, repeat, folder-open. Ask Chris before adding any other icon, logo or asset.

## Still to come (don't invent these; ask, or wait for the boards)

- **The platform → machine handoff:** opening a machine from app.glyphh.ai or from Claude, the launch ticket, the splash, then the desktop. Its screens will be drawn here.
- rrotor's **Settings** (from the account), including **archived threads**: search, restore, delete for good.
- **Light theme** and **phone** for every board.
- The live browser up close (watching, take control, hand back), a run's history, and the layout manager's full rules (splits, presets).
- **What the data model doesn't hold yet:**
  - Outputs hosted on rrotor: their storage, their address, how a caller is let in, versions, how long they are kept.
  - A thread's record: where conversations live is still an open decision.
  - Grouping a run's steps into the blocks a long thread shows.

  These are listed under Open in the server's doc.

## Working with the design

The design agent draws these boards on the Glyphh Design canvas and exports them here. If a board and DESIGN.md disagree, DESIGN.md wins. If something isn't drawn, or a component the build needs has no look yet, add it under **Requests** in `../DESIGN.md`; never improvise a look.
