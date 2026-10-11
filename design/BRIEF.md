# Glyphh: brand and product design brief

For a Claude Design design-system project. Synced back into code with `/design-sync` (this folder).

## What Glyphh is

What if you could combine every AI super power into one? Glyphh does. A member's **super powers** are bots that run on their own machine (**rrotor**), always on, each with its own models, connections, folders and browser. **Glyphh** is the main assistant that orchestrates them. Members reach it all from Claude or ChatGPT through the Glyphh plugin, or from any browser. Under it: about 3,900 models across 125 providers on the member's own keys, and about 3,500 connections (Gmail, Slack, Salesforce, ...).

## The direction

**An ultra-modern AI startup.** Confident, precise, a little playful. A fresh direction for **fonts and colours**, carried through every surface so Glyphh feels like one brand everywhere.

**Keep:**

- **The Glyphh logo.**
- **The cat avatars:** the Glyphh cat and the super power faces (16 bodies). They are alive: **the blink**, the little **hop**, and the glowing **ring with its comet** from the current site. Every super power wears a cat, and its **mood** shows in its eye (thinking, working, done, stuck, ...). The artwork and the motion are in `brand/` (see `brand/README.md`).
- **The look and feel of the old desktop app**, reworked: it becomes rrotor's UI (below).

## Surfaces and screens

### 1. Marketing site (glyphh.ai)

The beta page today: the cat in its ring, the super powers orbiting into it, "What if you could combine every AI super power into one?", **Sign up for the beta** (email sales@glyphh.ai). Rebrand it, and give it room to grow into a full site.

### 2. app.glyphh.ai: the web front door

A very light web app: everything a person reaches directly in a browser. Glyphh has no other app for people: the real work happens in their AI (Claude, ChatGPT, Codex) or on their own machine's UI. Every page has its own address.

**Pages only a browser can show** (something sends the person here):

- **Sign in:** Continue with Google, Continue with GitHub.
- **Allow:** "Claude wants to use your Glyphh": allow or deny, for an AI host (Claude, ChatGPT, Codex).
- **Approve a code:** "Is this code on your new machine?", for a machine or a CLI signing in.
- **Join:** "You're invited to Acme", then sign in, then "You've joined Acme".
- **Return pages:** you're connected (go back to Claude), machine approved, checkout done ("You're on Pro") or cancelled, a service connected ("Gmail is connected").
- **Error:** what happened, what to do, and its **trace id**.

**The app itself** (signed in):

- **My machines (home):** each machine, online or not, where it runs; tap to open its UI.
- **Deploy a machine:** the one-click hosts (Fly, AWS, Azure, GCP, DigitalOcean, Hetzner, any VPS), then live status: waiting, registered, starting, ready.
- **Add Glyphh to your AI:** Claude, ChatGPT and Codex, each with its setup steps.
- **Account:** profile, plan and usage, Stripe's portal for payment details, connected AI hosts (disconnect one), sign out.
- **Opening a machine:** connecting, and "this machine is offline".

**States for every page:** loading, success, expired link, refused, error with its trace id.

### 3. rrotor's UI (the old app, reworked)

The app every machine serves, in the browser and inside Claude:

- **Home:** the machine, its super powers, what is running now.
- **Glyphh, the main assistant:** chat, with a **talk button** (voice), and the swarm's live status beside it.
- **Super powers rail:** each with its cat, name, status dot.
- **Super power editor:**
  - **identity row:** avatar, voice (with a sample to hear), name;
  - description and instructions;
  - **sliders:** personality (serious to playful), directness (gentle to blunt), temperament (kind to spicy);
  - effort, and its loop (Claude Code, Codex, or the Glyphh loop on a model);
  - its **powers map:** folders (read or write), connections, models, skills, browsers, other super powers;
  - tool permissions (allow, ask, deny), and schedules.
- **Runs:** history and the **live view**: steps, logs, the browser screen, **take control** to sign in to a website.
- **Connections catalog:** search 3,500 services, a native connect screen.
- **Models catalog:** provider logos, name, description, type; add a key.
- **Usage and billing:** credits used and left, usage by user, connection, super power and day; plan, seats, machines.
- **Org admin:** members, invites, teams, allowed models and connections.
- **Settings:** theme, notifications, voice.

### 4. Cards inside Claude and ChatGPT (through the plugin)

The same screens as app.glyphh.ai, built from the same components, as native-feeling cards in the chat, taking the host's light or dark theme. Only after sign-in: signing in itself is always a browser page.

- **My machines:** a list, online or not, tap to open.
- **Deploy a machine:** the steps, then live status (waiting, registered, starting, ready).
- **Usage and plan:** "what have I used this month?"
- **The swarm:** what is running, live.
- **Needs you:** a super power asking a question, or for permission.

## Must haves

- **Dark first, with a light theme.** Contrast at WCAG AA or better.
- **Phone, iPad and desktop.** Inside Claude's chat it adapts to the host's theme.
- **Motion with meaning:** the blink, the hop, the comet; everything still for people who turn motion off.
- **Tokens:** colour, type scale, spacing, radius, shadow, motion; for light and dark.
- **Components:**
  - buttons, inputs, selects, toggles, sliders, chips, status dots;
  - avatars (the cats), cards, tables, tabs, modals;
  - toasts (with a trace id), empty states, skeletons;
  - code and terminal blocks, provider logo tiles.
- **Voice:** plain, short, confident. Errors say what happened and what to do.

## Deliverables

1. Brand: logo usage, the cat set and its motion, the colour palette, the typefaces.
2. Tokens for light and dark.
3. The component library.
4. The screens above, starting with **app.glyphh.ai** (sign-in first), then **rrotor's UI**, then the **cards in the chat**.
