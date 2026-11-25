# Ada vs numpy-only: comparison rubric

Written **before** the numpy control finished, so the criteria can't be bent to fit either result.

- **Arm A:** `test-dir/agents/` (round 1, Ada kernel).
- **Arm B:** `test-dir/control-numpy/` (numpy + stdlib only).

Same four roles, same prompts minus kernel-specific terms, and the same channel helper (renamed `glyph` → `payload`, with any dtype and shape allowed).

The orchestrator runs every probe itself on both arms, with the same code where possible.

## 1. Build

- Agent wall-clock time and tool calls (from the harness).
- Lines of shared code and of per-agent code.
- Test count, and whether every suite passes when the orchestrator runs it.

## 2. Coherence (one system or four?)

- An import graph of `shared/*.py`: does each layer build on the others?
- Is there one representation that facts, questions, messages and conclusions all share?

## 3. Determinism (the claim under test)

- **Cross-process:** encode the same structured meaning in two fresh Python processes. Are the bytes identical?
- **Cross-machine by construction:** does the representation depend on process state (unseeded RNG, dict order, `hash()` randomisation, a local file)?
- **Replay:** decode the channel log from the payloads alone, in a fresh process. Does it match what was recorded?

## 4. Machine-first (built for themselves?)

- The share of channel messages that carry a machine payload.
- Decode accuracy of those payloads, read from the payload alone, without `text`.
- Whether any human-facing interface was built.

## 5. Trust layer (build intelligence)

- Is self-grading prevented in code?
- Is there a reproduction threshold before something counts as known?
- Does a veto or refutation exist, and can consensus outvote it?
- Is there provenance (who wrote and graded what)?
- Were false claims planted or caught?
- Claims told, graded, known and refuted.

## 6. Reasoning

- Is there a calibrated "I don't know"?
- Which of analogy, chains, abstraction and nesting exist, and at what measured accuracy?

## Known confounds (stated up front)

- **Same model, same session.** Arm A ran earlier. Arm B's prompts were derived from Arm A's.
- **Prompts carried ideas.** In both arms the prompts asked memory for "never self-graded / another agent reproduces it". So a trust layer in both arms comes from the prompt; *how* it is built and whether it holds up is what can differ.
- **Arm A had a reference.** Its kernel ships a written spec (`spec()`) with rules; Arm B has none.
- **Sample size.** One run per arm. Differences are suggestive, not statistically significant.
