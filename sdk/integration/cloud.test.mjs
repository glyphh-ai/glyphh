// The TypeScript SDK against a real Ada Cloud (run.sh): a model made, its history imported, learned, decided,
// backtested, tuned, rolled back, exported and imported again; the usage, past the plan's calls a second (RateError)
// and past its month (LimitError); every answer has its contract's required keys.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const sdk = await import(process.env.SDK ?? "../typescript/dist/index.js");
const { Ada, AdaVersionUnknownError, AuthError, BusyError, LimitError, ModelMissingError, NoChangeError, RateError, SpecReadingError } = sdk;
const contract = JSON.parse(readFileSync("/contract/contract.json", "utf8"));

/** The schema's required keys are there (the Python suite validates the full JSON Schemas). */
function shaped(body, name) {
  if (name === "usage_requests") {
    for (const key of ["used", "max", "over", "overage"]) assert.ok(key in body, `usage.requests lacks ${key}`);
    return;
  }
  const schema = contract[name];
  for (const key of schema.required) assert.ok(key in body, `${name} lacks ${key}`);
  if (name === "decision") {
    const decided = body.outputs ? Object.values(body.outputs) : [body];
    for (const d of decided) for (const key of schema.$defs.decided.required) assert.ok(key in d, `decision lacks ${key}`);
  }
}

const SPEC = {
  name: "tickets",
  seed: 5,
  dimension: 2048,
  layers: [
    {
      name: "t",
      segments: [
        {
          name: "s",
          roles: [
            { name: "plan" },
            { name: "channel" },
            { name: "age", numeric_config: { min_value: 0, max_value: 30, bin_width: 3 } },
            { name: "text", text_encoding: "bag_of_words" },
            { name: "owner", security_weight: 0.9 },
            { name: "id", key_part: true, similarity_weight: 0 },
          ],
        },
      ],
    },
  ],
  output: { costs: { refund: { keep: 3 }, keep: { refund: 1 } }, ask_below: 0.6 },
};
const TEXTS = ["charged twice", "card lost", "app slow", "refund late", "login broken", "invoice wrong"];

function kase(i) {
  const plan = ["free", "pro", "team"][i % 3];
  const age = (i * 7) % 31;
  const text = TEXTS[i % TEXTS.length];
  const refund = (plan === "free") !== (age > 20) !== text.includes("twice");
  const what = { plan, channel: ["mail", "chat"][i % 2], age, text, owner: `o${i % 2}`, id: `c${i}` };
  return { data: { t: { s: what } }, outcome: refund ? "refund" : "keep" };
}

function asked(i) {
  const { id, ...what } = kase(i).data.t.s;
  return { t: { s: what } };
}

