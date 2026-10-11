---
name: glyphh
description: Use when the member mentions Glyphh, their super powers, their machines (rrotor), or their Glyphh account, org or plan. Explains what Glyphh is and how to use its tools.
---

# Glyphh

Glyphh combines every AI super power into one. A member's **super powers** are bots that run on their own machine (**rrotor**), always on, each with its own models, connections, folders and browser. **Glyphh** is the main assistant that orchestrates them. Models run on the member's own keys or subscription; connections (Gmail, Slack and about 3,500 more) go through Glyphh.

## Signing in

The Glyphh tools work once the member has signed in. If a tool answers `E_UNAUTHORIZED`, tell the member to connect Glyphh (in Claude Code: `/mcp`, choose glyphh, Authenticate; in Codex: `codex mcp login glyphh`). Sign-in is Google or GitHub, then **Allow**. Never ask the member for a password, a key or a token in the chat.

## Tools today

- `me`: who the member is in Glyphh: their name, email, role, org and plan. Use it for "who am I", "what plan am I on", "which org".
- `health`: whether the Glyphh server is up and can reach its database. Use it when something seems broken.

More tools arrive as Glyphh grows: super powers, machines, runs, connections.

## When something fails

Every refusal carries a code (`E_INVALID`, `E_UNAUTHORIZED`, `E_FORBIDDEN`, `E_NOT_FOUND`, `E_CONFLICT`, `E_UNAVAILABLE`, `E_INTERNAL`) and a **trace id**. Tell the member what the message says and give them the trace id: it finds the exact request in Glyphh's logs. Don't retry an `E_INTERNAL` more than once.
