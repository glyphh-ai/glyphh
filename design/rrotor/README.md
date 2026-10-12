# rrotor's views: the design, for the agent that builds them

rrotor's views are where you open a machine and watch its super powers work. **rrotor is headless** (Chris, 2026-10-12): the machine serves no UI; it streams every session to the server, and these views are **pages on app.glyphh.ai and live panels in Claude**, built in the platform (`glyphh-ai/platform`) on `@glyphh-ai/ui`. They keep their own look on the same brand. This folder is everything the build needs from the design. Pull `glyphh-ai/glyphh` before you start, and again before each screen: the design keeps moving.

## Read first

1. **This file**, all of it.
2. **`../DESIGN.md`**, the brand and the decisions. Read the brief, every section under Decisions, Brand assets, "How the build must be made" and the section headed "rrotor's UI is the business version". It holds the colours, type, cats, logo, buttons, lists, the rules for logos and icons, and the build rules (no inline styles, tokens only, small components). They apply here exactly as they do on the platform.
3. **The server's `docs/architecture.md`** (`glyphh-ai/server`). Read these sections: "rrotor is a Linux VM", "rrotor is headless: a machine that executes and streams", "The main assistant" (the loops), "Platform and rrotor", "Browsers and RPA on rrotor", "Machine to machine", "Usage" (power_events), "Schedules and runs", "Access" (launch tickets) and "Each machine has its own address". Under Open, read Decisions and Design. It has the data behind every screen, and you never contradict it.

## What rrotor's views are

- **Pages on the platform and panels in Claude, not served by the machine:** the machine streams each session (chat turns and steps in plain words, status, "needs you", a browser's screen) to the server, and the server passes it on to the page or panel watching. Opening a machine is the platform's (`MachineOpen` in `../screens/`): the card grows into the page and the splash plays in the centre. The member is already signed in on the platform; nobody signs in on a machine.
- **Needs you, wherever the member is:** when a super power needs an answer or a hand, the plugin's hook in Claude Code says "Glyphh needs you" and the Glyphh panel shows which super power and why; the member answers there or takes control of its browser.
- **A screen per browser, not a desktop** (the architecture, "rrotor is headless"): each super power's browser has its own screen, watched and taken over on its own. `MachineTakeover` draws a whole desktop; see Questions in `../DESIGN.md`.
- **The business version:** no terminal anywhere. Work shows as **Activity** in plain words and as **Outputs**. Developers get their own terminal later, as a separate way in.
- **One library, in the platform:** the views take their tokens, fonts, cats, logo tiles, icons and every component from **`@glyphh-ai/ui`**, in the platform repo (`ui/`; see "One component library, in the platform" in `../DESIGN.md`). The machine's own pieces (the rail, the stage, the drawer, the workbench tiles) are components there too. A piece the library lacks is a request, added under Requests in `../DESIGN.md`.

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
| `RrotorEdit`, `RrotorEdit2` | **Edit a super power.** It is the platform's editor (`../screens/SuperPowerEdit`): the same screen, the same states, the same markup and script, placed in rrotor's layout. It has the rail on the left, and **Edit** beside Overview, Crew and Workbench in the header. The power map runs across the top; the form is on the left (identity: cat, voice, name; when to use it; the four sliders; the brief, with Write it with AI; Delete, Cancel, Save); Powers are on the right, by kind, with + Add a power. States: the editor, the avatar picker, the voice picker, Add a power (Custom powers, Super powers), can't save without a brief, saved, and Glyphh in the drawer editing with you (the rail collapses and the map fits the narrower centre). Build it from the **same components as the platform's editor**, from `@glyphh-ai/ui`, never a second version. It is generated from `SuperPowerEdit`, so when the platform's editor changes, this board changes with it. **This machine's control** (`RrotorEdit2`): editing Glyphh shows one map of the whole machine, the platform's power map grown to hold everything. Glyphh is at the top; every super power is down the middle; every power is drawn once, as the platform's cards, on both sides (Connections and Folders on the left; Custom powers, Models and Browser on the right). Solid lines join each super power to every power it can use, so a power used by five super powers has five lines; dashed cyan lines show who hands work to whom. Chips filter by kind. It is touchable: pick a super power and its lines and cards light while the rest fade; pick a power and every super power using it lights, with its popover (who uses it, Permissions, Open it in Powers, Give it to another super power); drag a power onto a super power to give it (the target rings). **The canvas controls are app-old's flow canvas** (`app/src/renderer/skill-flow.tsx`): no dot grid; one stacked group in the top right with Zoom in, Zoom out and Fit the map; drag or scroll to pan, pinch or ⌘ scroll to zoom. Build it as one map component (the platform's) that takes any set of super powers, so a super power's own map and this one are the same component. |