test("create a model, import, learn, decide, backtest, activate, export", async () => {
  const ada = new Ada({ retryDeadline: 120 }); // a laptop's one or two sync workers can be slower than 10 s a read
  for (const name of ["ts-tickets", "ts-copy"]) await ada.deleteModel(name).catch((e) => assert.ok(e instanceof ModelMissingError));

  const m = await ada.createModel("ts-tickets", SPEC);
  assert.equal(m.created.version, 1);
  const lines = new TextEncoder().encode(Array.from({ length: 200 }, (_, i) => JSON.stringify(kase(i))).join("\n"));
  const seen = [];
  const imported = await m.importFile(lines, { format: "jsonl", onProgress: (j) => seen.push(j.percent) });
  shaped(imported, "job");
  assert.equal(imported.state, "done");
  assert.equal(imported.result.added, 200);
  assert.deepEqual(seen, [...seen].sort((a, b) => a - b));
  const many = await m.recordMany(Array.from({ length: 100 }, (_, i) => kase(200 + i)));
  assert.deepEqual([many.added, many.precedents, many.ids.length], [100, 300, 100]);
  const learned = await m.learn();
  assert.equal(learned.status, "done");
  assert.equal(learned.data.precedents, 300);

  const d = await ada.decide("ts-tickets", asked(3), { include: ["facts"], clearance: 0.5 });
  shaped(d.data, "decision");
  assert.ok(["keep", "refund"].includes(d.outcome) && typeof d.ask === "boolean" && d.facts.length === 1);
  assert.equal(d.status, "done");
  assert.equal(d.version, 1);

  const bt = await m.backtest([{ settings: { word_evidence: 0 }, name: "no word evidence" }], { holdout: { newest: 50 } });
  shaped(bt, "job");
  assert.equal(bt.result.held_out, 50);
  assert.equal(bt.result.candidates.length, 1);
  assert.equal((await m.settings()).settings.word_evidence, 2);
  const live = await m.settings({ word_evidence: 0 }, { note: "fewer asks", backtest: bt.id });
  assert.deepEqual([live.version, live.active, live.job], [2, true, null]);
  assert.deepEqual((await m.versions()).map((v) => [v.version, v.active]), [[1, false], [2, true]]);
  const back = await m.activate(1);
  assert.deepEqual([back.version, back.active], [1, true]);
  const reencoded = await m.settings({ word_weights: false }, { note: "every word as it is" });
  assert.equal(reencoded.version, 3);
  assert.equal(reencoded.job.state, "done");
  const other = structuredClone(SPEC);
  other.layers[0].segments[0].roles[2] = { name: "age", text_encoding: "bag_of_words" };
  await assert.rejects(m.setSpec(other), (e) => e instanceof SpecReadingError && e.status === 422);

  const ex = await m.export();
  shaped(ex, "job");
  assert.ok(ex.download.url);
  const zipped = await ada.download(ex);
  assert.equal(zipped[0], 0x50); // "PK"
  assert.equal(zipped[1], 0x4b);
  const copy = await ada.createModel("ts-copy", await m.spec());
  const copied = await copy.importFile(zipped, { format: "jsonl" });
  assert.equal(copied.result.added, 300);
  const [a, b] = [await m.decide(asked(7)), await copy.decide(asked(7))];
  assert.deepEqual([a.outcome, a.probabilities], [b.outcome, b.probabilities]);

  const q = await m.query(asked(3));
  shaped(q, "result");
  shaped(q.data, "answer");

  // Ada versions (contract 5): the list, a model's Ada, a backtest on another, an upgrade, a rollback, the refusals
  const listed = await ada.ada.versions();
  shaped(listed, "ada_versions");
  for (const v of listed.versions) for (const key of contract.ada_versions.$defs.version.required) assert.ok(key in v, `an Ada version lacks ${key}`);
  const latest = listed.latest_stable;
  assert.equal(listed.contract, 5);
  const beta = listed.versions.find((v) => v.beta && v.open && v.status === "beta")?.name;
  assert.ok(beta, "the registry lists a beta open to new models (ada-1-1-beta)");
  assert.equal(m.created.ada, latest); // made with no ada: the latest stable
  const info = await m.info();
  shaped(info, "model");
  // on the latest stable, the notice is only the quiet one a beta open to try gives: kind beta, to the beta
  assert.deepEqual([info.ada, info.ada_status, info.ada_notice?.kind, info.ada_notice?.to], [latest, "stable", "beta", beta]);
  const before = info.version;
  for (const v of await m.versions()) assert.ok(v.ada === latest && v.kernel);
  assert.equal((await ada.models()).find((x) => x.name === "ts-tickets").ada, latest);
  assert.equal((await m.decide(asked(3))).ada, latest);
  const tried = await m.backtest([], { ada: beta, holdout: { newest: 50 } });
  shaped(tried.result, "backtest");
  assert.deepEqual([tried.result.active.ada, tried.result.candidates.map((c) => c.ada)], [latest, [beta]]);
  const moved = await m.upgrade({ ada: beta, note: `${beta}: on the last 50`, backtest: tried.id });
  shaped(moved, "upgrade");
  assert.deepEqual([moved.ada, moved.from, moved.active, moved.job.state, moved.job.kind], [beta, latest, true, "done", "reencode"]);
  const onBeta = await m.info();
  assert.deepEqual([onBeta.ada, onBeta.ada_status, onBeta.version, onBeta.ada_notice], [beta, "beta", moved.version, null]);
  const versions = await m.versions();
  assert.deepEqual(versions.filter((v) => v.active).map((v) => v.ada), [beta]);
  assert.equal((await m.decide(asked(3))).ada, beta);
  await assert.rejects(m.upgrade({ ada: beta }), NoChangeError);
  await m.activate(before); // the rollback: on the Ada it ran before
  assert.deepEqual([(await m.info()).ada, (await m.info()).version], [latest, before]);
  await assert.rejects(m.upgrade({ ada: "ada-9-9" }), (e) => e instanceof AdaVersionUnknownError && e.status === 422 && e.latest === latest);

  await assert.rejects(new Ada({ key: "glyphh_ak_not_a_key" }).decide("ts-tickets", asked(1)), (e) => e instanceof AuthError && e.status === 401);
  await assert.rejects(ada.model("nope").info(), ModelMissingError);
  const waiting = await ada.write("POST", "/v1/models/ts-copy/imports", { format: "jsonl" });
  assert.equal(waiting.state, "awaiting");
  await assert.rejects(copy.importFile(lines, { format: "jsonl" }), (e) => e instanceof BusyError && e.detail.job === waiting.id);

  const usage = await ada.usage();
  shaped(usage, "usage");
  shaped(usage.requests, "usage_requests");
  assert.deepEqual([usage.plan, usage.precedents.max, usage.requests.max, usage.requests.overage, usage.requests_per_second], ["Basic", 10000, 50000, true, 10]);
  assert.ok(usage.requests.used > 0 && /^\d{4}-\d{2}$/.test(usage.month) && /^\d{4}-\d{2}-01$/.test(usage.resets_at));

  // past the plan's calls a second (Basic: 10): 429 E_RATE with Retry-After, thrown by a client that does not wait;
  // sent 20 at a time, so a slow laptop's reads still pass the rate
  const quick = new Ada({ retryDeadline: 0 });
  await assert.rejects(
    (async () => {
      for (let i = 0; i < 3; i++) await Promise.all(Array.from({ length: 20 }, () => quick.decide("ts-tickets", asked(1))));
    })(),
    (e) => e instanceof RateError && e.status === 429 && e.max === 10 && e.retryAfter >= 1,
  );
  assert.ok((await new Ada({ retryDeadline: 30 }).decide("ts-tickets", asked(1))).outcome); // waiting, it goes on
  // past the plan's month (the second org's, used already): 403 E_LIMIT requests, the plan to upgrade to, when it turns
  const full = new Ada({ key: process.env.ADA_FULL_KEY, retryDeadline: 0 });
  await assert.rejects(full.decide("ts-tickets", asked(1)), (e) => {
    assert.ok(e instanceof LimitError);
    assert.deepEqual([e.status, e.reason, e.plan, e.upgrade, e.max, e.resetsAt], [403, "requests", "Free", "Basic", 5000, usage.resets_at]);
    return true;
  });

  for (const name of ["ts-tickets", "ts-copy"]) assert.equal((await ada.deleteModel(name)).deleted, true);
  await assert.rejects(m.info(), ModelMissingError);
});
