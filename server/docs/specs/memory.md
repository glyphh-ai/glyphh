# Glyphh memory: the hosting plan

**Status:** proposed, nothing built. Written 2026-11-10 from the research in `timmetim/thinktank`
(`version_22_qwen_adapter/FINDINGS.md`, steps 1 to 11) and `origin/main` of `server` (edf2417). It answers one
question from Chris: do we host a model with the memory adapter inside it, or host only the adapter and reach it from
an SDK? **Recommendation: host only the memory, inside Ada Cloud, and reach it from the Python SDK.** No GPU, no
inference plans, no new infrastructure, and the IP never leaves the server.

**Ruled since (Chris, 2026-11-10, later the same day): option A. The memory lives in the model, and Glyphh hosts
that model; the open question is only how big.** The reason: through someone else's model in text-only mode the fact
memory is RAG with a better store. What is not RAG, and what is worth owning, is the memory acting on the next word
inside the model (a correction lands 100% where the same fact in the prompt lands 6%) and the gate on the output,
and both need the model's insides. Ada stays the external product (API and SDK). The recommendation below (B) is
kept as written for the record; sections 2 A and 6 are the path, and section 3's draft-check loop still describes
how rules work inside the hosted model.

**The ruling this keeps (Chris, 2026-11-09):** the adapter is never shipped to a customer. It is the IP, and the goal
is an acquisition. What changes is where the language model runs.

---

## 1. What the memory does

A memory beside a language model. The model's weights never change.

| | What it does | Measured (Qwen3-1.7B, 2026-11) |
|---|---|---|
| **Facts** | Told once, recalled in any wording, corrected in place, nothing else forgotten | 3,000 facts: recall 99-100% in six wordings (five never taught), corrections 92-100% after one telling, untouched facts 100%, the model's English unchanged (1.164 -> 1.167 bits/char). Fine-tuning (LoRA): 7% recall, forgets, damages English. Everything in the prompt: corrections 6% |
| **Rules** | An instruction given once is followed in later sessions with nothing in the prompt | A rule that acts at one place (a sign-off): 100% on unseen questions. A rule that acts on a topic (a ban): 50% (in the prompt: 85%), never applied where it has no business. In progress |

Not yet measured: a model larger than 1.7B (a 14B run is in progress), more than 3,000 facts, more than three rules,
more than one tenant.

## 2. The two ways to host it

### A. Host the model (the adapter inside our own inference server)

The customer calls a chat API; Glyphh runs an open-weight model on GPUs with the memory in the loop.

- **Adds:** GPU machines at a new provider (Fly retired its GPUs on 2026-08-01), an inference server, token
  metering, inference plans, model upgrades, GPU capacity planning and an uptime promise for generation.
- **Costs:** one always-on 48 GB L40S, enough for a 14B-32B model, is about $1.09 an hour (Runpod, 2026-11-10):
  about $800 a month before the first customer. An H100 is about $2.89 an hour, $2,100 a month.
- **Sells:** tokens. Glyphh competes on price and model quality with every inference host, with a small model.
- **IP:** safe.

### B. Host the memory (recommended)

The customer runs whatever model they like. The `glyphh` SDK sits in their generation loop and asks Glyphh's memory
what it knows; the memory answers from the server. The SDK is a thin client: it holds no keys, no thresholds and no
encoding, only "send this text, apply this answer".

- **Adds:** one more kind of model in Ada Cloud (same Postgres schema per org, same workers, same keys, same
  metering), and a module in the SDK. No GPU, no new plan family.
- **Costs:** CPU and Postgres, as Ada Cloud today.
- **Sells:** memory. "Push your data to Ada. She never forgets." Any model, including the one the customer already
  pays for.
- **IP:** safe. How a memory is keyed, stored and matched stays on the server. What a customer can observe is the
  protocol: text in; a continuation, a halt or a recalled rule out.

## 3. How B works

The research already ends in a loop that needs no access to the model's insides at reply time (steps 9 to 11):
**predict, look back, halt, recall, redraft.** The model drafts a reply; the memory reads the draft; where it knows
better it says where to stop and what to bring into view; the model redrafts from there.

```
SDK (customer's machine or cloud)                 Glyphh (Ada Cloud)
---------------------------------                 ------------------
draft = model.generate(prompt)        -- draft -->  match the draft against this org's memory
                                      <-- halts --  [{at, recall: "rule or fact text"} ...] or nothing
redraft from the first halt with the
recalled text in view; repeat (at most
once per recalled item)
reply to the user
```

