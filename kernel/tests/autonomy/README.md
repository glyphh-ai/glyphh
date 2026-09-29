# The Entity: software that buys intelligence once and owns it

## In one paragraph

Today, software that uses an LLM rents intelligence forever: every
decision is an API call, every day the meter runs, and the model — tuned
by RLHF to seek human approval — never stops needing supervision. The
entity in this folder inverts that. It is ~100 lines over the glyphh
substrate that treats an LLM as a **consultant hired only for novelty**:
when it faces a situation its own history can't answer, it asks the LLM
for a suggestion, tries it, and lets **the world** — not a human, not
the LLM — grade the result. Actions that worked become permanent,
citable precedent (one write, no training run). Actions that failed
become vetoes. Over its life the entity consults less and succeeds
more, until the LLM is almost never called. Intelligence becomes
capex, not opex.

## The measured result

Same 400-step life, same deterministic ops world (six incident kinds;
one pair differs only in event ORDER; some remediations depend on
severity). Two teachers:

| quartile | consult (sim) | success (sim) | consult (live Claude) | success (live) |
|---|---|---|---|---|
| Q1 | 0.38 | 0.90 | 0.68 | 0.60 |
| Q2 | 0.13 | 0.95 | 0.28 | 0.80 |
| Q3 | 0.09 | 0.99 | 0.28 | 0.71 |
| Q4 | **0.04** | **1.00** | **0.25** | **0.92** |

Live run: 149 API calls, $0.27 total, and the number that matters —
**the LLM was right 45% of the time; the entity's reflexes run at 94%.**
The student beat its teacher by 49 points, which classic distillation
cannot do, because the entity never learns the teacher's opinions: it
learns the intersection of the teacher's guesses and reality. The wrong
55% got graded, vetoed, and discarded; the right 45% got kept and
replays deterministically forever.

Reproduce (deterministic, no key, seconds):

    python3 -m pytest tests/autonomy -q

Reproduce the live run (set ANTHROPIC_API_KEY; ~$0.10-0.30):

    python3 -m pytest tests/autonomy/test_live_llm.py -q -s

## How it works (simple terms)

Think of a new employee on a helpdesk with a very expensive expert on
speed-dial.

1. A ticket arrives. The employee checks their own notebook: *have I
   seen something like this before, and did my fix work?*
2. Notebook has an answer → do that (a **reflex**: instant, free).
3. Notebook is blank → call the expert, try what they say.
4. Either way, reality answers: the fix worked or it didn't.
5. Worked → write it in the notebook, forever. Failed → write "never
   that again for this situation," which also forces a fresh
   consultation next time (the entity is never confidently wrong twice).

The expert is the LLM. The notebook is a glyphh DecisionSpace — so
"something like this" is real similarity math over attributes AND the
order events happened, and every notebook entry keeps its receipts (a
fact tree of the precedent behind it). The employee's phone bill
provably shrinks every week, and after a while they only call about
things that are genuinely new — and they *know* what's new, because the
notebook says so.

The one non-obvious design rule this experiment forced: **failure must
be first-class memory.** The first version had no vetoes; it became
confidently wrong forever on one slice (success collapsed to 0.76).
Vetoes turned the collapse into monotone improvement. Autonomy is safe
exactly when failure reopens humility without a human.

## A real-world example you can prove

**Support-ticket routing** (works identically for payment-retry
strategy, incident remediation, lead assignment — anything where the
world grades the decision).

- **Situation:** ticket attributes (product area, customer tier,
  keywords) + the ordered event trail (what pages/errors preceded it).
- **Action:** which team gets it (8-30 choices).
- **The world's grade, no human in the loop:** if the receiving team
  RESOLVES it, the routing was right; if they REASSIGN it, it was
  wrong. Your ticket system already records this.

Falsification protocol on your own data, one afternoon:

1. Export 12 months of tickets in arrival order with their final
   resolving team.
2. Replay them through the entity: consult an LLM when precedent is
   thin, grade each routing against the recorded outcome, record wins
   and vetoes.
3. Plot the two curves this folder plots: LLM-consult rate and routing
   accuracy per quartile of the replay.

The claim is proven if consult rate falls toward a floor while accuracy
meets or beats (a) the LLM alone on the same tickets and (b) your
current router. The claim is falsified if accuracy needs the LLM to
stay high. Everything is measured against ground truth you already
possess; nobody has to trust a demo.

## Is there precedence?

Yes — every piece has a lineage; the assembly and the economics are the
new part.

- **Case-Based Reasoning (1980s-90s):** retrieve a similar past case,
  reuse its solution, revise, retain. The entity IS a CBR loop; CBR
  faded partly because similarity over messy situations was weak and
  case acquisition was manual. Glyphh supplies the similarity (HDC over
  attributes + event order) and the LLM supplies case acquisition.
- **AlphaGo → AlphaGo Zero (2016-17):** the canonical proof that
  grounding beats imitation — learning from outcomes surpassed learning
  from human experts. Same principle here, without gradient training.
- **Knowledge distillation (Hinton, 2015):** student learns teacher's
  outputs — and lands at or below the teacher. Our student exceeds its
  teacher (94 vs 45) precisely because the world filters the transcript
  first. Distillation with a reality gate is a different animal.
- **DAgger (2011) / LLM-guided exploration (ELLM 2023, Eureka 2023):**
  using a knowledgeable prior to make exploration cheap, then letting
  the environment correct it — the formal role our LLM plays.
- **Voyager (2023) — nearest neighbor:** an LLM in Minecraft proposes
  skills, the game verifies them, verified skills enter a library and
  get reused. The differences that matter: Voyager keeps the LLM in
  charge forever (the library is the LLM's toolbox); here the authority
  is inverted — the precedent store decides, the LLM's involvement
  measurably decays to a floor, failures are first-class vetoes, and
  every decision cites its precedent in a fact tree. Voyager reduces
  the LLM's work; the entity retires it.
- **Reflexion (2023) / agent memory lines:** episodic self-feedback for
  LLM agents — but stored as text the LLM must re-read every call, so
  the meter never stops. Here memory is the decision procedure itself.

What we have not found precedent for, stated carefully: a system where
**the marginal need for an LLM provably decreases with experience** —
the consult-rate curve as a first-class, falsifiable product metric —
with symbolic one-shot retention, outcome-only reward (no RLHF, no
approval), failure vetoes, and per-decision receipts. That specific
assembly, and the "intelligence as capex" economics it produces, appears
to be new. (Treat that as a claim to challenge, not a settled fact —
the literature moves fast.)

## Honest limits

- Works where the world grades **cheaply, quickly, and unambiguously**.
  Slow or fuzzy feedback keeps the LLM on the payroll.
- The entity escapes its teacher's ceiling, not the world's — it can
  never know what reality can't confirm.
- Novelty detection is per-situation, not per-concept: a genuinely new
  kind of event whose surface attributes rhyme with old ones can draw a
  wrong reflex once before the veto corrects it (observed live). The
  strand drift score is the designed fix and not yet wired in here.
- The precedent store's seed corpus is, literally, the LLM's verified
  outputs. Know what the artifact is.
