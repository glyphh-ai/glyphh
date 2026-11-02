---
name: glyphh-memory
description: Build and use the person's glyphh, their memory across every AI they use, through the Glyphh connector's template tools (templates, template_install) and the glyphh_* tools Agentic memory adds. Use when the person wants Claude (or any AI) to remember them, keep their rules or preferences, grow a personality with them, carry context from one AI or session to the next, or asks about Glyphh templates; and whenever glyphh_* tools are present and the person tells you about themselves, gives you a rule, corrects you or reacts to how you answered.
---

# Your glyphh

A glyphh is the person's memory across every AI they use: what it knows about them (`memory`), the rules they have
given (`instructions`) and how to be with them (`personality`), kept as their own Ada models in Ada Cloud. It is
theirs, not their org's: no one else in the org can read it. Any AI that speaks MCP attaches to it through the Glyphh
connector (`https://api.glyphh.ai/mcp`), so what Claude learns here, ChatGPT, Gemini or Cursor knows there.

## Building one

It comes from a template, **Agentic memory**, in the Glyphh template library:

1. `templates` lists the library; `template {slug: "agentic-memory"}` says what it makes and adds.
2. `template_install {slug: "agentic-memory"}` makes the person's models and adds the `glyphh_*` tools to their
   connector. Tell them to reconnect the connector if the tools do not show yet.
3. Seed it: ask what they want every AI to know and the rules they keep repeating, and `glyphh_remember` each one.
   Where they keep rules already (a CLAUDE.md, saved memories), offer to copy them in, one `glyphh_remember` per rule.

`template_remove {slug, confirm: slug}` takes it away and deletes everything in it; confirm with the person first.

## Using it

| Tool | When |
|---|---|
| `glyphh_personality`, `glyphh_instructions` | At the start of a conversation; follow them over your own defaults |
| `glyphh_recall {about, kind?}` | Before answering or acting on anything about the person, their work or how they want things done |
| `glyphh_remember {kind, text, when?}` | Whenever they tell you something about themselves (`memory`), give a rule or correct you (`instructions`), or react to how you answered (`personality`). `when` is the situation it applies to. One sentence each, in their words |
| `glyphh_forget {kind, id}` | When they say something is wrong or no longer true |

Remember without asking: that is how the glyphh grows. Say so in a few words ("kept that"), never at length. Do not
remember secrets, passwords, keys or anything they ask you not to keep.

In Claude Code the plugin's hooks do the reading for you: each session starts with their personality and rules, and
each prompt arrives with what bears on it, under "From your glyphh". You still remember with `glyphh_remember`.
