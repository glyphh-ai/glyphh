// The runtime client against a local rrotor's fixtures (contract/runtime-fixtures.json, written from rrotor's code):
// every request as rrotor expects it, every refusal its typed RrotorError; reads sent again while rrotor is
// unreachable, writes never. No network: a fake transport answers.
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdtempSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import {
  Ada,
  AdaError,
  CliDeniedError,
  DEFAULT_RUNTIME_URL,
  LocalOnlyError,
  ManifestError,
  NoHeadError,
  NotHeadError,
  ProgramMissingError,
  RrotorAuthError,
  RrotorError,
  RunStateError,
  Runtime,
  ScheduleMissingError,
} from "../dist/index.js";

const contract = JSON.parse(readFileSync(new URL("../../../contract/runtime.json", import.meta.url), "utf8"));
const fixtures = JSON.parse(readFileSync(new URL("../../../contract/runtime-fixtures.json", import.meta.url), "utf8"));
const byName = (name) => fixtures.cases.find((c) => c.name === name);
const answered = (name) => [byName(name).response.status, byName(name).response.body];
const URL_ = "http://127.0.0.1:7777";
const TOKEN = "local-token-test";

function fakeClock() {
  const slept = [];
  let now = 0;
  return { slept, clock: { now: () => now, sleep: async (s) => { slept.push(s); now += s; } } };
}

function runtime(answers, options = {}) {
  const calls = [];
  const transport = async (method, url, headers, body) => {
    calls.push({ method, path: url.slice(URL_.length), headers, body: headers["content-type"] === "application/json" ? JSON.parse(body) : body });
    const next = answers.shift();
    if (next instanceof Error) throw next;
    const [status, content, got = {}] = next;
    return { status, body: typeof content === "string" ? content : JSON.stringify(content), headers: got };
  };
  return { rt: new Runtime({ url: `${URL_}/`, token: TOKEN, transport, ...options }), calls };
}

function asked(call, name) {
  const c = byName(name);
  assert.equal(`${call.method} ${call.path}`, `${c.request.method} ${c.request.path}`, name);
  assert.equal(call.headers.authorization, `Bearer ${TOKEN}`);
}

test("the fixtures name only codes the contract lists, and the Ada contract is apart", () => {
  assert.equal(contract.runtime, 1);
  assert.equal(fixtures.runtime, 1);
  for (const c of fixtures.cases) {
    assert.ok(contract[c.schema], c.name);
    if (c.response.status >= 400) assert.ok(contract.codes.includes(c.response.body.error.code), c.name);
  }
  assert.equal(DEFAULT_RUNTIME_URL, URL_);
});

test("no token anywhere is said plainly, at the first call", async () => {
  const rt = new Runtime({ transport: async () => assert.fail("no request without a token"), tokenFile: join(tmpdir(), "no-such-rrotor-token") });
  await assert.rejects(rt.programs(), (e) => e instanceof RrotorError && e.code === "E_CONFIG" && /rrotor skill/.test(e.message));
  const dir = mkdtempSync(join(tmpdir(), "rrotor-token-"));
  writeFileSync(join(dir, "token"), "from-the-file\n");
  const seen = [];
  const kept = new Runtime({ tokenFile: join(dir, "token"), transport: async (m, u, h) => (seen.push(h.authorization), { status: 200, body: '{"programs": []}' }) });
  assert.deepEqual(await kept.programs(), []);
  assert.deepEqual(seen, ["Bearer from-the-file"]);
});

test("programs are listed, a CLI among them", async () => {
  const { rt, calls } = runtime([answered("the programs"), answered("the programs")]);
  const [sales, gh] = await rt.programs();
  asked(calls[0], "the programs");
  assert.equal(sales.kind, "program");
  assert.deepEqual(sales.functions.start.approvals, ["write"]);
  assert.equal(gh.kind, "cli");
  await assert.rejects(rt.program("nope"), ProgramMissingError);
});

