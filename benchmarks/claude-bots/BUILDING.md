# How a bot is built (read by the orchestrator's builder agent)

A bot is a folder holding four files. A program (`botrun`) controls it: it walks the loop, runs the code steps,
asks Ada at the gates, and calls the bot's Claude agent only for the steps that need judgment.

## bot.json

```json
{
  "slug": "snake_case_name",
  "name": "Human name",
  "summary": "One sentence: what it does, when",
  "version": 1,
  "agent": "agent.md",
  "reads_glyphh": true,
  "touches": "read_only | drafts | sends | pays | deletes   (the most outward thing it does)",
  "hosts": ["only.the.https.hosts.its.code.reaches"],
  "seed": {"personality": ["..."], "instructions": ["..."], "memory": []},
  "gates": {
    "gate_name": {
      "case": "the program.py function that builds the gate's case",
      "outcomes": ["a", "b"],
      "spec": {
        "name": "gate_name",
        "layers": [{"name": "l", "segments": [{"name": "s", "roles": [
          {"name": "a_number", "numeric_config": {"min_value": 0, "max_value": 100, "bin_width": 5}},
          {"name": "an_exact_value"},
          {"name": "some_text", "text_encoding": "bag_of_words"},
          {"name": "run", "key_part": true, "similarity_weight": 0}
        ]}]}],
        "output": {"costs": {"a": {"b": 2}, "b": {"a": 1}}, "ask_below": 0.7}
      }
    }
  },
  "loop": [
    {"id": "fetch", "run": "fetch"},
    {"id": "decide", "gate": "gate_name", "on": {"a": "write", "b": "end"}},
    {"id": "write", "agent": "The step's job for Claude, with $fetch filled in", "skill": "skill-name", "remember": true},
    {"id": "deliver", "run": "deliver", "input": "$write", "approval": "deliver"}
  ],
  "routine": {"cron": "M H * * *"},
  "limits": {"seconds": 300, "agent_turns": 3}
}
```

- Steps: `run` (a program.py function `def name(ctx, inputs) -> dict|str`), `gate` (an Ada model that learns from the
  person's calls; `on` maps each outcome to the step it goes to, or `end`), `agent` (Claude writes or judges; `$id`
  is an earlier step's data). `approval` on a step that acts outward (sends, posts, pays, deletes): the person says yes
  first until the orchestrator trusts the bot.
- A gate's `case` function is `def name(ctx, data) -> dict` returning the case in the spec's shape
  (`{"l": {"s": {"a_number": 3, "an_exact_value": "x", "some_text": "...", "run": ctx.run_id}}}`). Every role is
  numbers, exact values or text the code computes from the run's data; numbers within the spec's min and max.
- Gates go where a person's judgment decides the run: is this worth doing, which way, is it safe. A bot has one to
  three gates. Each gate's outcomes are the choices the person would make; costs say which mistake is worse.

## program.py

Plain Python 3, standard library only. `ctx` gives: `ctx.http_json(url)` (GET JSON, only from `hosts`), `ctx.db()`
(the bot's own SQLite), `ctx.state(k)` / `ctx.set_state(k, v)`, `ctx.today` (a date), `ctx.run_id`, `ctx.dir` (the
bot's folder, a Path), `ctx.log(line)`. Deliver by writing a file under `ctx.dir / "out"` unless the job says
otherwise; never send, post, pay or delete without an `approval` step.

## agent.md

```
---
name: kebab-case-name
description: One line
tools: []
model: sonnet
---

Who the bot is and its job, in a few sentences. A program runs it and asks it only for its steps; it answers only
what the step asks, nothing before or after.
```

## skills/<name>/SKILL.md

How the agent does one kind of step: format, length, what to lead with. Frontmatter `name` and `description`.
