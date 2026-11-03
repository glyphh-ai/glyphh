# How a bot is built (read by the orchestrator's builder agent)

A bot is a folder holding four kinds of file. A program (the glyphh bot runner) controls it: it walks the loop, runs
the code steps, asks Ada at the gates, and calls the bot's Claude agent only for the steps that need judgment.

**The principle.** The bot's program holds the HARD gates (code and `limits`: never learned, never overridden) and
calls LEARNED gates (Ada models) for the judgment calls. A learned gate learns only from the person's answers, their
corrections and real outcomes, never from its own guesses. Claude never answers a gate or an approval for the person.

## Which gate for which job

| The job has | Use | In bot.json |
|---|---|---|
| A list to judge item by item (stories, emails, issues, leads, files) | a **per-item gate** | a `gate` step with `"each": "$step.items"` |
| One call on the whole run (is today worth a summary?) | a **gate** | a `gate` step, `on` mapping each outcome |
| Options of rising cost (models, strategies, effort) where a cheap one may do | a **ladder** | a `ladder` step: `try`, `check` |
| An outward action (sends, posts, pays, deletes) | an **approval**, learned with an **approval gate** | `"approval"` + `"approval_gate"` on the step |
| An outcome that only arrives later (did the lead convert, did the fix hold) | a **world-answered gate** | `"world": true` on the gate |
| A Claude answer the code reads | an **agent output gate** | `"schema"` (and `"check"`) on the agent step |
| Money, rate, time, size, "never more than N", "stop when nothing is new" | **hard gates, always** | `limits`, `requires`, `{"_end": why}` in code |

