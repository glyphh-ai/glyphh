# Glyphh Runtime

A hyperdimensional computing runtime. Glyphh, period: host models, stream
data in, query out — and the only thing it ever returns is a fact tree.

There is no chat, no LLM, no embeddings model anywhere in the runtime.
Deploy a model and its capabilities appear as MCP tools; import data over
a websocket and the manifest defines how it encodes (structure, temporal
flags, weights). What a model does is inherent to the model, not the
runtime. Language models live on the CLIENT side: they call the tools,
receive fact trees, and do the phrasing — the runtime is the information
boundary, and it cannot confabulate because it never generates.

## Architecture

```
.glyphh package (zip: manifest.yaml + encoder.py + data/*.jsonl)
    |
    v  deploy_model / seed_model (MCP)
+---------------------------------------------------+
|  Glyphh Runtime                                    |
|                                                    |
|  MODELS      (org_id, model_id) registry           |
|              manifest-defined encoder config       |
|              exemplars staged + encoded on deploy  |
|                                                    |
|  INGEST      websocket listeners                   |
|              data -> glyphs per the manifest        |
|              temporal flags + weights from config  |
|                                                    |
|  QUERY       similarity search -> FACT TREE        |
|              citations, per-layer breakdown        |
|                                                    |
|  DECIDE      precedent engine -> FACT TREE         |
|              outcome distribution + confidence     |
|                                                    |
|  TOOLS       each model's MCP_TOOLS surface        |
|              automatically on /mcp                 |
+---------------------------------------------------+
    |
    v
SQLite (single node) or PostgreSQL + pgvector (scale)
```

### The Fact Tree Contract

Every answer the runtime gives — a model query, a decision, a
model-exported tool — is a **fact tree**: grounded, cited structure,
never prose. Similarities, provenance, per-layer breakdowns, explicit
confidence. Phrasing is the caller's job: the LLM on the client side
(Claude, or whatever speaks MCP) turns the tree into language. The
runtime is the information boundary; it cannot confabulate because it
never generates.

### Models

The runtime ships with ZERO models installed — it is a clean substrate.
Every behavior lives in a model the user deploys (via the MCP `deploy_model`/`seed_model` tools or a `.glyphh`
package). What a model does is inherent to the model, not the runtime:
deploy the firewall model and ask "is this a prompt injection?"; deploy
the code-index model and ask about your codebase.

Bundled example models in `capabilities/` (deployable, never auto-installed):

- **firewall** — Prompt injection detection (200+ patterns, 16 attack families)
- **cognitive-router** — Routes requests to the right model
- **speaker-id** — Voice identification via MFCC encoding
- **code-index** — Semantic codebase search with 4-layer encoding



## Trajectory Intelligence

Alongside the lattice (bundled, order-insensitive glyphs), the runtime carries a second, DNA-shaped view of the same substrate: the **strand** (`glyphh/strand`) — an ordered permute-bind chain of codons where order is structural, complements are exact (`-v`), a template/coding duplex transcribes losslessly, and splice/crossover produces well-formed recombinations. The strand is the genotype (exact, sequential); the bundle is the phenotype (fuzzy, searchable). Production systems use both.

**Measured on real data** (Google Schema-Guided Dialogue, 1.5K dialogues; evals in `tests/eval/`):

- **Next-step prediction** — strand state 0.710 exact-match vs 0.595 for the unordered bundle and 0.653 for last-turn-only: order is real signal (`strand_dialog_eval.py`)
- **Trajectory anomaly** — spliced "hijacked" sessions (every turn plausible, trajectory wrong) detected at AUC 0.748 by bundle-identity margin; the decayed strand adapts too fast, so each view owns its job (`strand_anomaly_eval.py`)
- **Prediction horizon** — chained rollout dies at ~3 turns; terminal-outcome AUC is already 0.867 at turn 2 of 16 and 0.967 by turn 12. Detail is short-range, shape is long-range, and the crossover is measured (`strand_horizon_eval.py`)
- Confidence is honest by construction: kNN outcome frequencies calibrate without a calibration step (94% predicted → 94.7% observed)

**In the loop** — every `CognitiveLoop` turn feeds an `Anticipator` (per-session strand over a cross-session `StrandPredictor`, one-shot Hebbian updates): `loop.anticipate()` returns likely next function-sets for pre-warming and prefetch; `loop.drift()` scores trajectory anomaly (hijack / injection / workflow drift). `begin()` resets the session, never the learning.

**DecisionSpace** (`glyphh/decision`) — the precedent engine: sim across decisions, answered as a fact tree with confidence. Decisions are recorded one-shot as glyphs (attributes + optional ordered events as a strand state); `query()` returns a `FactTree` whose nodes are the matched precedents — each cited with glyph id, hash, situation, facts, and cosine — an outcome distribution weighted by similarity, and a confidence with defined semantics (consensus among sufficient precedent). Below the similarity threshold it declines to answer, citing the nearest case. Validated at 0.889 top-outcome accuracy vs 0.840 baseline, roughly calibrated out of the box (`decision_space_eval.py`).