**Voices are built behind a feature flag** (Chris, 2026-10-12): the round table, sound rings, captions, your turn and the mic stay in the design and ship when the flag is on; how voice streams is still being worked out. With the flag off, threads are text only and nothing else changes.

**Desktop only, dark only so far.** The light theme and phone layouts are still to draw. Build so that they drop in later: tokens for every colour, and layouts that collapse.

## The layout

- **Rail:** 256 px open, 72 px collapsed (remembered per person): the platform's rail, one component in both modes (decided by Chris, 2026-10-12). From the top: the logo (42 px, as the platform's rail) and, under it, the machine and its address; the Glyphh card; Super powers with +, search and filter chips (All, Working, Needs you, Idle); the list (cat with a status dot, name, a live line, a pink You when it needs you); the account at the bottom. Clicking the account opens rrotor's Settings, which is not drawn yet.
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

**Lucide**, approved by Chris (stroke 2, 20 px; 14–18 px in small places). Use only the names the boards use: server, sparkles, zap, store, chart-column, building-2, users, users-round, brain-circuit, plug, clipboard-check, key-round, scroll-text, credit-card, shield-check, building, layers, panel-left-close, panel-left-open, panel-right, menu, chevrons-up-down, chevron-right, chevron-down, minus and scan (the map's zoom out and fit, waiting for Chris's approval), user, life-buoy, sun, moon, monitor, log-out, mic, arrow-up, arrow-down, arrow-left, arrow-right, globe, layout-grid, orbit, pause, play, maximize-2, minimize-2, search, plus, ellipsis, check, loader, x, volume-2, hand, film, image, file-text, hash, download, link, send-horizontal, list-collapse, list-filter, grip-vertical, history, pin, archive, calendar-clock, repeat, folder-open. Ask Chris before adding any other icon, logo or asset.

## Still to come (don't invent these; ask, or wait for the boards)

- **The platform → machine handoff:** drawn as `MachineOpen` (in `../screens/`); opening a machine from Claude (a panel) is to draw.
- rrotor's **Settings** (from the account), including **archived threads**: search, restore, delete for good.
- **Light theme** and **phone** for every board.
- The live browser up close (watching, take control, hand back), a run's history, and the layout manager's full rules (splits, presets).
- **A thread's messages** live on the machine and its record on the server (decided 2026-10-12; "Where a thread's messages are" in `../DESIGN.md`): the states this brings (loading from the machine, an offline machine's thread, search with a machine offline) are on the design agent's list.
- **What the data model doesn't hold yet:**
  - Outputs hosted on rrotor: their storage, their address, how a caller is let in, versions, how long they are kept.
  - Grouping a run's steps into the blocks a long thread shows.

  These are listed under Open in the server's doc.

## Working with the design

The design agent draws these boards on the Glyphh Design canvas and exports them here. If a board and DESIGN.md disagree, DESIGN.md wins. If something isn't drawn, or a component the build needs has no look yet, add it under **Requests** in `../DESIGN.md`; never improvise a look.