test("a folder is deployed as a git bundle of its commit; a repo by its full commit", async () => {
  const folder = mkdtempSync(join(tmpdir(), "daily_sales-"));
  const git = (...args) => execFileSync("git", ["-C", folder, ...args], { encoding: "utf8" });
  git("init", "-q");
  git("config", "user.email", "t@example.com");
  git("config", "user.name", "t");
  writeFileSync(join(folder, "glyphh.json"), '{"name": "daily_sales", "functions": {"start": {}}}');
  writeFileSync(join(folder, "program.py"), "def start(ctx, inputs):\n    return None\n");
  git("add", ".");
  git("commit", "-qm", "first");
  const sha = git("rev-parse", "HEAD").trim();
  const { rt, calls } = runtime([answered("a deploy from a bundle"), answered("a deploy from a repo"), answered("a manifest refused")]);
  const made = await rt.deploy({ path: folder });
  assert.equal(`${calls[0].method} ${calls[0].path}`, "POST /v1/programs/deploy");
  assert.equal(calls[0].body.commit, sha);
  assert.ok(Buffer.from(calls[0].body.bundle, "base64").toString("latin1").startsWith("# v"));
  assert.equal(made.version, 1);
  const again = await rt.deploy({ repo: "acme/daily-sales", commit: "4a2d1e0f9c8b7a6d5e4f3c2b1a0d9e8f7c6b5a4d" });
  asked(calls[1], "a deploy from a repo");
  assert.equal(calls[1].body.token, undefined);
  assert.equal(again.version, 2);
  await assert.rejects(rt.deploy({ bundle: new Uint8Array([1, 2]), commit: "5b3e2f1a0d9c8b7a6e5f4d3c2b1a0f9e8d7c6b5a" }), ManifestError);
  await assert.rejects(rt.deploy({ repo: "acme/daily-sales", commit: "main" }), (e) => e.code === "E_COMMIT");
  const bare = mkdtempSync(join(tmpdir(), "bare-"));
  execFileSync("git", ["-C", bare, "init", "-q"]);
  mkdirSync(join(bare, "x"));
  writeFileSync(join(bare, "x", "README"), "x");
  execFileSync("git", ["-C", bare, "add", "."]);
  execFileSync("git", ["-C", bare, "-c", "user.email=t@e.com", "-c", "user.name=t", "commit", "-qm", "none"]);
  await assert.rejects(rt.deploy({ path: bare }), (e) => e.code === "E_MANIFEST");
  await assert.rejects(rt.deploy({ path: join(bare, "nowhere") }), (e) => e.code === "E_GIT");
});

test("a call waits for approval, then the person's decision ends it", async () => {
  const { rt, calls } = runtime([answered("a call that waits for approval"), answered("the runs waiting for approval"), answered("the run approved, done")]);
  const run = await rt.call("daily_sales", "start", { day: "2026-10-14" });
  asked(calls[0], "a call that waits for approval");
  assert.deepEqual(calls[0].body, byName("a call that waits for approval").request.body);
  assert.equal(run.status, "needs_approval");
  assert.equal(run.step, "write");
  const [waiting] = await rt.approvals();
  assert.equal(waiting.run_id, run.run_id);
  const done = await rt.approve(run.run_id);
  asked(calls[2], "the run approved, done");
  assert.deepEqual(calls[2].body, { answer: { approved: true } });
  assert.equal(done.data.written, true);
});

test("a run's status, log and cancel", async () => {
  const { rt, calls } = runtime([answered("a run's status"), answered("a run's log"), answered("a run cancelled")]);
  assert.equal((await rt.run("6f0e3c1a-2b4d-4e8f-9a1b-3c5d7e9f1a2b")).caller, "claude");
  assert.equal((await rt.log("6f0e3c1a-2b4d-4e8f-9a1b-3c5d7e9f1a2b")).at(-1).message, "written");
  assert.equal((await rt.cancel("0b1c2d3e-4f5a-4b6c-8d7e-9f0a1b2c3d4e")).status, "cancelled");
  asked(calls[2], "a run cancelled");
});

test("secrets are names only, never a value back", async () => {
  const { rt, calls } = runtime([answered("a program's secrets"), answered("a secret set"), answered("a secret deleted")]);
  assert.deepEqual(await rt.secrets("github"), [{ name: "GH_TOKEN", declared: true, set: false }]);
  const kept = await rt.setSecret("github", "GH_TOKEN", "ghp_shh");
  asked(calls[1], "a secret set");
  assert.deepEqual(calls[1].body, { value: "ghp_shh" });
  assert.ok(kept.set && !JSON.stringify(kept).includes("ghp_shh"));
  assert.equal((await rt.deleteSecret("github", "GH_TOKEN")).set, false);
  asked(calls[2], "a secret deleted");
  await assert.rejects(rt.setSecret("github", "GH_TOKEN", 42), RrotorError);
});

