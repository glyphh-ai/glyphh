---
name: glyphh-think
description: Think with the glyphh kernel, an algebra of thought. Use this skill in every session — the memory is always on; whenever a problem calls for structured reasoning you want to compose and reuse — comparing plans or designs by structure, abstracting a concept from cases, spotting analogies, nesting one conclusion inside the next, or telling orderings apart; and whenever the user wants you to learn from outcomes, build precedent, or "always/never do X" for situations that recur — including before repeating any kind of decision you have made earlier in this workspace (how to run something, how to fix a recurring error, which approach worked). Also use it when the user asks how glyphh works or asks you to record, veto, or recall an operational lesson.
---

# glyphh-think

glyphh is an algebra of thought. A meaning is a glyph (a ±1 vector).
Five operations build glyphs from glyphs, and every operation returns
the type it takes, so anything you build can be taken apart, compared,
abstracted and built on again. Use it when prose reasoning would lose
structure: when you need a conclusion to be a value the next step can
use.

Read the embedded guidance once per session before using the kernel:
`python3 -c "from glyphh_kernel import spec; print(spec())"`.

## The algebra

```python
from glyphh_kernel import symbol as S, bind, bundle, roll, sim, Strand

def thought(**parts):          # a structure: roles bound to fillers
    return bundle([bind(S(role), filler) for role, filler in parts.items()])

migrate  = thought(goal=S("move_data"), risk=S("downtime"),   step=S("dual_write"))
backfill = thought(goal=S("move_data"), risk=S("lock_table"), step=S("batch_copy"))
```

- **Compare** — `sim(migrate, backfill)` ≈ 0.25: shared structure
  measures close, unrelated thoughts measure near 0.
- **Ask** — `sim(bind(migrate, S("risk")), S("downtime"))` ≈ 0.5:
  `bind` is self-inverse, so binding with a role reads it back.
  Compare the result against candidates; don't expect exact recovery.
- **Abstract** — `concept = bundle([migrate, backfill])` resembles
  every instance (≈ 0.6) and nothing else. Detail fades, gist
  survives; past a few dozen parts keep the sources if you need them.
- **Recurse** — a concept is a value: use it as a filler in a bigger
  thought and query it from inside. Signal halves roughly per level
  (≈ 0.5, then ≈ 0.28), so nest a few levels, not dozens.
- **Sequence** — `Strand([...]).state()` folds order in: the same
  thoughts in a different order measure ≈ 0.25 against each other.
  `roll(v, k)` marks position directly.

Discipline that makes it work:

- Roles and fillers are short canonical tokens. You are the semantic
  layer; the algebra is exact. Normalize wording before encoding.
- Encode only what should matter to the comparison. Incidental
  attributes (ids, paths, timestamps) make unrelated things look alike.
- Agents that share `(seed, dim)` share a vocabulary. Keep defaults
  unless you mean to isolate one.
- Precedent never overrides a proof: auth, money, and state-machine
  legality stay as ordinary code.

## Judgment: graded precedent

One thing you can build with the algebra is a learned judgment: a
`Space` records what a situation led to and whether it worked, then
answers for similar situations later. Your context window ends; the
files do not. The next session — yours or another agent's — inherits
graded results instead of prose. Composed thoughts can ride along as
`events=[...]`.

### Setup

There is one memory, the same in every session and every directory:
`$GLYPHH_HOME/ada`, else `~/.glyphh/ada` (`wins.db`, `vetoes.db`,
`aliases.json`). The session-start note names it. Never start a
parallel store.

Reach it through the plugin's `glyphh` MCP server — tools `query`,
`record`, `veto`, `check`, `status`. The server runs outside your
shell sandbox, so reads and writes work even where the memory
directory is not writable from Bash. It uses `min_sim=0.40, k=7`,
which suits small operational situations (2–3 attributes): "most
attributes shared." Pass your real agent name as `author` on writes —
receipts carry it, so teammates can see who grounded what.

Without the MCP server (another harness, or the server failed to
connect), open the stores with the kernel directly — writes then need
the memory directory to be writable:

```python
import os, sys
from pathlib import Path
sys.path.insert(0, "<kernel directory from the session-start note>")
from glyphh_kernel import Space
mem = Path(os.environ.get("GLYPHH_HOME") or Path.home() / ".glyphh") / "ada"
wins   = Space(author="<your-agent-name>", min_sim=0.40, k=7, path=str(mem / "wins.db"))
vetoes = Space(author="<your-agent-name>", min_sim=0.40, k=7, path=str(mem / "vetoes.db"))
```

### The loop

**Before** a decision of a kind you may have faced before — how to run
a long job, how to fix a recurring error, which approach the user
prefers — query first:

```
query  situation={"task": "long_background_run",
                  "constraint": "exceeds_tool_timeout"}
```

Act on `top` only when `act` is true — it means all three hold:
`sufficient`, `confidence >= 0.5`, and the nearest veto of that
outcome (`veto_match`) is below `support`. (Kernel equivalent:
`vetoes.matches(situation, a.top) < a.support`.) With `calibrated`
false (`count < 3`) treat the answer as a cited reminder, not a
settled rule: precedent of one is a note, not calibration. To vet an
approach you are considering rather than asking what worked, use
`check` with that `outcome`.

**After** the outcome is known — the command worked, the fix held, the
user accepted or corrected it — record it:

```
record  situation=... outcome="setsid_nohup_with_status_file" author=...  # worked
veto    situation=... outcome="run_in_background_tool"        author=...  # failed
```

Record at the moment of grading, not at session end. A directive from
the user ("always run checks before pushing") is a win recorded
immediately, graded by their authority.

### Encoding situations

Similarity tracks shared attribute pairs, so encoding discipline is
what makes recall precise:

- Keys and values are short canonical tokens: `{"task":
  "install_dep", "constraint": "debian_cryptography_conflict"}`.
  Normalize wording — you are the semantic layer; the store is exact.
- Include only attributes that should influence recall. Paths,
  timestamps, ticket numbers, and other incidentals make unrelated
  situations look alike; leave them out.
- Outcomes are action names, not sentences:
  `pin_less_than_2_and_purge_dist_packages`.
- Never store secrets, credentials, or personal data in situations or
  outcomes.

### What belongs where

- **wins** — approaches confirmed by outcome: a command pattern that
  worked, a fix that held, a user-stated rule.
- **vetoes** — approaches that failed or were refused: a denied
  command pattern, an approach the user rejected ("don't game it"), a
  tool that hit a hard limit.
- **Not precedent**: invariants (auth, safety rules) — those belong in
  code or CLAUDE.md; one-off facts that will never recur; anything
  you'd need to paraphrase a paragraph to encode.

### Aliases

The prompt hook's doorbell is lexical. When a concept has several
surface names, add them to `<memory>/aliases.json` so unsolicited
recall covers the paraphrases:

```json
{"angling": ["fishing"], "postgres": ["database", "db"]}
```

Add an alias whenever you notice a recall miss caused by wording —
that is the write-time semantic layer doing its job.

### Logging

The memory keeps a usage log (`LOG.md` beside the stores); append an
entry when memory materially entered a decision: the query, the
answer, what you did, and a verdict — helped / neutral / hindered /
memory-was-wrong. Log misses and wrong answers as prominently as
hits; the log's value is honesty about whether the memory earns its
keep.

### Persistence

The `.db` files are ordinary repo state. Commit them with related
work (use `git add -f` if `*.db` is gitignored). Other agents' rows
arrive via `refresh()` on a shared file or `merge(path)` for an
exchanged one; before merging a file you didn't write, spot-check its
receipts against reality.