### HTTP API

Both surfaces ship in `glyphh.server`:

```
POST /v1/strand/sessions                    open a trajectory session
POST /v1/strand/sessions/{id}/events        stream events; each response returns
                                            predicted_next, event_margin, drift
GET/DELETE /v1/strand/sessions/{id}         summary / close (learning is kept)

POST /v1/decide                             {situation, events?} -> outcome
                                            distribution + confidence + fact tree
POST /v1/decide/record                      store a decided case as precedent
GET  /v1/decide/stats                       precedent pool stats
```

State is in-memory; persistence and per-tenant isolation are deployment concerns, not yet in the box.

## MCP Interface

The MCP server is the runtime's control plane — decisions, the model
lifecycle, and every deployed model's own tools behind one
authenticated, metered, self-describing surface:

```
decide(situation, events?)         outcome distribution + confidence + the
                                    fact tree citing every matched precedent
record_decision(situation, outcome) store a decided case as precedent
                                    (one-shot, persisted, shared with /v1/decide)

list_models()                       models loaded in this runtime
deploy_model(package_b64 |          deploy/redeploy a .glyphh package (zip
             package_path |         with manifest.yaml) shipped inline as
             model_dir)             base64, from a server path, or from an
                                    unpacked directory; data/*.jsonl
                                    exemplars encode automatically
seed_model(model_id, exemplars, …)  create + deploy a new model from inline
                                    exemplars — no files needed; calling again
                                    appends exemplars and redeploys
unload_model(model_id)              remove from memory, keep stored glyphs
delete_model(model_id, confirm)     permanently delete a model and its data
```

Decision precedent persists in SQLite (`GLYPHH_DECISIONS_DB`, default
`~/.glyphh/decisions.db`) and survives restarts.

Deployed models expose their OWN tools: a model's encoder.py can export
MCP_TOOLS and handle_mcp_tool, and those tools appear on this surface
automatically — deploy the firewall model and `firewall_scan` shows up;
unload it and the tool disappears. Capabilities belong to models, not
the runtime.

Any MCP client can therefore stand up, seed, and query a glyphh model in
a single conversation. The CLI intentionally keeps only what must work
when the server is down: the interactive shell, `glyphh serve`, and
offline bootstrap (config, auth). Administration is MCP.

Available at `http://localhost:8002/mcp` via Streamable HTTP.

### Connect from Claude Code

Create `.mcp.json` in your project root:

```json
{
  "mcpServers": {
    "glyphh": {
      "type": "http",
      "url": "http://localhost:8002/mcp"
    }
  }
}
```

### Connect from other tools

Any MCP-compatible client can connect to the same endpoint and drive the same runtime: deploy from one tool, query from another.

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install glyphh[runtime]
```

## Quick Start

```bash
# Start the interactive shell (boots the embedded runtime)
glyphh

# Or start as a headless server
glyphh serve

# Or run the self-contained Docker image — SQLite, decisions, and
# deployed models all live on the /data volume; no external services
docker build -t glyphh/runtime .
docker run -p 8002:8002 -v glyphh-data:/data glyphh/runtime

# Scale up: point DATABASE_URL at PostgreSQL + pgvector
# (docker compose up runs the pgvector sidecar for you)
```

Boot sequence: validate config → load license → init database → open the MCP endpoint. Models deploy afterwards, through the surface.

## CLI Commands

The CLI exists only to start things — administration is MCP. The
interactive shell (`glyphh`) boots the embedded runtime and offers
prefixed admin commands:

```
config show           Show current configuration
auth login            Authenticate with Glyphh platform
auth logout           Log out
token create          Mint a runtime API token
```

## Testing

```bash
pip install glyphh[dev]
pytest tests/unit/ -v
```

The test suite covers:
- **Engine** — encoder hierarchy, ops, similarity, edges, property tests
- **Memory (SDK)** — ThoughtGlyphSpace absorb/dedup/recall, atoms, bindings
- **Strand** — permute-bind chains, lossless duplex/transcription, splice, k-mer profiles, predictor, loop anticipation/drift
- **DecisionSpace** — precedent matching, fact-tree citations, insufficient-precedent gate, /v1/decide and /v1/strand routes

## License

Glyphh AI Community License — Copyright (c) 2026 Glyphh AI LLC. All rights reserved.

See [LICENSE](https://github.com/glyphh-ai/glyphh-runtime/blob/main/LICENSE) for full terms. Patent pending (Application No. 63/969,729).
