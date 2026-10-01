# Ada in TypeScript

A **bit-identical** port of `../glyphh_kernel.py` (encoding 2), plus the
Ada plugin's MCP server and hooks, for Node. No dependencies at runtime:
`node:crypto` and the built-in `node:sqlite` (Node ≥ 22.13).

Every `symbol`, `bind`, `bundle`, `roll`, `Strand` state and `Space`
encoding is the same vector, byte for byte, as the Python kernel makes.
Both kernels read and write the same SQLite store files. The parity
tests hold the two to that by running the Python kernel alongside.

```
src/kernel.ts            the kernel: primitives, Strand, Space, decide, reencodeStore, SPEC
src/pyjson.ts            Python-exact text: json.dumps, round(), code-point order
src/plugin/mcp/server.ts the MCP server (tools: query, record, veto, check, status)
src/plugin/hooks/*.ts    SessionStart, UserPromptSubmit, Stop
dist/                    compiled output (committed; Node runs it directly)
plugin/                  a self-contained Claude Code plugin root running on node
test/                    kernel, parity and plugin tests
```

## Use the kernel

```js
import { Space, decide, symbol, bind, bundle, sim } from "./dist/index.js";

const wins = new Space({ path: "wins.db" });
const vetoes = new Space({ path: "vetoes.db" });
const d = decide(wins, vetoes, { task: "deploy", env: "prod" });
if (d.act) { /* reflex: d.outcome */ } else { /* consult; see d.reason */ }
```

The API mirrors Python's, with two differences:
- Names are camelCase: `minSim`, `minCount`, `minVetoCount`, `toJson()`.
- Options are passed as objects: `record(situation, outcome, { events, ts })`.

Read `spec()` first. It is the Python kernel's SPEC, verbatim.

## Use the plugin

`plugin/` is a drop-in for the Python plugin (`../plugin`):
- **Same identity:** the plugin name `ada`, the MCP server `ada`, and so the same tool names.
- **Same memory:** `$GLYPHH_HOME/ada`, else `~/.glyphh/ada`.
- **Same output:** identical tool replies and hook output.
- **Runtime:** its commands run on `node` instead of `python3`.

Install only one of the two plugins at a time. To try it locally, run `claude --plugin-dir js/plugin`.

## Build and test

```bash
npm install          # typescript + @types/node (dev only)
npm run build        # tsc -> dist/, then sync dist/ -> plugin/lib and the skill
npm test             # node --test test/
```

The parity tests call `../.venv/bin/python` (else `python3`) with numpy installed.

## Known differences

- **Numbers in stored situations.** JavaScript can't tell `3.0` from `3`, so a situation recorded from JS stores `3` where Python would store `3.0`. Both encode as the symbol `val:3`, so matching is unaffected.
- **Aggregates in the last floating-point bit.** Float sums (confidence, support) can differ in the last bit. Both sides round to 4 places with Python's round-half-even rule, and the parity tests compare the rounded values.
