// The client against the contract's fixtures (contract/fixtures.json, as a real Ada Cloud answered them): every
// request as Ada expects it, every answer read right, every refusal its typed AdaError; jobs waited for with their
// progress; what may be sent again, sent again, and nothing else.
import assert from "node:assert/strict";
import { mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import {
  Ada,
  AdaError,
  AdaTimeoutError,
  AuthError,
  BusyError,
  DEFAULT_URL,
  FewRolesError,
  HeadLostError,
  JobFailedError,
  LimitError,
  ModelMissingError,
  NoHeadError,
  NotCommittedError,
  RateError,
  ReadOnlyError,
  RunLostError,
  SpecError,
  SpecReadingError,
  retryAfter,
  AdaBetaClosedError,
  AdaVersionDeprecatedError,
  AdaVersionError,
  AdaVersionRetiredError,
  AdaVersionUnavailableError,
  AdaVersionUnknownError,
  ClientTooOldError,
  NoChangeError,
  SUPPORTED_ADA,
  SUPPORTED_CONTRACT,
} from "../dist/index.js";

const contract = JSON.parse(readFileSync(new URL("../../../contract/contract.json", import.meta.url), "utf8"));
const fixtures = JSON.parse(readFileSync(new URL("../../../contract/fixtures.json", import.meta.url), "utf8"));
const byName = (name) => fixtures.cases.find((c) => c.name === name);
const answered = (name) => {
  const c = byName(name);
  return [c.response.status, c.response.body, c.response.headers ?? {}];
};
const URL_ = "https://ada.test";

/** No real waiting: the client's sleeps recorded, its clock moved by them. */
function fakeClock() {
  const slept = [];
  let now = 0;
  return { slept, clock: { now: () => now, sleep: async (s) => { slept.push(s); now += s; } } };
}

/** Ada, answering from a script of [status, body] or [status, body, headers]; an Error is thrown. */
function fake(...answers) {
  const options = answers.length && !Array.isArray(answers.at(-1)) && !(answers.at(-1) instanceof Error) ? answers.pop() : {};
  const calls = [];
  const transport = async (method, url, headers, body) => {
    let sent = body;
    if (typeof body === "string") sent = JSON.parse(body);
    calls.push({ method, url, path: url.replace(URL_, ""), headers, body: sent });
    const next = answers.shift();
    if (next instanceof Error) throw next;
    const [status, answer, got] = next;
    const text = answer instanceof Uint8Array ? new TextDecoder().decode(answer) : JSON.stringify(answer);
    const out = { status, body: text, headers: got ?? {} };
    if (answer instanceof Uint8Array) out.raw = answer;
    return out;
  };
  return { ada: new Ada({ url: `${URL_}/`, key: "glyphh_ak_test", transport, ...options }), calls };
}

function job(state, kind = "learn", more = {}) {
  const body = {
    id: "j1",
    model: "tickets",
    kind,
    state,
    percent: state === "done" ? 100 : 0,
    args: {},
    result: null,
    error: null,
    created_at: "2026-10-22 04:18:43+00:00",
    started_at: null,
    finished_at: null,
    made_by: "u1",
    ...more,
  };
  for (const key of contract.job.required) assert.ok(key in body);
  return body;
}

test("the contract is 5, the SDK's, and every fixture's refusal is a code it names", () => {
  assert.equal(contract.contract, 5);
  assert.equal(fixtures.contract, 5);
  assert.equal(SUPPORTED_CONTRACT, 5);
  const names = ["decision", "usage", "job", "answer", "result", "error", "ada_versions", "model", "models", "versions", "upgrade", "backtest"];
  for (const name of names) assert.ok(contract[name], name);
  for (const c of fixtures.cases) {
    if (c.response.status >= 400) assert.ok(contract.codes.includes(c.response.body.error.code), c.name);
    if (c.schema) for (const key of contract[c.schema].required) assert.ok(key in c.response.body, `${c.name}: ${key}`);
    if (c.result_schema) for (const key of contract[c.result_schema].required) assert.ok(key in c.response.body.result, `${c.name}: result.${key}`);
  }
  const listed = byName("the Ada versions").response.body.versions.map((v) => v.name);
  assert.deepEqual([...SUPPORTED_ADA].sort(), listed.sort());
});

test("a model is made from its spec, written once", async () => {
  const c = byName("a model made from its spec");
  const { ada, calls } = fake(answered(c.name), [200, { models: [{ name: "tickets" }] }], [200, { name: "tickets", deleted: true }], [200, { version: 1, spec: { a: 1 } }]);
  const m = await ada.createModel(c.request.body.name, c.request.body.spec);
  assert.deepEqual(m.created, c.response.body);
  const t = ada.model("tickets");
  assert.deepEqual([calls[0].method, calls[0].path, calls[0].body], ["POST", "/v1/models", c.request.body]);
  assert.equal(calls[0].headers.authorization, "Bearer glyphh_ak_test");
  assert.equal(calls[0].headers["idempotency-key"].length, 32);
  assert.deepEqual(await ada.models(), [{ name: "tickets" }]);
  assert.equal((await t.delete()).deleted, true);
  assert.deepEqual(await t.spec(), { a: 1 });
  assert.deepEqual(calls.map((k) => [k.method, k.path]).slice(1), [["GET", "/v1/models"], ["DELETE", "/v1/models/tickets?confirm=tickets"], ["GET", "/v1/models/tickets"]]);
});

test("a decision from /v1/decide reads as 3.0's Result too", async () => {
  const c = byName("a decision");
  const { ada, calls } = fake(answered(c.name));
  const d = await ada.decide("tickets", c.request.body.data, { include: ["facts"], clearance: 0.5 });
  assert.deepEqual(calls[0].body, c.request.body);
  assert.equal(calls[0].path, "/v1/decide");
  const body = c.response.body;
  assert.deepEqual([d.outcome, d.probabilities, d.ask, d.model, d.version, d.ada], [body.outcome, body.probabilities, false, "tickets", body.version, "ada-1-0"]);
  assert.deepEqual(d.receipts, body.receipts);
  assert.deepEqual(d.facts, body.facts);
  assert.equal(d.status, "done");
  assert.deepEqual(d.data, body);
});

test("a decision that asks, and one of several outputs", async () => {
  const asks = byName("a decision that asks a person");
  const several = byName("a decision of several outputs");
  const { ada, calls } = fake(answered(asks.name), answered(several.name));
  const d = await ada.model("tickets").decide(asks.request.body.data);
  assert.equal(d.ask, true);
  assert.equal(d.outcome, asks.response.body.outcome);
  const both = await ada.decide("routing", several.request.body.data, { outputs: ["team", "urgent"] });
  assert.deepEqual(Object.keys(both.outputs).sort(), ["team", "urgent"]);
  assert.equal(both.outputs.team.outcome, "billing");
  assert.equal(both.ask, false);
  assert.equal(both.outcome, null);
  assert.deepEqual(calls[1].body, several.request.body);
});

test("an import goes to its upload link, then is waited for with progress", async () => {
  const done = answered("an import, done");
  const running = [200, { ...done[1], state: "running", percent: 40, result: null }];
  const { slept, clock } = fakeClock();
  const { ada, calls } = fake(answered("an import, waiting for its file"), answered("the import's file, sent to its upload link"), running, done, { clock });
  const dir = mkdtempSync(join(tmpdir(), "ada-"));
  const file = join(dir, "history.jsonl");
  writeFileSync(file, '{"data": {}, "outcome": "keep"}\n');
  const seen = [];
  const j = await ada.model("tickets").importFile(file, { onProgress: (x) => seen.push([x.state, x.percent]) });
  assert.equal(j.state, "done");
  assert.deepEqual(j.result, done[1].result);
  assert.deepEqual(seen, [["queued", 0], ["running", 40], ["done", 100]]);
  const upload = byName("an import, waiting for its file").response.body.upload.url;
  assert.deepEqual(calls.map((k) => [k.method, k.url]), [["POST", `${URL_}/v1/models/tickets/imports`], ["PUT", upload], ["GET", `${URL_}/v1/jobs/${done[1].id}`], ["GET", `${URL_}/v1/jobs/${done[1].id}`]]);
  assert.deepEqual(calls[0].body, { format: "jsonl", partial: false, learn: true });
  assert.ok(calls[1].body instanceof Uint8Array);
  assert.equal(new TextDecoder().decode(calls[1].body), '{"data": {}, "outcome": "keep"}\n');
  assert.equal(calls[1].headers.authorization, undefined);
  assert.deepEqual(slept, [0.25, 0.5]);
});

test("an import of bytes says its format and mapping; without one it is refused before a request", async () => {
  const { ada, calls } = fake(answered("an import, waiting for its file"), answered("the import's file, sent to its upload link"));
  const bytes = new TextEncoder().encode("product,team\napp,billing\n");
  const j = await ada.model("routing").importFile(bytes, { format: "csv", mapping: { product: "t.w.product", team: "outcome.team" }, partial: true, learn: false, wait: false });
  assert.equal(j.state, "queued");
  assert.deepEqual(calls[0].body, { format: "csv", mapping: { product: "t.w.product", team: "outcome.team" }, partial: true, learn: false });
  await assert.rejects(ada.model("routing").importFile(bytes), (e) => e.code === "E_INVALID");
  await assert.rejects(ada.model("routing").importFile("cases.txt"), (e) => e.code === "E_INVALID");
  assert.equal(calls.length, 2);
});

test("an export is waited for, and its file downloaded by its link", async () => {
  const done = answered("an export, done, with its download link");
  const { clock } = fakeClock();
  const zip = new Uint8Array([0x50, 0x4b, 3, 4]);
  const { ada, calls } = fake([202, job("queued", "export", { args: { format: "ada_sqlite" } })], done, [200, zip], { clock });
  const dir = mkdtempSync(join(tmpdir(), "ada-"));
  const j = await ada.model("tickets").export({ format: "ada_sqlite", to: join(dir, "t.zip") });
  assert.deepEqual(j.download, done[1].download);
  assert.deepEqual(new Uint8Array(readFileSync(join(dir, "t.zip"))), zip);
  assert.deepEqual(calls[0].body, { format: "ada_sqlite" });
  assert.equal(calls[2].url, done[1].download.url);
  assert.equal(calls[2].headers.authorization, undefined);
  await assert.rejects(ada.download(job("running", "export")), (e) => e.code === "E_INVALID");
});

test("a backtest, and tuning by versions", async () => {
  const bt = answered("a backtest, done");
  const { clock } = fakeClock();
  const { ada, calls } = fake(
    [202, job("queued", "backtest")],
    bt,
    [200, { version: 1, settings: { k: 15 } }],
    answered("a settings change, live at once"),
    [200, { version: 3, active: false, job: job("queued", "reencode") }],
    [200, job("done", "reencode", { result: { store: "made" } })],
    [200, { versions: [{ version: 1, active: false }, { version: 2, active: true }] }],
    [200, { version: 1, active: true, job: null }],
    [200, { version: 4, active: true, job: null }],
    { clock },
  );
  const m = ada.model("tickets");
  const j = await m.backtest([{ settings: { word_evidence: 0 }, name: "no word evidence" }], { holdout: { newest: 40 } });
  assert.equal(j.result.candidates[0].accuracy, bt[1].result.candidates[0].accuracy);
  assert.deepEqual(calls[0].body, { candidates: [{ settings: { word_evidence: 0 }, name: "no word evidence" }], holdout: { newest: 40 } });
  assert.deepEqual(await m.settings(), { version: 1, settings: { k: 15 } });
  assert.deepEqual(await m.settings({ word_evidence: 0 }, { note: "why", backtest: j.id }), { version: 2, active: true, job: null });
  assert.deepEqual(calls[3].body, { changes: { word_evidence: 0 }, note: "why", backtest: j.id });
  const changed = await m.settings({ word_weights: false });
  assert.equal(changed.job.state, "done");
  assert.deepEqual((await m.versions()).map((v) => v.version), [1, 2]);
  assert.equal((await m.activate(1)).active, true);
  assert.equal((await m.setSpec({ name: "tickets" }, { note: "a cost" })).version, 4);
  assert.deepEqual(calls.map((k) => [k.method, k.path]), [
    ["POST", "/v1/models/tickets/backtest"],
    ["GET", "/v1/jobs/j1"],
    ["GET", "/v1/models/tickets/settings"],
    ["PATCH", "/v1/models/tickets/settings"],
    ["PATCH", "/v1/models/tickets/settings"],
    ["GET", "/v1/jobs/j1"],
    ["GET", "/v1/models/tickets/versions"],
    ["POST", "/v1/models/tickets/versions/1/activate"],
    ["PUT", "/v1/models/tickets/spec"],
  ]);
  for (const k of calls) if (k.method !== "GET") assert.ok(k.headers["idempotency-key"]);
});

test("a job that fails, and one that outlasts the wait", async () => {
  const { clock } = fakeClock();
  const failed = job("failed", "learn", { error: { code: "E_SPEC", message: "Too few graded precedents.", path: "output" } });
  const f = fake([202, job("queued")], [200, failed], { clock });
  await assert.rejects(f.ada.model("tickets").learnJob(), (e) => {
    assert.ok(e instanceof JobFailedError);
    assert.deepEqual([e.code, e.message, e.detail.path, e.detail.job.state], ["E_SPEC", "Too few graded precedents.", "output", "failed"]);
    return true;
  });
  const late = fake(...Array(20).fill([200, job("running", "learn", { percent: 10 })]), { clock });
  await assert.rejects(late.ada.wait("j1", { timeout: 5 }), (e) => e instanceof AdaTimeoutError && e.detail.job === "j1");
  const c = fake([202, job("queued", "calibrate")]);
  assert.equal((await c.ada.model("tickets").calibrate({ wait: false })).state, "queued");
});

test("recordMany sends a thousand a request, each made once", async () => {
  const got = (n, total) => [200, { ids: Array.from({ length: n }, (_, k) => `i${k}`), added: n, replaced: 0, precedents: total }];
  const { ada, calls } = fake(got(1000, 1000), got(1000, 2000), got(500, 2500));
  const cases = Array.from({ length: 2500 }, (_, i) => ({ data: { n: i }, outcome: "keep" }));
  const total = await ada.model("tickets").recordMany(cases, { idempotencyKey: "load-1" });
  assert.deepEqual([total.added, total.precedents, total.ids.length], [2500, 2500, 2500]);
  assert.deepEqual(calls.map((k) => k.body.cases.length), [1000, 1000, 500]);
  assert.deepEqual(calls.map((k) => k.headers["idempotency-key"]), ["load-1", "load-1.1", "load-1.2"]);
  const g = fake([200, { id: "a1" }], [200, { id: "a1" }]);
  await g.ada.model("tickets").grade("a1", "keep", { output: "team" });
  await g.ada.model("tickets").forget("a1");
  assert.deepEqual(g.calls.map((k) => [k.method, k.path]), [["POST", "/v1/models/tickets/grade"], ["DELETE", "/v1/models/tickets/precedents/a1"]]);
  assert.deepEqual(g.calls[0].body, { id: "a1", value: "keep", output: "team" });
});

for (const [name, error] of [
  ["a wrong key", AuthError],
  ["a model that is not there", ModelMissingError],
  ["a spec that reads a role another way", SpecReadingError],
  ["cases past the plan's precedents", LimitError],
  ["past the plan's month of requests", LimitError],
  ["past the plan's calls a second", RateError],
  ["a big model asked with few of its roles", FewRolesError],
  ["another import open on the model", BusyError],
]) {
  test(`a refusal is its typed error: ${name}`, async () => {
    const c = byName(name);
    const { ada, calls } = fake(answered(name), { retryDeadline: 0 });
    await assert.rejects(ada.call(c.request.method, c.request.path, c.request.body ?? undefined), (e) => {
      const sent = c.response.body.error;
      assert.ok(e instanceof error && e instanceof AdaError);
      assert.deepEqual([e.code, e.status, e.message, e.traceId], [sent.code, c.response.status, sent.message, sent.trace_id]);
      const { code, message, ...detail } = sent;
      assert.deepEqual(e.detail, detail);
      if (error === SpecReadingError) assert.ok(e instanceof SpecError);
      if (name === "cases past the plan's precedents") {
        assert.deepEqual([e.reason, e.used, e.max, e.upgrade, e.resetsAt], ["precedents", 995, 1000, undefined, undefined]);
      }
      if (name === "past the plan's month of requests") {
        assert.deepEqual([e.reason, e.plan, e.upgrade, e.max], ["requests", "Free", "Basic", 5000]);
        assert.deepEqual([e.used, e.resetsAt], [sent.used, sent.resets_at]);
      }
      if (error === RateError) {
        assert.equal(e.retryAfter, Number(c.response.headers["retry-after"]));
        assert.deepEqual([e.retryAfter, e.max], [sent.retry_after, 5]);
      }
      return true;
    });
    assert.equal(calls.length, 1);
  });
}

test("an answer that is not json, no code, and Ada unreachable", async () => {
  const broken = new Ada({ url: URL_, key: "k", retryDeadline: 0, transport: async () => ({ status: 502, body: "<html>" }) });
  await assert.rejects(broken.models(), (e) => e.code === "E_RUNTIME" && e.status === 502);
  const gone = new Ada({ url: URL_, key: "k", retryDeadline: 0, transport: async () => { throw new Error("no route"); } });
  await assert.rejects(gone.models(), (e) => e.code === "E_UNREACHABLE");
  for (const [status, code] of [[401, "E_AUTH"], [402, "E_LIMIT"], [404, "E_NOT_FOUND"], [429, "E_RATE"]]) {
    const a = new Ada({ url: URL_, key: "k", retryDeadline: 0, transport: async () => ({ status, body: "{}" }) });
    await assert.rejects(a.models(), (e) => e.code === code);
  }
});

test("a write carrying its key is sent again with the same key and body", async () => {
  const { slept, clock } = fakeClock();
  const { ada, calls } = fake(
    [503, { error: { code: "E_UNAVAILABLE", message: "Ada is unreachable for a moment: try again." } }],
    [504, { error: { code: "E_TIMEOUT", message: "No answer within 30 seconds: try again." } }],
    [200, { ids: ["a"], added: 1, replaced: 0, precedents: 1 }],
    { clock },
  );
  await ada.model("tickets").recordMany([{ data: { a: 1 } }]);
  assert.equal(calls.length, 3);
  assert.equal(new Set(calls.map((k) => k.headers["idempotency-key"])).size, 1);
  assert.equal(new Set(calls.map((k) => JSON.stringify(k.body))).size, 1);
  assert.equal(slept.length, 2);
});

test("a read is sent again, and a 3.0 write without a key is not", async () => {
  const { slept, clock } = fakeClock();
  const q = byName("a query through POST /v1/runs, as SDK 3.0 calls it");
  const r = fake(new Error("reset"), [502, {}], answered(q.name), { clock });
  assert.deepEqual((await r.ada.model("tickets").query(q.request.body.inputs.data)).data, q.response.body.data);
  assert.equal(r.calls.length, 3);
  assert.ok(slept[0] >= 0.125 && slept[0] <= 0.25 && slept[1] >= 0.25 && slept[1] <= 0.5);
  const w = fake(new Error("reset"), { clock });
  await assert.rejects(w.ada.model("tickets").record({ a: 1 }, "keep"), (e) => e.code === "E_UNREACHABLE");
  assert.equal(w.calls.length, 1);
});

test("too many requests waits as Retry-After says, then throws", async () => {
  const { slept, clock } = fakeClock();
  const rate = [429, { error: { code: "E_RATE", message: "Too many requests a second." } }, { "Retry-After": "3" }];
  const ok = fake(rate, answered("a decision"), { clock });
  assert.ok((await ok.ada.decide("tickets", {})).outcome);
  assert.deepEqual(slept, [3]);
  const no = fake(...Array(5).fill(rate), { clock, retryDeadline: 7 });
  await assert.rejects(no.ada.model("tickets").record({ a: 1 }), (e) => e instanceof RateError && e.retryAfter === 3);
  assert.equal(no.calls.length, 3);
});

test("3.0's calls name their functions, and a long learn is waited for", async () => {
  const q = byName("a query through POST /v1/runs, as SDK 3.0 calls it");
  const body = q.response.body;
  const { ada, calls } = fake(...Array(6).fill([200, body]));
  const m = ada.model("tickets");
  await m.query(q.request.body.inputs.data);
  await m.record({ a: 1 }, "keep");
  await m.record({ a: 1 }, undefined, { outcomes: { team: "billing" }, ts: 5 });
  await m.facts({ a: 1 }, { top: 2, clearance: 0.5 });
  await m.probabilities({ a: 1 }, { output: "team" });
  await m.call("decide", { data: { a: 1 } });
  assert.deepEqual(
    calls.map((k) => [k.body.function, k.body.inputs, k.body.clearance]),
    [
      ["query", q.request.body.inputs, undefined],
      ["record", { data: { a: 1 }, outcome: "keep" }, undefined],
      ["record", { data: { a: 1 }, outcomes: { team: "billing" }, ts: 5 }, undefined],
      ["facts", { data: { a: 1 }, top: 2 }, 0.5],
      ["probabilities", { data: { a: 1 }, output: "team" }, undefined],
      ["decide", { data: { a: 1 } }, undefined],
    ],
  );
  const { clock } = fakeClock();
  const still = { ...body, function: "learn", data: { job: job("running", "learn", { percent: 60 }) } };
  const l = fake([200, still], [200, job("done", "learn", { result: { precedents: 12, tau: 0.4 } })], { clock });
  const r = await l.ada.model("tickets").learn({ sample: 50 });
  assert.deepEqual(r.data, { precedents: 12, tau: 0.4 });
  assert.deepEqual(l.calls[0].body.inputs, { sample: 50 });
});

test("the URL defaults to Ada Cloud, and the key comes from the environment", async () => {
  for (const name of ["GLYPHH_ADA_URL", "GLYPHH_RUNTIME_URL", "GLYPHH_API_KEY", "GLYPHH_RUNTIME_KEY"]) delete process.env[name];
  assert.throws(() => new Ada(), (e) => e.code === "E_CONFIG" && /GLYPHH_API_KEY/.test(e.message));
  process.env.GLYPHH_RUNTIME_KEY = "glyphh_rk_old";
  assert.equal(new Ada().url, DEFAULT_URL);
  assert.equal(DEFAULT_URL, "https://ada.glyphh.ai");
  process.env.GLYPHH_API_KEY = "glyphh_ak_env";
  process.env.GLYPHH_RUNTIME_URL = "https://old.example/";
  assert.equal(new Ada().url, "https://old.example");
  process.env.GLYPHH_ADA_URL = "http://ada:8080/";
  assert.equal(new Ada().url, "http://ada:8080");
});

test("usage is the server's shape: the month, its reset, precedents, requests and calls a second", async () => {
  const sent = byName("the org's usage").response.body;
  const { ada, calls } = fake(answered("the org's usage"));
  const usage = await ada.usage();
  assert.equal(calls[0].path, "/v1/usage");
  assert.deepEqual(usage, sent);
  assert.deepEqual([usage.plan, usage.precedents.max, usage.requests.max, usage.requests.over, usage.requests.overage, usage.requests_per_second], ["Free", 1000, 5000, 0, false, 5]);
  assert.match(usage.month, /^\d{4}-\d{2}$/);
  assert.match(usage.resets_at, /^\d{4}-\d{2}-01$/);
  assert.deepEqual([usage.ada.latest_stable, usage.ada.versions.map((v) => [v.name, v.models])], ["ada-1-0", [["ada-1-1-beta", 0], ["ada-1-0", 3]]]);
});

test("a rate refusal without the header waits as its body says", async () => {
  const { slept, clock } = fakeClock();
  const body = { error: { code: "E_RATE", message: "Your plan allows 5 Ada calls a second: try again in 2 seconds.", retry_after: 2, reason: "rate", max: 5 } };
  const { ada } = fake([429, body], answered("a decision"), { clock });
  assert.ok((await ada.decide("tickets", {})).outcome);
  assert.deepEqual(slept, [2]);
});

// a self-hosted cluster's refusals and read-your-writes, kept from 3.1 (nothing of them reaches the cloud)

const NO_HEAD = [503, { error: { code: "E_NO_HEAD", message: "The cluster has no head." } }, { "Retry-After": "2" }];
const DONE = { run_id: "r1", model: "incidents", version: 1, function: "record", status: "done", data: { id: "a1" }, step: null, prompt: null, seconds: 0.1 };

test("a cluster's no head is retried, and its seq sent back", async () => {
  const { slept, clock } = fakeClock();
  const { ada, calls } = fake(NO_HEAD, NO_HEAD, [200, DONE, { "Rrotor-Cluster-Seq": "1042" }], [200, { models: [] }], { clock });
  assert.deepEqual((await ada.model("incidents").record({ a: 1 })).data, { id: "a1" });
  assert.deepEqual(slept, [2, 2]);
  await ada.models();
  assert.equal(ada.clusterSeq, 1042);
  assert.equal(calls.at(-1).headers["rrotor-min-seq"], "1042");
  const many = fake(...Array(6).fill(NO_HEAD), { clock, retryDeadline: 9 });
  await assert.rejects(many.ada.model("incidents").record({ a: 1 }), NoHeadError);
  assert.equal(many.calls.length, 5);
  const off = fake([200, DONE, { "Rrotor-Cluster-Seq": "9" }], [200, DONE], { readYourWrites: false });
  await off.ada.model("incidents").record({ a: 1 });
  await off.ada.model("incidents").record({ a: 1 });
  assert.equal(off.calls[1].headers["rrotor-min-seq"], undefined);
});

for (const [code, status, error] of [["E_HEAD_LOST", 503, HeadLostError], ["E_NOT_COMMITTED", 503, NotCommittedError], ["E_RUN_LOST", 410, RunLostError]]) {
  test(`a cluster's refusal is typed and not sent again: ${code}`, async () => {
    const { slept, clock } = fakeClock();
    const { ada, calls } = fake([status, { error: { code, message: "x" } }], { clock });
    await assert.rejects(ada.model("incidents").record({ a: 1 }), error);
    assert.equal(calls.length, 1);
    assert.deepEqual(slept, []);
  });
}

test("a reading function that wrote, and a record past a runtime's cap", async () => {
  const failed = { ...DONE, function: "query", status: "failed", data: { code: "E_READ_ONLY", reason: "query writes" } };
  const { ada } = fake([200, failed], [200, { ...DONE, data: { status: "limit_exceeded", indexed: false, message: "cap", cap: 5000 } }]);
  await assert.rejects(ada.model("incidents").query({ a: 1 }), (e) => e instanceof ReadOnlyError && e.detail.run_id === "r1");
  assert.equal((await ada.model("incidents").record({ a: 1 })).limit_exceeded, true);
});

test("Retry-After as a date, and a transport that answers no headers", async () => {
  assert.equal(retryAfter("Wed, 21 Oct 2015 07:28:00 GMT"), 0);
  assert.equal(retryAfter("1.5"), 1.5);
  assert.equal(retryAfter("soon"), undefined);
  const { ada } = fake([200, { models: [] }]);
  assert.deepEqual(await ada.models(), []);
  assert.equal(ada.clusterSeq, 0);
});

// Ada versions (contract 5)

test("the Ada versions are listed, with the latest stable", async () => {
  const c = byName("the Ada versions");
  const { ada, calls } = fake(answered(c.name), answered(c.name));
  const found = await ada.ada.versions();
  assert.deepEqual(calls.map((k) => [k.method, k.path]), [["GET", "/v1/ada"]]);
  assert.deepEqual([found.latest_stable, found.contract, found.versions.length], ["ada-1-0", 5, 2]);
  const [beta, stable] = found.versions;
  assert.deepEqual([beta.name, beta.kernel, beta.status, beta.beta, beta.open, beta.changes_answers, beta.models], ["ada-1-1-beta", "3.13.0", "beta", true, true, true, 1]);
  assert.deepEqual([stable.name, stable.status, stable.deprecated, stable.ends], ["ada-1-0", "stable", null, null]);
  assert.equal(await ada.ada.latestStable(), "ada-1-0");
});

test("a model carries its Ada on its info and on each version", async () => {
  const info = byName("a model and its Ada");
  const listed = byName("the org's models, each with its Ada");
  const versions = byName("a model's versions, each with its Ada");
  const { ada, calls } = fake(answered(info.name), answered(listed.name), answered(versions.name));
  const m = ada.model("tickets");
  const i = await m.info();
  assert.deepEqual([i.name, i.version, i.ada, i.ada_status, i.ada_notice], ["tickets", 4, "ada-1-1-beta", "beta", null]);
  assert.deepEqual((await ada.models()).map((x) => [x.name, x.ada]), [["routing", "ada-1-0"], ["tickets", "ada-1-1-beta"]]);
  assert.deepEqual((await m.versions()).map((v) => [v.version, v.active, v.ada, v.kernel]), [[3, false, "ada-1-0", "3.12.2"], [4, true, "ada-1-1-beta", "3.13.0"]]);
  assert.deepEqual(calls.map((k) => k.path), ["/v1/models/tickets", "/v1/models", "/v1/models/tickets/versions"]);
});

test("a model is made on the latest stable unless an Ada is named", async () => {
  const beta = byName("a model made on a beta Ada");
  const { ada, calls } = fake(answered("a model made from its spec"), answered(beta.name));
  const first = await ada.createModel("routing", { name: "routing" });
  assert.equal("ada" in calls[0].body, false);
  assert.equal(first.created.ada, "ada-1-0");
  const sent = beta.request.body;
  const made = await ada.createModel(sent.name, sent.spec, { ada: "ada-1-1-beta" });
  assert.deepEqual(calls[1].body, sent);
  assert.deepEqual([made.created.ada, made.created.ada_status, made.created.ada_notice], ["ada-1-1-beta", "beta", null]);
  // on the latest stable, the quiet notice: a beta is open to try
  assert.deepEqual([first.created.ada_notice.kind, first.created.ada_notice.to], ["beta", "ada-1-1-beta"]);
});

test("a backtest against another Ada, then an upgrade waited for, then a rollback", async () => {
  const [, bt] = answered("a backtest against another Ada, done");
  const up = answered("an upgrade to another Ada");
  const done = { ...up[1].job, state: "done", percent: 100, result: { version: 4, ada: "ada-1-1-beta" } };
  const { slept, clock } = fakeClock();
  const { ada, calls } = fake(
    [202, { ...bt, state: "queued", percent: 0, result: null }],
    [200, bt],
    up,
    [200, { ...done, state: "running", percent: 50, result: null }],
    [200, done],
    [200, { version: 3, active: true, job: null }],
    { clock },
  );
  const m = ada.model("tickets");
  const j = await m.backtest([], { ada: "ada-1-1-beta", holdout: { newest: 200 } });
  assert.deepEqual(calls[0].body, { candidates: [], ada: "ada-1-1-beta", holdout: { newest: 200 } });
  assert.deepEqual([j.result.active.ada, j.result.candidates[0].ada], ["ada-1-0", "ada-1-1-beta"]);
  const seen = [];
  const moved = await m.upgrade({ ada: "ada-1-1-beta", note: "2 fewer wrong", backtest: j.id, onProgress: (x) => seen.push(x.state) });
  assert.deepEqual(calls[2].body, { ada: "ada-1-1-beta", note: "2 fewer wrong", backtest: j.id });
  assert.deepEqual([moved.version, moved.ada, moved.from, moved.active, moved.job.kind], [4, "ada-1-1-beta", "ada-1-0", true, "reencode"]);
  assert.deepEqual(seen, ["queued", "running", "done"]);
  assert.equal((await m.activate(3)).active, true);
  assert.deepEqual(calls.map((k) => [k.method, k.path]), [
    ["POST", "/v1/models/tickets/backtest"],
    ["GET", `/v1/jobs/${bt.id}`],
    ["POST", "/v1/models/tickets/upgrade"],
    ["GET", `/v1/jobs/${up[1].job.id}`],
    ["GET", `/v1/jobs/${up[1].job.id}`],
    ["POST", "/v1/models/tickets/versions/3/activate"],
  ]);
  assert.ok(slept.length >= 2);
  const later = fake(up);
  const queued = await later.ada.model("tickets").upgrade({ wait: false });
  assert.deepEqual([later.calls[0].body, queued.active, queued.job.state], [{}, false, "queued"]);
});

for (const [name, error] of [
  ["an Ada that does not exist", AdaVersionUnknownError],
  ["a retired Ada", AdaVersionRetiredError],
  ["a deprecated Ada as an upgrade's target", AdaVersionDeprecatedError],
  ["a beta closed to new models", AdaBetaClosedError],
  ["an Ada this deploy does not have", AdaVersionUnavailableError],
  ["an upgrade to the Ada the model runs", NoChangeError],
]) {
  test(`an Ada refusal is typed, names the latest stable, and is never sent again: ${name}`, async () => {
    const c = byName(name);
    const { slept, clock } = fakeClock();
    const { ada, calls } = fake(answered(name), { clock });
    await assert.rejects(ada.call(c.request.method, c.request.path, c.request.body, false, "k1"), (e) => {
      const sent = c.response.body.error;
      assert.ok(e instanceof error && e instanceof AdaError);
      assert.deepEqual([e.code, e.status, e.message], [sent.code, c.response.status, sent.message]);
      if (e instanceof AdaVersionError) assert.deepEqual([e.ada, e.latest], [sent.ada, sent.latest]);
      return true;
    });
    assert.equal(calls.length, 1);
    assert.deepEqual(slept, []);
  });
}

test("a deprecated or moved model warns once per client and notice; a beta's notice never does", async () => {
  const deprecated = byName("a model on a deprecated Ada");
  const moved = byName("a decision just after its model was moved off a retired Ada");
  const warned = [];
  const { ada } = fake(answered(deprecated.name), answered(deprecated.name), answered(moved.name), answered("a model and its Ada"), { onWarning: (w) => warned.push(w) });
  const info = await ada.model("claims").info();
  await ada.model("claims").info();
  const d = await ada.decide("claims", moved.request.body.data);
  await ada.model("tickets").info();
  const said = (c) => c.response.headers["glyphh-ada-notice"].split(": ");
  assert.deepEqual(warned, [
    { kind: "deprecated", message: said(deprecated).slice(1).join(": ") },
    { kind: "moved", message: said(moved).slice(1).join(": ") },
  ]);
  assert.deepEqual([info.ada_notice.kind, info.ada_notice.to, info.ada_notice.ends], ["deprecated", "ada-1-1", "2027-04-21"]);
  assert.deepEqual([d.ada, d.version], ["ada-1-1", 3]);
  // the default handler is console.warn
  const original = console.warn;
  const printed = [];
  console.warn = (...args) => printed.push(args.join(" "));
  try {
    await fake(answered(deprecated.name)).ada.model("claims").info();
  } finally {
    console.warn = original;
  }
  assert.ok(printed[0].startsWith("Glyphh Ada: deprecated: claims runs ada-1-0"));
});

test("a server of a newer contract is refused clearly, never read", async () => {
  const newer = { "Glyphh-Contract": "6" };
  for (const answer of [[200, { models: [] }, newer], [503, { error: { code: "E_UNAVAILABLE", message: "x" } }, newer]]) {
    const { ada, calls } = fake(answer);
    await assert.rejects(ada.models(), (e) => {
      assert.ok(e instanceof ClientTooOldError);
      assert.deepEqual([e.code, e.contract, e.supported], ["E_CLIENT_TOO_OLD", 6, 5]);
      assert.match(e.message, /contract 6.*npm install @glyphh-ai\/glyphh@latest/);
      return true;
    });
    assert.equal(calls.length, 1);
  }
  const { ada } = fake([200, { ...byName("the Ada versions").response.body, contract: 7 }]);
  await assert.rejects(ada.ada.versions(), ClientTooOldError);
  const fine = fake([200, { models: [] }, { "glyphh-contract": "5" }], [200, { models: [] }, { "glyphh-contract": "4" }], [200, { models: [] }]);
  for (let i = 0; i < 3; i++) assert.deepEqual(await fine.ada.models(), []); // its own, an older one, or none: read
});
