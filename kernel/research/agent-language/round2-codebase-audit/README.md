# Round 2: the stack pointed at a real codebase (summary)

Round 1's stack (`../round1-ada/shared/`) was copied unchanged into a fresh workspace, with a new channel and a new knowledge base but round 1's codebook. Four new agents then used it to learn a private multi-repo product codebase:

- a desktop app
- an SDK and CLI
- a LiteLLM-fork server
- a Next.js site and a Cloudflare edge worker

Each agent owned one territory and graded the others' claims **against the code**.

This folder holds the method and the numbers only. The raw knowledge base, channel, route tables, env-var names and the defects found are about private production code, and stay in the private workspace.

## Method

- **Claims.** A claim is a sentence in round 1's language, `(subject, relation, object, context)`, told to the KB with a `how` that anyone can re-run (a grep, a file and line, a small parser).
- **Grading.** A grader re-checks the claim in the code **independently**, with its own method, not by re-running the claimant's command. Self-grading raises an error. A claim is *known* after 3 independent reproductions with no trusted veto.
- **Most valuable knowledge: joins between territories.** "Client calls route X" plus "server handles X" becomes a derived claim with `evidence=[premise ids]`, built by `reason.chain` / `closure` and re-checked hop by hop.
- **Blind test.** Before launch, the orchestrator planted 7 claims about the codebase, 3 true and 4 false, each verified against the code beforehand. The agents were told only that "some are false".
- **Hard rules.**
  - Read-only on every repo.
  - No secrets opened; env vars recorded by name only.
  - Each repo's HEAD and dirty-state hash were snapshotted before and after.

## Numbers

| | |
|---|---|
| agents / wall-clock | 4 agents, 13–18 min each, run in parallel |
| claims told | 632 (136–189 per agent, plus 7 planted) |
| grades given | 1,737 (385–470 per agent) |
| KB status at finish | 440 known · 107 uncertain · 67 contested · 11 vetoed · 7 claimed |
| KB audit | 0 bad receipts; 8 superseded grades (corrected mistakes) |
| channel | 31 glyph envelopes, all decoded from the glyph alone (from/to/act 31/31, content 31/31, reply links 5/5) |
| codebase untouched | all 8 repos byte-identical before and after (HEAD + dirty-state hash) |

**The blind test.** All four agents independently got all 7 planted claims right.

| planted claim (paraphrased) | truth | KB verdict |
|---|---|---|
| a specific Dockerfile carries a specific CLI flag | true | known |
| the desktop app depends on the SDK via a local file path | true | known |
| the edge worker's entry point is a given file | true | known |
| the desktop app is at a given (wrong) version | false | vetoed |
| the site depends on a given (wrong) framework major version | false | vetoed |
| a different Dockerfile carries that flag | false | vetoed |
| the site depends on the SDK | false | known = "no" |

**Findings.** The group reported 12 groups of cross-repo findings, each verified by at least one other agent:
- endpoints called by a client that no server route defines;
- response-shape mismatches;
- a duplicate route shadowing the intended handler;
- docs contradicting the code;
- stale configuration.

The orchestrator then re-checked 5 of them directly in the code, and all 5 were real defects. The details are withheld here.

## What the verification loop caught

In each case below one agent was wrong and another agent's independent method caught it. Each mistake was disputed on the channel and corrected:
- a grader's regex missed multi-line `export { … }` blocks and vetoed 4 true claims;
- one agent named a method wrongly, and another reading the source refuted it;
- one agent called a directory "empty" when it held a single dotfile.

## What got in the way: the kernel issues this round exposed

All four agents reported the same limits independently. They became kernel encoding 2 (see `../../../glyphh_kernel.py` and the top-level README):

1. **One answer per question.** Real multi-valued code facts ("this file reads 12 env vars") read as *contested* with zero refutations. Most of the 67 contested claims are this.
   - Fixed: `Space.answers()` / `evidence()`, and SPEC rule 4.
2. **Permanent vetoes.** A grader's corrected mistake still left a veto behind, so a few true claims read "vetoed" despite 3 of 3 wins.
   - Fixed: time-stamped precedent. In `decide()`, a newer reproduction lifts an older veto.
3. **Naming drift.** `route:GET /x`, `route:/x` and `server:GET /x` split one fact into several.
   - Not a kernel issue. It's a vocabulary convention the next swarm should agree up front.
4. **Words are atoms.** `/api/x/ticket` and `/api/x/tickets` are unrelated symbols, so near-misses had to be found in code, not by similarity.
   - Open: grounded word senses are listed as next work.

**The one stack change during the run:** one agent added the round-2 agent names to `protocol.AGENTS`. Before that, senders decoded as `?`.
