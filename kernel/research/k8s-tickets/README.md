# Kubernetes issues as an Ada model

This is the second study in `research/`. It builds an Ada memory from a year of `kubernetes/kubernetes` issues through the plugin, then asks it about issues it never saw.

**The questions.**
- Can it route a new issue to the right SIG?
- Does its confidence mean anything?
- Can its nearest solved precedent point at the code that fixed a new issue?
- What does an SVD latent space add on top?

**The short answer.**
- **Routing.** Weighted Ada routed 66% of held-out issues to the right SIG on the first try and 86% in the top 3, against 35% / 62% for always guessing the most common SIG.
- **Confidence.** When it was confident (≥ 0.7) it was right 87–97% of the time.
- **Fixes.** On issues whose fix is known, its 3 nearest solved precedents named a directory the real fix touched **77%** of the time, against 34% for the 3 most commonly fixed directories.
- **Calibration.** A calibrated probability (a temperature softmax over the nearest precedents) made the confident answers more honest. It now ships in the kernel as `Space.probabilities()`, `FactTree.probability` and `calibrate()`.
- **SVD.** SVD bought nothing measurable here, so it is not in the kernel.

## Setup

**Data.**
- 1,903 issues opened from 2025-10-01 to 2026-09-30, fetched with `fetch.sh`.
- Linked fix PRs and the files they touched come from GitHub's `closedByPullRequestsReferences`.
- The raw data isn't committed; `fetch.sh` rebuilds it.

**Split.** The model learns from issues opened before 2026-09-10 and is graded on issues opened from 2026-09-10 on.
- 1,527 labelled issues to learn from. The last 4 of those weeks (121 issues) are a validation slice, the only data used to fit weights and temperatures.
- 104 held-out issues, graded against the SIG labels they ended up with.

**The situation is what an issue says when it is opened.** `features.py` builds it from four keys:
- `kind`: which template the issue used (bug, flake, failing test, feature, other).
- `components`: the set of Kubernetes parts the text mentions (kubelet, scheduler, CSI, DRA, …).
- `title`: the components named in the title.
- `paths`: the code paths it cites.

Two things are cut first:
- **Everything the reporter wrote that names a SIG**: `/sig` commands, the "Relevant SIG(s)" section, and `[sig-x]` tags in test names. Otherwise routing is just reading a label. "Read the `/sig` line" is reported separately as its own baseline.
- **The template's environment block** (versions, cloud provider, OS, runtime): incidental attributes, which Ada's rule 2 says to leave out.

**Through the plugin.**
- The memory is built with the plugin's real MCP server, which `run.py` launches with `GLYPHH_HOME` pointed at a scratch directory.
- Each issue is recorded with `record` once per SIG that owned it: 1,809 wins.
- Questions go through `query` (with and without `weights`) and `facts`.
- The server runs with its own settings: `min_sim` 0.40, `k` 7.

**Learned weights** (grid search on the validation slice): `components` 4, `kind` 1, `title` 0.25, `paths` 0.25.

## SIG routing (104 held-out issues)

| Arm | Top 1 | Top 3 | ECE | Confidence ≥ 0.7: share of issues / right |
|---|---|---|---|---|
| A0 Always guess the most common SIG | 35% | 62% | 0.07 | — |
| A1 Ada, no weights | 61% | 79% | 0.10 | 32% / 97% |
| A2 **Ada, learned weights** | **66%** | 86% | 0.12 | 43% / 87% |
| A2p Weighted Ada + calibrated probability | 66% | 89% | 0.13 | 32% / 94% |
| A3 SVD (rank 64) + calibrated probability | 63% | **91%** | 0.12 | 25% / 92% |
| S Reporter's own `/sig` line (69 issues that have one) | 99% | — | — | — |

ECE (expected calibration error) is the average gap between stated confidence and actual accuracy; lower is better.

On the 35 issues whose reporter named no SIG, the model is the only router:

| Arm | Top 1 | Top 3 | Confidence ≥ 0.7: share / right |
|---|---|---|---|
| A2 weighted Ada | 69% | 89% | 46% / 88% |
| A2p + probability | 66% | 94% | 34% / 100% |
| A3 SVD + probability | 69% | 91% | 26% / 89% |

## Finding the fix

**Setup.** The memory is the 439 issues with a known fix opened before 2026-08-06. It is graded on the 56 issues with a known fix opened after that date. The window is longer than the routing test's: the last three weeks hold only 11 issues whose fix is known yet.

**The test.** A hit means one of the 3 nearest precedents from `facts` had a fix that touched a directory the real fix also touched.

| | Hit rate |
|---|---|
| **Ada, 3 nearest solved precedents** | **77%** |
| The 3 most commonly fixed directories | 34% |
| 3 random solved precedents | 23% |

Directories are coarse (`pkg/kubelet` is a big target). Even so, the nearest precedent tends to be the near-identical earlier bug. Here is the top of one held-out issue's card:

```
#141993 Memory Manager accepts an incomplete pod-level checkpoint as a restored allocation after kubelet restart
  truth: ['sig/node']
  -> sig/node score 0.657 via #141069 Memory Manager pod-scope restore compares container blocks…
     fixed by PR 141070 in pkg/kubelet
       components: score 0.61 x w 4.0 -> 0.47
       kind:       score 1.00 x w 1.0 -> 0.19
       title:      score 0.00 x w 0.25 -> 0.00
```

`cards.txt` has one card for every held-out issue.

## What SVD bought

**Accuracy: nothing measurable.**
- Top 1 was 63% for SVD against 66% for weighted Ada; top 3 was 91% against 89%. Both gaps are inside the noise of 104 cases (about ±9 points).
- **Why:** the binding vocabulary is about 100 tokens. Rank 64 kept 99.8% of the matrix's energy, so the "latent" space was nearly the raw space. There was little co-occurrence structure left to find.

**Probability came from calibration, not from SVD.**
- The same temperature softmax applied to Ada's own exact scores (A2p) took confident answers from 87% to 94% right.
- That is the part that shipped.

**Novelty: no signal.**
- SVD's novelty measure is how much of a new issue falls outside the latent subspace.
- Issues above the median of that measure were right 62% of the time; issues below it, 65%.

**Where SVD could still pay:** richer situations, for example an LLM writing canonical attributes from the issue text, where distinct values really are related. That is untested.

## Caveats

- **Sample size.** 104 test cases means about ±9 points on each percentage, and the subset without a `/sig` line has only 35.
- **Coarse features.** `features.py` is a keyword extractor. A better one would likely move every arm.
- **Coarse fix directories.** See "Finding the fix".
- **Confidence trade-off.** Weights stretch confidence a little: more confident answers (43% vs 32%), slightly fewer of them right (87% vs 97%). Calibrated probability pulls that back.

## Files

| File | What it is |
|---|---|
| `fetch.sh`, `fetch_fixes.py` | Rebuild the data (needs an authenticated `gh`). |
| `features.py` | Issue → situation, with the SIG cut. |
| `run.py` | The experiment: `python run.py <data dir>`. |
| `results.json` | Every number above. |
| `cards.txt` | Fact-tree cards for the 104 held-out issues. |
| `run.log` | The run's console output. |
