// The kernel's invariants, as tests (the JS mirror of ../../test_kernel.py).
import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { DatabaseSync } from "node:sqlite";

import { Space, Strand, bind, bundle, decide, reencodeStore, roll, sim, spec, SPEC, symbol } from "../dist/index.js";

const tmp = () => mkdtempSync(join(tmpdir(), "ada-kernel-"));
const eq = (a, b) => a.length === b.length && a.every((x, i) => x === b[i]);

test("bind is self-inverse; symbols deterministic and seed-scoped", () => {
  const a = symbol("a"), b = symbol("b");
  assert.ok(eq(bind(bind(a, b), b), a));
  assert.ok(eq(symbol("k", 7), symbol("k", 7)));
  assert.ok(!eq(symbol("k", 7), symbol("k", 8)));
  assert.ok(Math.abs(sim(a, b)) < 0.06);
});

test("bundle resembles parts, is order-free; roll is invertible", () => {
  const parts = ["a", "b", "c", "d"].map((k) => symbol(k));
  assert.ok(sim(bundle(parts.slice(0, 2)), parts[0]) > 0.4);
  assert.ok(eq(bundle(parts), bundle([...parts].reverse())));
  const a = symbol("a");
  assert.ok(eq(roll(roll(a, 3), -3), a));
  assert.ok(Math.abs(sim(roll(a, 1), a)) < 0.06);
});

test("strand order matters", () => {
  const s1 = new Strand([symbol("x"), symbol("y")]);
  const s2 = new Strand([symbol("y"), symbol("x")]);
  assert.ok(sim(s1.state(), s2.state()) < 0.7);
});

test("tie-breaks carry no position bias", () => {
  const space = new Space();
  for (const n of [2, 4, 6]) {
    const base = Object.fromEntries(Array.from({ length: n }, (_, i) => [`a${i}`, `v${i}`]));
    const g = space.encode(base);
    const gap = Math.abs(sim(g, space.encode({ ...base, a0: "X" })) - sim(g, space.encode({ ...base, [`a${n - 1}`]: "X" })));
    assert.ok(gap < 0.06, `n=${n}: bias ${gap}`);
  }
});

test("space answers with receipts; empty space is insufficient; below-bar rows carry no vote", () => {
  const space = new Space();
  space.record({ kind: "db", sev: "high" }, "failover");
  space.record({ kind: "db", sev: "high" }, "failover");
  space.record({ kind: "spike" }, "scale_up");
  const a = space.query({ kind: "db", sev: "high" });
  assert.ok(a.sufficient && a.top === "failover" && a.receipts.every((r) => r.length === 5));
  assert.ok(!new Space().query({ kind: "db" }).sufficient);
  const s = new Space({ minSim: 0.4 });
  s.record({ a: "1", b: "2", c: "3", d: "4" }, "right");
  for (let i = 0; i < 5; i++) s.record({ w: `x${i}`, y: `z${i}` }, "wrong");
  const q = s.query({ a: "1", b: "2", c: "3", d: "9" });
  assert.equal(q.top, "right");
  assert.equal(q.count, 1);
  assert.ok(!("wrong" in q.outcomes));
});

test("events disambiguate by order", () => {
  const e1 = [symbol("up"), symbol("down")], e2 = [symbol("down"), symbol("up")];
  const space = new Space();
  space.record({ kind: "flap" }, "scale_down", { events: e1 });
  space.record({ kind: "flap" }, "scale_up", { events: e2 });
  assert.equal(space.query({ kind: "flap" }, e1).top, "scale_down");
  assert.equal(space.query({ kind: "flap" }, e2).top, "scale_up");
});

test("matches is undilutable", () => {
  const vetoes = new Space();
  const s = { kind: "db", sev: "high" };
  vetoes.record(s, "restart");
  for (let i = 0; i < 20; i++) vetoes.record({ kind: `other${i}` }, "scale_up");
  assert.ok(vetoes.matches(s, "restart") > 0.9);
  assert.equal(vetoes.matches(s, "failover"), 0);
});

test("persistence round-trips, dims are checked, authors kept, refresh sees other writers", () => {
  const dir = tmp();
  const path = join(dir, "shared.db");
  const a = new Space({ author: "agent-a", path });
  const b = new Space({ author: "agent-b", path });
  a.record({ k: "v" }, "out");
  assert.ok(!b.query({ k: "v" }).sufficient);
  assert.equal(b.refresh(), 1);
  b.record({ k: "v" }, "out");
  assert.deepEqual(new Set(b.query({ k: "v" }).receipts.map((r) => r[4])), new Set(["agent-a", "agent-b"]));
  a.close(); b.close();
  assert.equal(new Space({ path }).size, 2);
  new Space({ dim: 2048, path: join(dir, "d.db") }).record({ k: "v" }, "out");
  assert.throws(() => new Space({ dim: 4096, path: join(dir, "d.db") }));
});