test("schedules are listed, paused and resumed", async () => {
  const { rt, calls } = runtime([answered("the schedules"), answered("a schedule paused"), answered("a schedule resumed")]);
  assert.equal((await rt.schedules())[0].id, "daily_sales/each_morning");
  const paused = await rt.pauseSchedule("daily_sales", "each_morning");
  asked(calls[1], "a schedule paused");
  assert.equal(paused.next_at, null);
  assert.equal((await rt.resumeSchedule("daily_sales", "each_morning")).paused, false);
  asked(calls[2], "a schedule resumed");
});

test("CLIs are listed and a command runs or waits for approval", async () => {
  const { rt, calls } = runtime([answered("the CLIs"), answered("a CLI command, done"), answered("a CLI command that waits for approval")]);
  assert.equal((await rt.clis())[0].install.source, "url");
  const done = await rt.runCli("github", ["pr", "list", "--limit", 2]);
  asked(calls[1], "a CLI command, done");
  assert.deepEqual(calls[1].body, { args: ["pr", "list", "--limit", "2"] });
  assert.equal(done.data.exit_code, 0);
  const waiting = await rt.runCli("github", ["pr", "merge", "41"], { files: { "notes.txt": "hi" } });
  assert.equal(waiting.status, "needs_approval");
  assert.deepEqual(calls[2].body.files, { "notes.txt": "hi" });
});

test("the licence is read and a key handed in as the body", async () => {
  const { rt, calls } = runtime([answered("the licence, Community"), answered("a licence key handed in")]);
  assert.equal((await rt.licence()).community, true);
  const got = await rt.setLicence("  payload.signature\n");
  assert.equal(calls[1].body, "payload.signature");
  assert.equal(calls[1].headers["content-type"], "text/plain");
  assert.equal(got.licence.tier, "pro");
  assert.equal(got.kept, true);
});

for (const [name, error] of [
  ["a wrong token", RrotorAuthError],
  ["a program that is not there", ProgramMissingError],
  ["arguments a CLI does not allow", CliDeniedError],
  ["a run that is not waiting", RunStateError],
  ["a schedule that is not there", ScheduleMissingError],
  ["a licence on a self-hosted rrotor", LocalOnlyError],
  ["a secret set on a follower", NotHeadError],
]) {
  test(`a refusal is its typed error: ${name}`, async () => {
    const c = byName(name);
    const { rt } = runtime([answered(name)]);
    await assert.rejects(rt.request(c.request.method, c.request.path, c.request.method === "GET" ? undefined : c.request.body), (e) => {
      assert.ok(e instanceof error && e instanceof RrotorError && e instanceof AdaError);
      assert.equal(e.code, c.response.body.error.code);
      assert.equal(e.status, c.response.status);
      if (error === NotHeadError) assert.equal(e.head, "rrotor-0");
      return true;
    });
  });
}

test("rrotor unreachable: a read is sent again, a write never", async () => {
  const { slept, clock } = fakeClock();
  const read = runtime([new Error("ECONNREFUSED"), answered("the programs")], { clock });
  assert.equal((await read.rt.programs()).length, 2);
  assert.equal(read.calls.length, 2);
  assert.equal(slept.length, 1);
  const write = runtime([new Error("ECONNREFUSED")], { clock });
  await assert.rejects(write.rt.call("daily_sales"), (e) => e.code === "E_UNREACHABLE" && /127\.0\.0\.1:7777/.test(e.message));
  assert.equal(write.calls.length, 1);
  const odd = runtime([[500, "not json"]], { clock });
  await assert.rejects(odd.rt.call("daily_sales"), (e) => e.message === "rrotor answered 500");
});

test("a cluster's no head is waited out and its seq sent back", async () => {
  const { slept, clock } = fakeClock();
  const noHead = [503, { error: { code: "E_NO_HEAD", message: "The cluster has no head." } }, { "Retry-After": "2" }];
  const { rt, calls } = runtime([noHead, [...answered("a call that waits for approval"), { "Rrotor-Cluster-Seq": "77" }], answered("the programs")], { clock });
  assert.equal((await rt.call("daily_sales", "start", { day: "2026-10-14" })).status, "needs_approval");
  assert.deepEqual(slept, [2]);
  await rt.programs();
  assert.equal(rt.clusterSeq, 77);
  assert.equal(calls.at(-1).headers["rrotor-min-seq"], "77");
  const spent = runtime([noHead, noHead, noHead], { clock, retryDeadline: 3 });
  await assert.rejects(spent.rt.programs(), NoHeadError);
});

test("Ada Cloud is untouched beside it", async () => {
  const ada = new Ada({ url: "https://ada.test", key: "glyphh_ak_test", transport: async () => ({ status: 200, body: '{"models": []}' }) });
  assert.deepEqual(await ada.models(), []);
});
