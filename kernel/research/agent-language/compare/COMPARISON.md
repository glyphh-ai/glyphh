# Ada vs numpy only: results

The two arms, scored against [RUBRIC.md](RUBRIC.md), which was written before the numpy arm finished:

- **Arm A** (`test-dir/agents/`): four agents given the Ada kernel.
- **Arm B** (`test-dir/control-numpy/`): four agents given numpy and the stdlib only.

Both arms had the same roles and the same prompts, minus kernel terms. One run each.

✔ marks a result the orchestrator measured itself on scratch copies of both stacks, run with the same probe scripts (`$TMPDIR/cmp/probe.py`, `attack.py`). Unmarked numbers are each agent's own.

## Summary table

| | A: Ada | B: numpy only |
|---|---|---|
| Agent time (harness) | 20–34 min (1212–2015 s) | 20–28 min (1208–1695 s) |
| Tool calls per agent | 85–103 | 82–93 |
| Shared code | 2,256 lines + the 485-line kernel | 3,054 lines (they wrote their own vector engine) |
| ✔ Tests | 93, all pass | 89, all pass |
| Representation | Ada glyphs: 4096-d bipolar, sha256 symbols, bind/bundle/roll | **Reinvented the same family**: 8192-d bipolar, sha256 atoms, bind by multiplying, roll for nesting, majority bundle |
| One object for facts, questions, messages, conclusions | yes | yes |
| ✔ Deterministic across processes (different `PYTHONHASHSEED`) | yes, byte-identical | yes, byte-identical |
| Built for machines | 32/38 channel lines carry glyphs; 28/28 envelopes decode from the glyph alone | 46/46 payloads decode from the payload alone; 33/33 protocol messages match their text |
| ✔ Capacity, flat frames exact at the same 4,096 dims (1,000 words, 128 roles) | 32 fields; 48 → 9/15; 64 → 0/15 | **64 fields**; 96 → 0/15 (a least-squares "peeling" reader) |
| Nesting | 2–3 levels anonymous; any depth with `chunk` | depth 6 × 4 branches exact; proofs up to 20 premises |
| Trust: known when | ≥3 independent reproductions, strict majority, no veto | Beta trust ≥ 0.6 and ≥1 outside ok, reputation-weighted |
| Self-grading refused in code | yes | yes |
| Planted false claims | 4 planted by memory, 4 refuted (8/8 refutations) | 1 planted (`7×9=64`), refuted by 2 agents |
| Calibrated "I don't know" | ECE 0.024 | ECE 0.012 |
| Built that the other arm didn't | typed slot learning, fidelity check, lineage/stale, ordinal inference | the language growing its own words (dictionary), conversations turned into facts, grader reputation, a naive-baseline comparison, Horn-rule inference, contradiction detection |

## The adversarial probe ✔

Both knowledge bases got the same attacks, on fresh temporary stores:

| attack | A: Ada KB | B: numpy KB |
|---|---|---|
| a lie plus **one** colluding "ok" | `uncertain`: **blocked** | `answered: cheese`: **accepted** |
| a true fact with 3 reproductions | `known` | `answered` (conf 0.74) |
| the same, plus **one** hostile refutation from a newcomer | `vetoed`: **the true fact is lost** | `answered` (conf 0.70): **sabotage resisted** |

The two stores fail in opposite directions:
- A's count gate (from the kernel's contract) makes it hard to fool, but easy to silence.
- B's Beta scoring makes it hard to silence, but a single ally can push a lie through. B's memory agent reported this weakness itself.

## What this says about Ada

**1. The primitive did not unlock capability.**
- Without it, four agents reinvented the same class of vector-symbolic machinery from scratch, in the same time and with the same effort.
- At equal dimension their reader decodes twice as much.
- They were as deterministic, as machine-first, and as well tested.
- The earlier claim that the kernel was needed for agents to build this is **not supported**.

**2. What Ada did change: the trust policy.**
- Both arms got the same prompt about grading. The Ada arm adopted the kernel's stricter gates: 3 reproductions, strict majority, and a veto primitive. It explicitly cited `spec()`'s "a consensus of one means almost nothing".
- The numpy arm settled for one outside grade.
- That difference showed up exactly in the collusion probe.
- So the kernel's value here is **its opinions, written down**: defaults about when to trust, not operations.

**3. What Ada offers that a from-scratch stack can't: a fixed standard.**
- B is deterministic *within its own code*. Another team's numpy stack would produce different vectors for the same meaning.
- Ada's symbols are fixed by `(key, seed, dim)` forever. Two groups that both use Ada share a vocabulary with no negotiation.
- This experiment never tested that, because each arm talked only to itself. It is the one advantage B can't reproduce without adopting a shared spec, which is to say, Ada or something like it.

**4. Ada's defaults have real costs.**
- Permanent vetoes let one hostile newcomer erase a true fact.
- The single-answer `Space` made true multi-valued facts read as contested (every round-2 agent hit this).
- B's design avoided both.

## Verdict

"A primitive lets agents build tooling they otherwise couldn't" is **not what this run shows**: a strong model builds the equivalent from numpy in about 25 minutes.

What it does show:
- A small, written-down primitive with **opinionated trust defaults** measurably changes how agents decide what's true, for better (collusion) and worse (sabotage).
- A **fixed encoding** is the one thing a from-scratch stack cannot give you, because interoperability across teams needs a shared standard.

## Caveats

- One run per arm, same model, same session. Arm B's prompts were derived from Arm A's.
- The capacity probe used each arm's own default reader settings. B's reader is slower: about 35 ms vs about 18 ms per decode, per the agents' reports.
- The attack probe uses each KB's default configuration. Ada's round-1 memory agent measured other veto rules (`parity`) that resist sabotage better.
- The contamination check (a grep for Ada paths and idioms in B's code) was clean, but it cannot prove the agents never read `ada/`.