Never put a hard limit in a learned gate, and never let a gate's guess stand in for code. Every bot has `limits`.

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
      "question": "What the person is asked at this gate, in a few words",
      "ask_below": 0.75,
      "min_precedents": 10,
      "audit": 0.1,
      "max_questions": 10,
      "default": "b",
      "spec": {
        "name": "gate_name",
        "layers": [{"name": "l", "segments": [{"name": "s", "roles": [
          {"name": "a_number", "numeric_config": {"min_value": 0, "max_value": 100, "bin_width": 5}},
          {"name": "an_exact_value"},
          {"name": "some_text", "text_encoding": "bag_of_words"},
          {"name": "id", "key_part": true, "similarity_weight": 0}
        ]}]}],
        "output": {"costs": {"a": {"b": 2}, "b": {"a": 1}}, "ask_below": 0.75}
      }
    }
  },
  "loop": [
    {"id": "fetch", "run": "fetch"},
    {"id": "decide", "gate": "gate_name", "each": "$fetch.items", "label": "title", "key": "id",
     "on": {"empty:a": "end"}},
    {"id": "write", "agent": "The step's job for Claude, with $decide.a filled in", "skill": "skill-name",
     "remember": true},
    {"id": "deliver", "run": "deliver", "input": "$write", "requires": "len($decide.a) > 0"}
  ],
  "routine": {"cron": "M H * * *"},
  "limits": {"seconds": 300, "agent_turns": 3, "usd_per_run": 0.5, "usd_per_day": 2, "runs_per_day": 4,
             "quiet_hours": "22:00-07:00", "max_items": 30}
}
```

- `slug` is lower case letters, digits and `_`, at most 46 characters (its Ada models are named
  `bot-<slug>-gate-<gate>` and `bot-<slug>-<memory|instructions|personality>`, at most 63).
- `$id` is an earlier step's data, `$id.path` a part of it (`$fetch.items`, `$decide.a`, `$fetch.items.0.title`).
- Steps (exactly one kind each):
  - `run`: a program.py function `def name(ctx, inputs) -> dict|str` (`input` is what it gets). Answering
    `{"_end": "why"}` ends the run there: a hard gate, in code (nothing new, a rule broken).
  - `gate`: an Ada model that learns from the person's calls. Without `each`, `on` maps every outcome to the step it
    goes to (or `end`). With `each`, see per-item gates.
  - `agent`: Claude writes or judges; `skill` is how; `remember` keeps the answer in the bot's memory.
  - `ladder`: see ladders.
- Any step may carry `requires`: a plain expression over earlier data (comparisons `== != < <= > >=`, `and`, `or`,
  `not`, `len(...)`, numbers, strings, `true false null`, `$id.path`); when it does not hold, the step is skipped, or
  with `"otherwise": "end"` the run ends.

### Per-item gates: the gate for lists

`"each": "$fetch.items"` decides every item of that list. The gate's `case` function gets one item:
`def name(ctx, item) -> dict` (the run's data is `ctx.data`). Items Ada is sure of are decided at once; the unsure
ones are asked as ONE batch a run (one by one at a terminal; in a routine the run stops with the list, and the person
answers all of them with `glyphh bot continue <slug> 1=a 2=b rest=b`). Every answer is kept as a precedent. `label`
is the path to what the person is shown (`"title"`), `key` the path to the item's id. The step's data is a list per
outcome (`$decide.a`, `$decide.b`) plus `decisions` (each item's outcome, who decided: ada, person or default, and
P). `on` routes after the loop, its rules in order: `empty:<o>` (no item came out o), `any:<o>`, `all:<o>`, `else`;
no rule matching goes on to the next step. Outcomes may not be named decisions, asked, decided, defaulted, deferred,
dropped or items.

### Each gate's asking policy

On the gate, beside its spec: `ask_below` (ask under this probability; overrides the spec's), `min_precedents`
(answers it needs before Ada decides alone; 10 to 20 for a list), `audit` (a fraction of Ada's sure calls still
asked, to keep checking it; 0.05 to 0.1), `shadow` (true: Ada decides but the person is always asked, to measure
agreement before trusting it), `max_questions` (per run; the rest take `default`, or without one wait for the next
run), `default` (the outcome for what is not asked; never kept as a precedent). Set `max_questions` and `default`
on every per-item gate so a run never asks more than a person will answer.

### World-answered gates

`"world": true`: the outcome comes later from the world, not the person. Ada decides when sure; else the person's
call stands for now but is not kept. The case is kept; the real outcome is recorded with
`glyphh bot outcome <slug> <run> <gate> [item] <outcome>`, or from code with `ctx.gate(name).record_outcome(outcome,
item)`. A world gate has no audit or shadow.

### Ladders: the gate for cost

`{"id": "solve", "ladder": "route", "input": "$task", "try": "attempt", "check": "worked", "start": "mid",
"on_fail": "next"}` (or `"each": "$tasks.items"`): the gate's outcomes are the rungs, cheapest first. The gate picks
the cheapest it predicts will work (`start`, else the gate's `default`, else the cheapest, while it is unsure);
`def attempt(ctx, rung, item)` does it, `def worked(ctx, rung, result, item) -> bool` checks it, a failure goes one
rung up, and the rung that worked is recorded (a real outcome). `on_fail` when none did: `next` (carry on, `ok`
false), `end` or `fail`.

### Approvals: for outward actions

`approval` on a step that acts outward: the person says yes first. A step's own `touches` says how far it acts
(default the bot's); a bot that `touches` sends, pays or deletes must have an approval. The orchestrator's trust
decides who is asked: `ask_all` every approval, `ask_outward` the steps that send, pay or delete, `autonomous` none
but never a pay or a delete alone. `"approval_gate": "send_ok"` names a gate whose outcomes are `yes` and `no`,
learning the person's yes and no from its case (`def name(ctx, data)`): it stands in only when both it is sure and
trust allows; until then the person is asked, and every answer is kept.

### Agent output gates

`"schema": {...}` (JSON Schema: type, properties, required, additionalProperties, items, enum, const, minimum,
maximum, minLength, maxLength, minItems, maxItems, pattern, anyOf) makes the agent answer JSON that fits; `"check":
"fn"` is `def fn(ctx, answer, data)` answering True, or what is wrong. A wrong answer is sent back once with what
is wrong; wrong again, the run fails. The step's data is the JSON.

### Hard limits

`limits`: `seconds` and `agent_turns` (each agent step), `steps` (a run), `usd_per_run` and `usd_per_day` (from what
Claude reports for agent steps and what code reports with `ctx.spend(usd)`; a step that would pass one ends the run),
`runs_per_day`, `quiet_hours` (local; a routine run inside them is skipped), `max_items` (items a list gate takes).
A malformed limit is refused at load. `glyphh bot pause <slug>` stops a bot entirely until `resume`.

## program.py

Plain Python 3, standard library only. `ctx` gives: `ctx.http_json(url)` (GET JSON over https, only from `hosts`),
`ctx.db()` (the bot's own SQLite), `ctx.state(k)` / `ctx.set_state(k, v)`, `ctx.today` (a date), `ctx.run_id`,
`ctx.data` (the run's data so far), `ctx.dir` (the bot's folder, a Path), `ctx.gate(name)` (a gate, for code that
asks or records itself: `.decide(case)` answers a Call with `outcome`, `ask`, `p`, `sure`; `.record(case, outcome)`
keeps a precedent the code knows is true; `.record_outcome(outcome, item)`), `ctx.spend(usd)` and `ctx.budget()`,
`ctx.log(line)`. A case is `{"l": {"s": {...}}}` in the spec's shape; every role is numbers, exact values or text
the code computes from the data, numbers within the spec's min and max. Deliver by writing a file under
`ctx.dir / "out"` unless the job says otherwise; never send, post, pay or delete without an `approval` step.

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
