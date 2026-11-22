// The org's hosted bots over the Glyphh API: every request as the server's /v1 bots routes take it, on the same API
// key Ada takes, every answer read right, a run waited for until it ends or asks, refusals typed.
import assert from "node:assert/strict";
import { test } from "node:test";
import { Ada, AdaTimeoutError, ConflictError, DEFAULT_API_URL, HostedBots, InvalidError } from "../dist/index.js";

const URL_ = "https://api.test";
const BOT = { id: "b1", slug: "inbox-cat", name: "Inbox Cat", summary: "Answers the mail", spec: {}, last_run: null };
const ASKS = { question: "send: send the reply. Yes?", options: ["yes", "no"], step: "send", approval: true };
const run = (status = "queued", more = {}) => ({ id: "r1", bot_slug: "inbox-cat", status, input: "x", output: "", error: "", log: [], data: {}, question: null, ...more });

function fakeClock() {
  let now = 0;
  return { now: () => now, sleep: async (s) => { now += s; } };
}

/** The Glyphh API, answering from a script of [status, body]. */
function fake(...answers) {
  const calls = [];
  const transport = async (method, url, headers, body) => {
    calls.push({ method, url, path: url.replace(URL_, ""), headers, body: typeof body === "string" ? JSON.parse(body) : body });
    const [status, answer] = answers.shift();
    return { status, body: JSON.stringify(answer), headers: {} };
  };
  return { transport, calls, bots: new HostedBots({ url: URL_, key: "glyphh_ak_test", transport, retryDeadline: 0, clock: fakeClock() }) };
}

test("bots are listed, searched and read on the Ada key", async () => {
  const { bots, calls } = fake([200, { bots: [BOT] }], [200, { bots: [] }], [200, BOT], [200, { gates: { worth: { precedents: 3 } } }]);
  assert.deepEqual((await bots.list()).map((b) => b.slug), ["inbox-cat"]);
  assert.deepEqual(await bots.search("mail cat"), []);
  assert.equal((await bots.bot("inbox-cat").info()).name, "Inbox Cat");
  assert.deepEqual(await bots.bot("inbox-cat").gates(), { worth: { precedents: 3 } });
  assert.equal(calls[0].headers.authorization, "Bearer glyphh_ak_test");
  assert.deepEqual(calls.map((c) => c.path), ["/v1/bots", "/v1/bots?q=mail%20cat", "/v1/bots/inbox-cat", "/v1/bots/inbox-cat/gates"]);
});

test("a run is started, waited for, answered and carried on", async () => {
  const { bots, calls } = fake(
    [202, run()],
    [200, run("running")],
    [200, run("dispatched")],
    [200, run("needs_input", { question: ASKS })],
    [202, run("queued")],
    [200, run("done", { output: "Sent." })],
  );
  const seen = [];
  const asked = await bots.bot("inbox-cat").run("lunch?", { wait: true, onProgress: (r) => seen.push(r.status) });
  assert.deepEqual(seen, ["queued", "running", "dispatched", "needs_input"]);
  assert.equal(asked.question.approval, true);
  assert.deepEqual(calls[0].body, { input: "lunch?" });
  assert.equal(calls[0].headers["idempotency-key"], undefined);
  const done = await bots.answer(asked, "yes", { wait: true });
  assert.equal(done.output, "Sent.");
  assert.equal(calls[4].path, "/v1/bot-runs/r1/answer");
  assert.deepEqual(calls[4].body, { answer: "yes" });
});

test("runs, the approvals queue, cancel, wrong and templates", async () => {
  const template = { slug: "news-brief", name: "News brief", summary: "", apps: ["slack"], tools: [], gates: [] };
  const { bots, calls } = fake(
    [200, { runs: [run("done")] }],
    [200, run("done")],
    [200, { runs: [run("needs_input", { question: ASKS })] }],
    [200, run("failed", { error: "cancelled" })],
    [200, { gate: "worth", said: "skip", now: "answer" }],
    [200, { templates: [template] }],
    [200, template],
    [201, BOT],
  );
  assert.equal((await bots.runs("inbox-cat")).length, 1);
  assert.equal((await bots.getRun("r1")).status, "done");
  assert.equal((await bots.approvals())[0].question.step, "send");
  assert.equal((await bots.cancel("r1")).error, "cancelled");
  await bots.wrong("r1", "answer", { gate: "worth" });
  assert.deepEqual(calls[4].body, { outcome: "answer", gate: "worth" });
  assert.equal((await bots.templates("news"))[0].slug, "news-brief");
  assert.deepEqual((await bots.template("news-brief")).apps, ["slack"]);
  assert.equal((await bots.install("news-brief", { name: "Morning news" })).slug, "inbox-cat");
  assert.deepEqual(calls.map((c) => `${c.method} ${c.path}`), [
    "GET /v1/bots/inbox-cat/runs",
    "GET /v1/bot-runs/r1",
    "GET /v1/bot-approvals",
    "POST /v1/bot-runs/r1/cancel",
    "POST /v1/bot-runs/r1/wrong",
    "GET /v1/bot-templates?q=news",
    "GET /v1/bot-templates/news-brief",
    "POST /v1/bot-templates/news-brief/install",
  ]);
  assert.deepEqual(calls[7].body, { name: "Morning news" });
});

test("refusals are typed and a long run times out", async () => {
  const conflict = { error: { code: "E_CONFLICT", message: "The bot has a run going." } };
  const misfit = { error: { code: "E_INVALID", message: "Answer with one of yes, no.", options: ["yes", "no"] } };
  const { bots } = fake([409, conflict], [422, misfit], ...Array.from({ length: 40 }, () => [200, run("running")]));
  await assert.rejects(bots.run("inbox-cat"), ConflictError);
  await assert.rejects(bots.answer("r1", "maybe"), InvalidError);
  await assert.rejects(bots.wait("r1", { timeout: 10 }), (e) => e instanceof AdaTimeoutError && e.detail.run_id === "r1");
});

test("the address defaults to the Glyphh API, and Ada hands its key over", async () => {
  assert.equal(new HostedBots({ key: "glyphh_ak_x" }).url, DEFAULT_API_URL);
  assert.equal(DEFAULT_API_URL, "https://api.glyphh.ai");
  const { transport, calls } = fake([200, { bots: [] }]);
  const ada = new Ada({ url: "https://ada.test", key: "glyphh_ak_mine", transport });
  assert.deepEqual(await ada.bots.list(), []);
  assert.equal(calls[0].url, `${DEFAULT_API_URL}/v1/bots`);
  assert.equal(calls[0].headers.authorization, "Bearer glyphh_ak_mine");
});