test("merge unions by id and persists", () => {
  const dir = tmp();
  const pa = join(dir, "a.db"), pb = join(dir, "b.db");
  const a = new Space({ author: "agent-a", path: pa });
  const shared = a.record({ k: "v" }, "out");
  a.close();
  const b = new Space({ author: "agent-b", path: pb });
  b.record({ k: "v" }, "out", { rid: shared });
  b.record({ x: "y" }, "other");
  b.close();
  const a2 = new Space({ path: pa });
  assert.equal(a2.merge(pb), 1);
  assert.equal(a2.size, 2);
  assert.equal(a2.query({ x: "y" }).receipts[0][4], "agent-b");
  a2.close();
  assert.equal(new Space({ path: pa }).size, 2);
});

test("an encoding-1 store re-encodes on open; events make reencodeStore lossless", () => {
  const dir = tmp();
  const path = join(dir, "v1.db");
  const db = new DatabaseSync(path);
  db.exec("CREATE TABLE precedents (id TEXT PRIMARY KEY, situation TEXT NOT NULL, outcome TEXT NOT NULL," +
    " dim INTEGER NOT NULL, glyph BLOB NOT NULL, author TEXT NOT NULL DEFAULT 'anon')");
  db.prepare("INSERT INTO precedents VALUES (?, ?, ?, ?, ?, ?)")
    .run("r1", '{"task": "x", "constraint": "y"}', "out", 4096, new Uint8Array(4096).fill(1), "a");
  db.close();
  const space = new Space({ path });
  const a = space.query({ task: "x", constraint: "y" });
  assert.ok(a.top === "out" && a.receipts[0][1] > 0.99);
  space.close();
  const check = new DatabaseSync(path);
  assert.equal(check.prepare("SELECT value FROM meta WHERE key='encoding'").get().value, "2");
  check.close();

  const evPath = join(dir, "ev.db");
  const events = [symbol("up"), symbol("down")];
  const s = new Space({ path: evPath });
  s.record({ kind: "flap" }, "scale_down", { events });
  s.close();
  const raw = new DatabaseSync(evPath);
  raw.prepare("UPDATE precedents SET glyph = ?").run(new Uint8Array(4096).fill(1));
  raw.close();
  assert.equal(reencodeStore(evPath), 1);
  const back = new Space({ path: evPath });
  assert.ok(back.query({ kind: "flap" }, events).receipts[0][1] > 0.99);
});

test("answers() reads many true outcomes; evidence() sees past top-k", () => {
  const space = new Space({ minSim: 0.4 });
  const s = { file: "app.py", relation: "imports" };
  for (const m of ["os", "json", "numpy"]) for (const g of ["a", "b", "c"]) { space.author = g; space.record(s, m); }
  assert.ok(space.query(s).confidence < 0.5);
  const got = space.answers(s, { minCount: 3 });
  assert.deepEqual(got.map((e) => e.outcome).sort(), ["json", "numpy", "os"]);
  assert.ok(got.every((e) => e.count === 3 && e.authors.join() === "a,b,c"));
  const crowded = new Space({ k: 3 });
  for (let i = 0; i < 5; i++) crowded.record({ k: "v" }, "crowd");
  crowded.record({ k: "v", near: "miss" }, "rare");
  assert.ok(!("rare" in crowded.query({ k: "v" }).outcomes));
  assert.equal(crowded.evidence({ k: "v" }, "rare").count, 1);
});

const stores = (n = 3, t0 = 10) => {
  const wins = new Space({ minSim: 0.4 }), vetoes = new Space({ minSim: 0.4 });
  for (let i = 0; i < n; i++) wins.record({ task: "deploy", env: "prod" }, "canary", { ts: t0 + i });
  return [wins, vetoes];
};
const S = { task: "deploy", env: "prod" };

test("decide: three gates, newer veto blocks, newer win lifts, corroboration resists a lone saboteur", () => {
  let [wins, vetoes] = stores(3);
  assert.equal(decide(wins, vetoes, S).reason, "reflex");
  assert.equal(decide(...stores(1), S).reason, "uncalibrated");
  assert.equal(decide(wins, vetoes, { task: "cook", env: "home" }).reason, "insufficient");
  vetoes.record(S, "canary", { ts: 20 });
  assert.equal(decide(wins, vetoes, S).reason, "vetoed");
  assert.ok(decide(wins, vetoes, S, { minVetoCount: 2 }).act);
  wins.record(S, "canary", { ts: 30 });
  const d = decide(wins, vetoes, S);
  assert.ok(d.act && d.lifted);
  vetoes.record(S, "canary", { ts: 40 });
  assert.equal(decide(wins, vetoes, S).reason, "vetoed");
  assert.equal(decide(wins, vetoes, S).toJson().answer.count, 4);
});

test("the kernel carries its own spec", () => {
  assert.equal(spec(), SPEC);
  for (const anchor of ["NOTHING UNGRADED", "three gates", "matches()", "Attribute hygiene", "merge("]) {
    assert.ok(SPEC.includes(anchor), anchor);
  }
});
