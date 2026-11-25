# Micro gates

Can many micro Ada gates working together reason where one model can't, and can they teach an agent something it
can't learn alone?

**The first half held. The second did not.** Chained gates, learning from the ends of chains alone, answered what one
Ada model could not. An LLM alone, with no gates and no code, answered every question it was given, including the
world where the gates scored zero.

| Moves shown directly | Length 3 | 5 | 8 | 12 | 16 |
| --- | --- | --- | --- | --- | --- |
| **50%**: gates with credit | 96.2% | 94.9% | 90.4% | 88.0% | 84.4% |
| 50%: one Ada model | 8.0% | 9.5% | 10.0% | 9.8% | 10.3% |
| 50%: gates, no credit | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| 50%: most common end | 9.9% | 9.1% | 8.8% | 10.2% | 8.9% |
| **25%**: gates with credit | 68.3% | 59.5% | 52.9% | 49.2% | 45.6% |
| **10%**: gates with credit | 8.8% | 7.5% | 8.0% | 7.6% | 6.3% |
| **0%**: gates with credit | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |

Chance is 10%. Mean of five hidden worlds, 200 chains a length, a refused answer counted wrong. `results/table.txt` has
every row.

The LLM, on the same 50 questions of world 1 (10 a length), one run each:

| Moves shown directly | Gates with credit | LLM, reasoning only | LLM, writing its own code |
| --- | --- | --- | --- |
| 50% | 48 of 50 | 50 of 50 | 50 of 50 |
| 0% | 0 of 50 | 50 of 50 | 50 of 50 |

## The test

A hidden machine: 10 states, 6 actions, each action a shuffle of the states, every name made up (`world.py`). A
precedent is a start, 2 or 3 actions and where it ended, never the states between; 5% of ends are recorded wrong. Some
share of single moves also have a precedent of their own. Every test chain is unseen, uses at least one move never
shown directly, and runs up to 16 actions, five times longer than any precedent.

The gates (`gates.py`) are one small Ada model per action on the real kernel. One gate's answer is the next gate's
question. A chain with one step unknown has every state tried in that hole, the later gates carry each try forward, and
the try that lands on the graded end is recorded. Chains answered rightly back their steps; chains answered wrongly
take a precedent from their weakest step.

## What this leaves out

- **The gates do not learn how to learn.** The credit rule is about thirty lines of hand-written Python. The gates
  hold what was learned; the method of reasoning is ours, not theirs.
- **The rule needs a foothold.** It only fills one hole at a time, so with few moves shown it credits wrong answers
  (10% shown: 77% of moves wrong) or never starts (0% shown).
- **The task is a lookup once learned.** Every state is an exact symbol, so Ada's similarity does no work here; only its
  probabilities, which outvote the noise.
- **No gates were spawned.** The set of gates is fixed at one per action.
- **The LLM sample is small:** one world, 50 questions, one run per contestant, on a task that suits it. Its tool
  calls were audited: the reasoning-only runs read the prompt and nothing else, and the code runs fitted the machine by
  annealing inside their own folders. The gates needed about a second of CPU and no LLM; the LLM runs took 33 to 98
  seconds and about 60,000 to 70,000 tokens each.
- Seed 0 was used while building, and a change came from it (chains answered rightly back their steps). Seeds 1 to 5
  ran once after that. The other settings were never tuned.

## Across sessions

`sessions.py`: ten sessions on one unseen world, 120 new chains and 20 questions each, with two actions changing their
rules at session 6, unannounced. Every Claude call is a fresh process with no tools. One world, one run.

| Agent | Right | Sessions 6 to 10 | Tokens | Cost |
| --- | --- | --- | --- | --- |
| Claude alone, starting cold | 199 of 200 | 100 of 100 | 132,559 | $2.35 |
| Claude with its own notes | 200 of 200 | 100 of 100 | 100,059 | $1.59 |
| Gates, Claude on what they refuse | 170 of 200 | 70 of 100 | 85,672 | $1.50 |

