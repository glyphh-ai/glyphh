# Agent language: swarms that build their own software on the kernel

This is the first study in `research/`. It is **one** example of what agents do with the kernel, not the limit of it.

**The question.** Give a swarm of agents a small deterministic primitive and one task: *make a language and build, with it, an application you use to communicate and to build intelligence.*
- What do they build?
- Does it hold up on real work?
- What did the primitive itself contribute?

**The short answer.** Across three runs of four agents each, the agents built software **for themselves, not for humans**:
- glyph-to-glyph protocols;
- a knowledge base that only trusts what another agent independently reproduces;
- reasoning that says "I don't know" with calibrated confidence.

They made all of it deterministic, so every claim can be checked by re-running it. Pointed at a real codebase, the same stack judged 7 of 7 planted claims correctly and surfaced real defects.

A numpy-only control built comparable machinery, which makes the kernel's specific contribution narrower and sharper:
- its **fixed encoding**, a shared standard;
- its **trust defaults**, which measurably changed what the agents accepted as true.

## Layout

| folder | what |
|---|---|
| [`round1-ada/`](round1-ada/) | **Round 1.** Four agents (lexicon, courier, memory, reasoner) given the kernel. They built `shared/language.py`, `protocol.py`, `knowledge.py` and `reason.py`, plus their own tests, benches and reports. `REPORT.md` is the combined report, `TRANSCRIPT.md` the conversation decoded from the glyphs alone, and `shared/LANGUAGE.md` the spec they co-wrote. |
| [`round2-codebase-audit/`](round2-codebase-audit/) | **Round 2.** Round 1's stack, unchanged, used by four new agents to audit a private multi-repo codebase. Summary and numbers only; the raw data stays private. |
| [`control-numpy/`](control-numpy/) | **Control.** Four agents with the same roles and prompts minus the kernel, numpy and the stdlib only. |
| [`compare/`](compare/) | `RUBRIC.md`, written **before** the control finished, and `COMPARISON.md` (the results, including an adversarial probe of both trust layers). |
| [`kernel_v1/`](kernel_v1/) | The kernel exactly as the agents ran it (encoding 1). Round 1's code imports it from here, so the results reproduce regardless of later kernel changes. |

Paths inside the copied reports still say `test-dir/agents`, `test-dir/control-numpy` and so on, where the runs happened. They map to the folders above.

## Results at a glance

| | Round 1 (kernel) | Round 2 (kernel stack on a real codebase) | Control (numpy only) |
|---|---|---|---|
| agents / time | 4 / 20–34 min | 4 / 13–18 min | 4 / 20–28 min |
| tests (all pass) | 93 | (uses round 1's) | 89 |
| messages decoded from payload alone | 28/28 envelopes | 31/31 | 33/33 protocol, 46/46 payloads |
| claims / grades | 95 / 258 | 632 / 1,737 | 43 facts / 153 events |
| planted false claims caught | 4/4 (planted by memory) | 4/4 plus 3/3 true confirmed (planted by the orchestrator) | 1/1 |
| trust gate | ≥3 independent reproductions + veto | same | Beta trust ≥ 0.6, ≥1 outside grade |

Head-to-head probes, run by the orchestrator on scratch copies (see `compare/COMPARISON.md`):
- **Determinism:** both stacks are byte-identical across processes.
- **Capacity:** at the same 4,096 dimensions, the control's least-squares reader decodes 64 fields exactly to the kernel stack's 32.
- **Collusion:** a lie with one colluding ally is **blocked** by the kernel's count gate but **accepted** by the control.
- **Sabotage:** one hostile refutation **erases** a true fact under the kernel's encoding-1 veto rule but is **resisted** by the control.

## What changed in the kernel because of this

Every agent in every round hit the same kernel limits. Kernel **encoding 2** (`glyphh_kernel.py` 1.1.0) fixes them:

1. **Vetoes were permanent.** One mistaken or hostile refutation suppressed a true fact forever.
   - Precedent is now time-stamped. In `decide()`, a newer reproduction lifts an older veto and a newer failure re-imposes it.
   - `min_veto_count=2` demands corroborated failures, which makes a lone saboteur ineffective.
2. **One answer per question.** True multi-valued facts read as "contested".
   - `Space.answers()` and `Space.evidence()` judge each outcome on its own count, over every precedent, not just the top `k`.
3. **The contract was pseudocode.** Every agent re-implemented it, differently.
   - `decide(wins, vetoes, situation)` now returns a `Decision` with a `reason`. The plugin's MCP server uses it.
4. **Tie-break position bias.** Round 1's memory agent found that similarity depended on which attribute differed. Changing the attribute that sorts first cost twice as much as changing the one that sorts last (0.26 vs 0.50 at two attributes).
   - Ties are now broken by a hash of the parts as a set: order-free and unbiased (the gap is now below 0.02).
5. **Stores outlived their encoding silently.**
   - Files now carry an encoding stamp and re-encode on open, and events are stored so re-encoding is lossless.

Round 1's code passes all its tests on both encodings.

## Reproduce

Run from this folder. The tests write only to temporary or private stores, but the benches and live scripts append to the stacks' shared files, so run them in a scratch copy.

```bash
cd round1-ada && for d in lexicon courier memory reasoner; do (cd $d && python3 -m unittest discover -p 'test_*.py'); done
```

```bash
cd control-numpy && for d in lexicon courier memory reasoner; do (cd $d && python3 -m unittest discover -p 'test_*.py'); done
```

`round1-ada/courier/measure.py`, `lexicon/capacity.py`, `reasoner/bench.py` and `memory/demo_curve.py` reproduce the measured tables in the reports.

## Honest limits

- **Small samples.** One run per arm, one model, one session. The control's prompts were derived from round 1's. Differences are suggestive, not statistically significant.
- **Same model grading itself.** Its errors may correlate, so three agreeing agents is weaker evidence than three independent humans.
- **Easy blind test.** The planted claims in round 2 were checkable with a grep. Semantic falsehoods ("this handler checks auth") are the harder, untested case.
- **Round 1 knows only itself.** Its knowledge is all self-referential: measurements of its own language. Round 2 is the only run grounded in an outside world.
- **The interoperability advantage is untested.** A fixed shared encoding is the kernel's clearest contribution, and none of these runs tested it: each swarm only talked to itself.

## Where this goes next

This study barely scratches the surface. Open directions:
- **Cross-swarm interoperability.** Two independently built swarms exchange knowledge, with the kernel and without. This is the test of the standard.
- **Semantic blind tests** and a different model as one of the graders.
- **Grounded word senses.** A word's meaning comes from the contexts it is used in, so near-duplicate names (`ticket` / `tickets`) are caught by similarity.
- **Long-running swarms** on a live codebase, where facts expire as code changes. This is now possible with time-stamped precedent.
- **The consult-rate curve** measured from real decisions routed through `decide()`, not simulated.