- **One call per draft, not per token.** A reply costs one to three calls. Nothing streams to the user until the
  draft is checked; that is the latency cost (about one extra generation per reply that halts).
- **Teaching a fact:** `memory.tell(text)`. One call, no model needed.
- **Teaching from documents (agreed, Chris 2026-11-10):** the customer sends whatever they have; nobody is asked for
  structured data. Ingest rewrites each note into single sentences that each name their subject ("Piheba Doti's
  account manager is Nipira."), using the customer's own model through the SDK, and those sentences are what is told.
  Subject-named one-sentence facts are what is proven at 99-100%; raw prose that says "they" after the first
  sentence is not (thinktank step12).
- **Teaching a rule:** `memory.rule(text)` starts a rehearsal. The server asks the SDK for generic work only
  ("answer this practice question with this system prompt", "score this text under that prompt"), and decides on its
  side what the rule changed and where its gates sit. About two minutes of the customer's model at 1.7B.
- **Two modes, by what the customer's model exposes:**

| Mode | For | What the memory returns | Proven |
|---|---|---|---|
| **Steer** | Open-weight models run locally (transformers, MLX, vLLM, llama.cpp): the SDK sees the next-word scores | Halts, recalled rules, and for facts the remembered continuation to mix into the scores | Facts and rules, with the memory in-process |
| **Recall** | Any chat API, Claude and GPT included: text in, text out | Halts and the text to place in view | Rules (this is steps 9 to 11). Facts by recall: not tested |

## 3.1 What has to change (Chris, 2026-11-10: "we already have Ada and the Python SDK")

Nothing new stands up. The research already runs on the Ada kernel (`glyphh_kernel.symbol`, `glyphh_lexicon.LEXICON`,
`glyphh_nsm.decompose` from `ada-private`); three places gain functions:

| Where | Gains | Today |
|---|---|---|
| **Kernel** (`ada-private`) | A memory store: text keyed by meaning with its remembered continuation, nearest match above a threshold, a correction that replaces in place. Gates: at a spot of a draft and on a whole draft. Rehearsal: finding where a rule changed a reply | The encoding exists; the store, the gates and rehearsal live only in `thinktank` scripts |
| **API** (`server`) | `tell` (a fact), `rule` (starts a rehearsal job), `check` (a draft in; halts and recalled text out), `forget` | Models, records, reads, jobs, keys and metering exist and are reused |
| **SDK** (`glyphh`) | A `memory` module: the draft, check, redraft loop around the customer's own generate call, and the score mixing for Steer mode | The client, auth and Ada calls exist |

## 4. Plans and metering

No new plan. A memory is a precedent and a draft check is a read, counted exactly as `docs/specs/ada-cloud.md`
section 7 counts them:

| | Free | Basic | Pro | Team | Enterprise |
|---|---|---|---|---|---|
| Memories (facts and rules), within the org's precedents | 1,000 | 10,000 | 100,000 | 1,000,000 | By contract |
| Draft checks, within the org's requests a month | 5,000 | 50,000 | 1,000,000 | 5,000,000 | By contract |

A reply is one to three reads. At $1 per 10,000 reads over the plan, 10,000 replies cost a customer $1 to $3.

## 5. What has to be proven before B is built

| # | Proof | Where | Why it could fail |
|---|---|---|---|
| 1 | The numbers hold on a bigger model | thinktank, Qwen3-14B (running 2026-11-10) | A stronger model may resist steering more, or need it less |
| 2 | Facts work through the draft check | thinktank, next step | Facts are proven steering every word live; checking a finished draft is a different loop |
| 3 | Facts work in Recall mode | thinktank, against a chat API | With every fact in the prompt corrections failed (6%); recalling only the current fact is untested |
| 4 | Topic rules reach the prompt's level | thinktank | 50% against 85% today |
| 5 | Scale and tenancy | server | 3,000 facts and one user so far; an org may hold a million |
| 6 | Latency of a draft check | server | Target: under 50 ms at the server for a 100-word draft |

## 6. What A is still good for

A demo. One rented GPU for a week (about $185 on an L40S) running a 14B model with the memory in the loop is the
fastest way to show a buyer "tell it once, it remembers" in a chat window, with no SDK to install. It is not a plan
to sell tokens.

## 7. Open decisions for Chris

1. **B over A** as the product (this document's recommendation), with A only as a demo.
2. **The name.** "Glyphh memory" here; "Ada memory" keeps one product name.
3. **Which mode ships first.** Recall reaches every model including Claude and is the smaller build; Steer is the
   stronger result and the one the research proves.
4. **Whether a draft check is one read** however long the draft, or priced by length.