**The gates lost.** Before the change they took Claude out of two sessions entirely and got 100 of 100. After it they
did not recover in this world, refusing 9 to 15 of 20 questions a session and getting 30 wrong; on the build world
(seed 0, gates alone) they recovered by session 10, so one good world proved nothing. Claude's notes, a plain table of
about 3,000 characters, spotted the change by themselves and rewrote it.

**The test was also too easy for memory to matter.** 120 chains a session show nearly the whole machine, so the cold
agent lost one question in 200 with nothing carried over. A test of memory needs sessions too thin to solve alone.

The token counts here, about 10,000 a call, are the honest price of solving this world. The 60,000 to 70,000 above
came from subagents, which carry their own overhead.

That run is kept as `results/sessions_seed7_120.*`.

## Thin sessions, and the beam

The same test on a new unseen world (seed 11) with 30 chains a session, too few to solve alone. Kernel 3.17.0 adds
`glyphh_spec.beam`, which carries the likeliest paths through a chain of gates instead of each gate's one best answer.
Its settings and each gate agent's fade were chosen on seed 0. One world, one run.

| Agent | Right | Sessions 1 to 5 | Sessions 6 to 10 | Cost |
| --- | --- | --- | --- | --- |
| Claude alone, starting cold | 22 of 200 | 12 | 10 | $1.50 |
| Claude with its own notes | 157 of 200 | 72 | 85 | $1.35 |
| Gates, Claude on what they refuse | 30 of 200 | 14 | 16 | $1.25 |
| Beam gates, Claude on what they refuse | 36 of 200 | 17 | 19 | $1.46 |

**Memory is what matters here: kept knowledge took Claude from 22 to 157.** The agent that kept it was Claude writing
its own notes, not the gates. The gates barely beat starting cold, refusing most questions in every session. The beam
added 6 answers, and on seed 0 it did no better than plain gates; the fade was what helped the gates recover there.

The likely reason, not tested: 30 chains leave too few precedents, and a fade that forgets in half a day or a day
throws away the little that was kept. The notes agent reasons over everything it has ever seen; the credit rule does
not.

## Claude with Ada as its memory

`substrate.py` and `ada_mcp.py`: the same ten thin sessions, but Claude holds the Ada tools itself (make a model,
record, ask, beam, forget, a 500-character note) and nothing else survives a session. It decides what to keep and when
to ask. One world (seed 11), one run.

| Session | Right | Tokens | Tool calls | What it did |
| --- | --- | --- | --- | --- |
| 1 | 2 | 127k | 32 | made one model `step` (state, action → next), recorded 29 moves |
| 2 to 7 | 1, 1, 1, 3, 6, 3 | 171k to 290k | 46 to 127 | asked the model every state and action (60 asks a session), recorded what it inferred |
| 8 | 11 | 124k | 17 | stopped asking, wrote its whole table into the note: "model step stale; trust this note" |
| 9 to 10 | 13, 11 | 77k | 5 | read the note, answered from it, rewrote it |

52 of 200 right, 1.7 million tokens, $5.67; the notes agent got 157 for $1.35 and the cold one 22 for $1.50.

**Claude did change, in the wrong direction.** It leaned on the model hardest in the middle sessions and did worst
there, then abandoned it for the note and did better. It never used the beam. The reasons it gave in its own note and
what the log shows: one flat model of single moves cannot hold what a chain of 2 or 3 actions does not say (the states
between), so it recorded its own inferences as if they were facts, the 5% noise and the change at session 6 made them
stale, and asking the model 60 times a session cost more than a table in a note. The tools as given made it slower,
not faster.

## What would prove it

Gates that keep what thin sessions teach, with the notes agent as the rival to beat, fixed on seed 0 and run on an
unseen world. Then a task that outgrows notes, since a notes file must fit in every prompt and gates need not.

## Run it

    uv run python run.py          # the table, into results/
    uv run python run.py llm 0.5  # the LLM's prompt and key at that share of moves shown, into results/

`../ada_kernel.py` loads the ada-private checkout. Kernel 3.16.0 for these results.
