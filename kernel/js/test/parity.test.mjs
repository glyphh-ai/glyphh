// The JS kernel against the Python kernel: same vectors, same stores,
// same answers. Needs the repo's Python (../.venv, else python3 + numpy).
import { test } from "node:test";
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { existsSync, mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

import { SPEC, Space, Strand, bind, bundle, decide, roll, sim, symbol } from "../dist/index.js";

const here = dirname(fileURLToPath(import.meta.url));
const venv = join(here, "..", "..", ".venv", "bin", "python");
const PY = existsSync(venv) ? venv : "python3";
const py = (...args) => execFileSync(PY, [join(here, "parity_ref.py"), ...args], { encoding: "utf8" });
const h = (g) => createHash("sha256").update(Buffer.from(g.buffer, g.byteOffset, g.byteLength)).digest("hex");

const KEYS = ["a", "b", "attr:task", "val:deploy", "é", "\u{1F642}", "", "x".repeat(300)];
const SITUATIONS = [
  { task: "deploy", env: "prod" },
  { b: "2", a: "1", c: "3", d: "4" },
  { "é": "ü", Z: "z", a: "\u{1F642}" },
  Object.fromEntries(Array.from({ length: 9 }, (_, i) => [`k${i}`, `v${i}`])),
  { only: "one" },
];

test("SPEC is the Python kernel's SPEC, verbatim", () => {
  const pySpec = JSON.parse(execFileSync(PY, ["-c",
    "import sys, json; sys.path.insert(0, sys.argv[1]); import glyphh_kernel as k; print(json.dumps(k.SPEC))",
    join(here, "..", "..")], { encoding: "utf8" }));
  assert.equal(SPEC, pySpec);
});

test("every primitive is bit-identical to Python", () => {
  const ref = JSON.parse(py("vectors"));
  for (const key of KEYS) {
    for (const [seed, dim] of [[42, 4096], [7, 1000], [42, 64]]) {
      assert.equal(h(symbol(key, seed, dim)), ref.symbols[`${seed}|${dim}|${key}`], `symbol ${seed}|${dim}|${key}`);
    }
  }
  const [a, b, c, d, e] = ["a", "b", "c", "d", "e"].map((k) => symbol(k));
  assert.equal(h(bind(a, b)), ref.ops.bind);
  for (const k of [1, 3, -5, 4096, 4099]) assert.equal(h(roll(a, k)), ref.ops[`roll${k}`], `roll ${k}`);
  assert.equal(h(bundle([a, b])), ref.ops.bundle2);
  assert.equal(h(bundle([a, b, c])), ref.ops.bundle3);
  assert.equal(h(bundle([a, b, c, d])), ref.ops.bundle4);
  assert.equal(h(bundle([d, c, b, a])), ref.ops.bundle4rev);
  assert.equal(h(bundle([a, b, c, d, e])), ref.ops.bundle5);
  assert.equal(h(bundle([a, a, b, b])), ref.ops.bundle_dup);
  for (const decay of [0.7, 0.2, 1.0]) {
    assert.equal(h(new Strand([a, b, c, d]).state(decay)), ref.ops[`strand${decay === 1 ? "1.0" : decay}`], `strand ${decay}`);
  }
  assert.equal(h(new Strand([a]).state()), ref.ops.strand1);
  const space = new Space();
  const ev = [symbol("up"), symbol("down"), symbol("up")];
  SITUATIONS.forEach((s, i) => {
    assert.equal(h(space.encode(s)), ref.encode[String(i)], `encode ${i}`);
    assert.equal(h(space.encode(s, ev)), ref.encode[`${i}+ev`], `encode ${i}+events`);
  });
  assert.equal(sim(a, b), ref.sims.ab);
  assert.equal(sim(space.encode(SITUATIONS[0]), space.encode({ task: "deploy", env: "dev" })), ref.sims.enc01);
});

function writeJs(root) {
  const ev = [symbol("up"), symbol("down")];
  const wins = new Space({ minSim: 0.4, author: "py-a", path: join(root, "jswins.db") });
  const vetoes = new Space({ minSim: 0.4, author: "py-b", path: join(root, "jsvetoes.db") });
  const base = { task: "deploy", env: "prod" };
  for (let i = 0; i < 3; i++) wins.record(base, "canary", { ts: 10 + i });
  wins.record({ task: "deploy", env: "dev" }, "yolo", { ts: 5 });
  wins.record({ kind: "flap" }, "scale_down", { events: ev, ts: 6 });
  for (const m of ["os", "json", "numpy"]) for (const g of ["a", "b", "c"]) {
    wins.author = g;
    wins.record({ file: "app.py", rel: "imports" }, m, { ts: 7 });
  }
  vetoes.record(base, "canary", { ts: 20 });
  wins.close(); vetoes.close();
}

function readJs(root, prefix) {
  const wins = new Space({ minSim: 0.4, path: join(root, `${prefix}wins.db`) });
  const vetoes = new Space({ minSim: 0.4, path: join(root, `${prefix}vetoes.db`) });
  const base = { task: "deploy", env: "prod" };
  const ev = [symbol("up"), symbol("down")];
  const strip = (j) => { for (const r of j.receipts) delete r.id; return j; };
  const out = {
    glyphs: wins["glyphs"].map(h).sort(),
    query: strip(wins.query(base).toJson()),
    decide: (() => { const d = decide(wins, vetoes, base).toJson(); return d; })(),
    answers: wins.answers({ file: "app.py", rel: "imports" }, { minCount: 3 }).map((e) => e.toJson()),
    flap: strip(wins.query({ kind: "flap" }, ev).toJson()),
    matches: vetoes.matches(base, "canary"),
  };
  wins.close(); vetoes.close();
  return out;
}

const norm = (x) => JSON.parse(JSON.stringify(x, (k, v) => (k === "id" ? undefined : v)));

test("stores cross between languages: Python writes, JS reads; JS writes, Python reads", () => {
  const root = mkdtempSync(join(tmpdir(), "ada-parity-"));
  py("write", root);
  writeJs(root);
  const pyOnPy = JSON.parse(py("read", root));
  const jsOnPy = readJs(root, "");
  const pyOnJs = JSON.parse(py("read", root, "js"));
  const jsOnJs = readJs(root, "js");
  for (const [name, got] of [["js reading python's store", jsOnPy], ["python reading js's store", pyOnJs], ["js reading js's store", jsOnJs]]) {
    assert.deepEqual(got.glyphs, pyOnPy.glyphs, `${name}: glyphs`);
    assert.deepEqual(norm(got.query), norm(pyOnPy.query), `${name}: query`);
    assert.deepEqual(norm(got.decide), norm(pyOnPy.decide), `${name}: decide`);
    assert.deepEqual(got.answers, pyOnPy.answers, `${name}: answers`);
    assert.deepEqual(norm(got.flap), norm(pyOnPy.flap), `${name}: events`);
    assert.equal(got.matches, pyOnPy.matches, `${name}: matches`);
  }
});
