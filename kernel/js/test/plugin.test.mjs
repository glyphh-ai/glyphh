// The Node plugin against the Python plugin: same MCP replies, same hook
// output, on the same memory. Plus the plugin/lib sync and manifests.
import { test } from "node:test";
import assert from "node:assert/strict";
import { execFileSync, spawnSync } from "node:child_process";
import { cpSync, existsSync, mkdtempSync, readdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";

import { Space } from "../dist/index.js";

const here = dirname(fileURLToPath(import.meta.url));
const JS = join(here, "..");
const REPO = join(JS, "..");
const venv = join(REPO, ".venv", "bin", "python");
const PY = existsSync(venv) ? venv : "python3";

function fixture() {
  const home = mkdtempSync(join(tmpdir(), "ada-plugin-"));
  const mem = join(home, "ada");
  const wins = new Space({ author: "test-agent", path: join(mem, "wins.db") });
  wins.record({ task: "deploy_service", constraint: "canary_required" }, "canary_then_full_rollout", { ts: 1 });
  wins.record({ task: "deploy_service", constraint: "canary_required" }, "canary_then_full_rollout", { ts: 2 });
  wins.record({ person: "chris", topic: "fishing" }, "loves_back_lakes_with_gold_spoon", { ts: 3 });
  wins.record({ task: "long_background_run", constraint: "exceeds_tool_timeout" }, "setsid_nohup_with_status_file", { ts: 4 });
  wins.author = "other-agent";
  wins.record({ kind: "flaky_test", area: "asyncio" }, "use_asyncio_run", { ts: 5 });
  wins.close();
  const vetoes = new Space({ author: "test-agent", path: join(mem, "vetoes.db") });
  vetoes.record({ task: "deploy_service", constraint: "canary_required" }, "big_bang_deploy", { ts: 6 });
  vetoes.record({ task: "long_background_run", constraint: "exceeds_tool_timeout" }, "chained_sleep_polling", { ts: 7 });
  vetoes.close();
  writeFileSync(join(mem, "aliases.json"), JSON.stringify({ angling: ["fishing"] }));
  return home;
}

const copyHome = (home) => {
  const other = mkdtempSync(join(tmpdir(), "ada-plugin-"));
  cpSync(home, other, { recursive: true });
  return other;
};

function hook(lang, name, payload, home) {
  const [cmd, file] = lang === "py"
    ? [PY, join(REPO, "plugin", "hooks", `${name}.py`)]
    : [process.execPath, join(JS, "plugin", "lib", "plugin", "hooks", `${name}.js`)];
  return spawnSync(cmd, [file], {
    input: JSON.stringify(payload), encoding: "utf8", env: { ...process.env, GLYPHH_HOME: home },
  });
}

function mcp(lang, home, messages) {
  const [cmd, file] = lang === "py"
    ? [PY, join(REPO, "plugin", "mcp", "server.py")]
    : [process.execPath, join(JS, "plugin", "lib", "plugin", "mcp", "server.js")];
  const out = execFileSync(cmd, [file], {
    input: messages.map((m) => JSON.stringify(m) + "\n").join(""), encoding: "utf8",
    env: { ...process.env, GLYPHH_HOME: home },
  });
  return out.split("\n").filter(Boolean).map((l) => JSON.parse(l));
}

const tool = (id, name, args = {}) => ({ jsonrpc: "2.0", id, method: "tools/call", params: { name, arguments: args } });
const payload = (reply) => (reply.result?.content ? { isError: reply.result.isError, body: tryJson(reply.result.content[0].text) } : reply);
const tryJson = (t) => { try { return JSON.parse(t); } catch { return t; } };
const scrub = (x) => JSON.parse(JSON.stringify(x, (k, v) => (k === "id" && typeof v === "string" ? "<id>" : k === "memory_dir" ? "<dir>" : v)));

const SIT = { task: "deploy_service", constraint: "canary_required" };
const SESSION = [
  { jsonrpc: "2.0", id: 1, method: "initialize", params: { protocolVersion: "2025-06-18" } },
  { jsonrpc: "2.0", method: "notifications/initialized" },
  { jsonrpc: "2.0", id: 2, method: "tools/list" },
  { jsonrpc: "2.0", id: 3, method: "ping" },
  tool(4, "query", { situation: SIT }),
  tool(5, "check", { situation: SIT, outcome: "big_bang_deploy" }),
  tool(6, "status"),
  tool(7, "query", { situation: { task: "long_background_run", constraint: "exceeds_tool_timeout" } }),
  tool(8, "query", { situation: { nothing: "like_this" } }),
  tool(9, "record", { situation: { task: "x" }, outcome: "y", author: "a" }),
  tool(10, "veto", { situation: SIT, outcome: "canary_then_full_rollout", author: "grader" }),
  tool(11, "query", { situation: SIT }),
  tool(12, "query", {}),
  tool(13, "record", { situation: SIT, outcome: " ", author: "a" }),
  tool(14, "nope"),
  { jsonrpc: "2.0", id: 15, method: "nope/method" },
];

test("MCP: the Node server answers exactly like the Python server", () => {
  const home = fixture();
  const py = mcp("py", copyHome(home), SESSION).map(payload).map(scrub);
  const js = mcp("js", copyHome(home), SESSION).map(payload).map(scrub);
  assert.equal(js.length, py.length);
  py.forEach((p, i) => assert.deepEqual(js[i], p, `reply ${i}`));
  const vetoed = js[10].body;
  assert.equal(vetoed.reason, "vetoed");
  assert.equal(vetoed.act, false);
});

test("MCP: one store, both servers — JS writes, Python reads, and back", () => {
  const home = fixture();
  mcp("js", home, [tool(1, "record", { situation: { task: "cross" }, outcome: "from_js", author: "node" })]);
  const [fromPy] = mcp("py", home, [tool(1, "query", { situation: { task: "cross" } })]).map(payload);
  assert.equal(fromPy.body.top, "from_js");
  assert.equal(fromPy.body.receipts[0].author, "node");
  mcp("py", home, [tool(1, "record", { situation: { task: "cross" }, outcome: "from_js", author: "py" })]);
  const [fromJs] = mcp("js", home, [tool(1, "query", { situation: { task: "cross" } })]).map(payload);
  assert.equal(fromJs.body.count, 2);
});

const PROMPTS = [
  "how should I deploy this service, we need a canary",
  "is chris into fishing?",
  "angling trip with chirs this weekend",
  "should we do a big bang deploy",
  "the test is flaky with asyncio again",
  "long background run keeps hitting the tool timeout — chained sleep polling?",
  "totally unrelated question about gardening",
  "",
];

test("UserPromptSubmit: the Node hook prints exactly what the Python hook prints", () => {
  const home = fixture();
  for (const prompt of PROMPTS) {
    const p = hook("py", "user_prompt", { prompt, session_id: "s" }, home);
    const j = hook("js", "user_prompt", { prompt, session_id: "s" }, home);
    assert.equal(j.status, p.status, prompt);
    assert.equal(j.stdout, p.stdout, `prompt: ${prompt}`);
  }
  assert.match(hook("js", "user_prompt", { prompt: PROMPTS[0] }, home).stdout, /canary_then_full_rollout \(x2\).*VETOED: big_bang_deploy/);
  assert.equal(hook("js", "user_prompt", { prompt: PROMPTS[6] }, home).stdout, "");
});

test("SessionStart: same state injected (kernel path aside)", () => {
  const home = fixture();
  const p = hook("py", "session_start", { session_id: "py-s" }, home);
  const j = hook("js", "session_start", { session_id: "js-s" }, home);
  const dropKernel = (s) => s.replace(/ Kernel: .*?\.(py|js)\./, " Kernel: <k>.");
  assert.equal(j.status, 0);
  assert.equal(dropKernel(j.stdout), dropKernel(p.stdout));
  assert.match(j.stdout, /7 wins|5 wins/);
  assert.match(j.stdout, /Kernel: .*kernel\.js\./);
});

test("Stop: blocks once when nothing was recorded, never loops, passes after a record", () => {
  const home = fixture();
  for (const lang of ["py", "js"]) {
    const session = `stop-${lang}-${Date.now()}`;
    hook(lang, "session_start", { session_id: session }, home);
    const first = hook(lang, "stop_gate", { session_id: session }, home);
    assert.equal(first.status, 2, lang);
    assert.match(first.stderr, /nothing has been recorded/);
    assert.equal(hook(lang, "stop_gate", { session_id: session }, home).status, 0, `${lang}: nags once`);
    assert.equal(hook(lang, "stop_gate", { session_id: session, stop_hook_active: true }, home).status, 0);
    const again = `stop2-${lang}-${Date.now()}`;
    hook(lang, "session_start", { session_id: again }, home);
    const w = new Space({ author: "t", path: join(home, "ada", "wins.db") });
    w.record({ task: `new-${lang}` }, "done");
    w.close();
    assert.equal(hook(lang, "stop_gate", { session_id: again }, home).status, 0, `${lang}: recorded -> pass`);
  }
});

function files(dir, filter = () => true) {
  const out = [];
  const walk = (d) => {
    for (const e of readdirSync(d)) {
      const p = join(d, e);
      if (statSync(p).isDirectory()) walk(p);
      else if (filter(p)) out.push(relative(dir, p));
    }
  };
  walk(dir);
  return out.sort();
}

test("plugin/lib is in sync with dist, and the skill with the Python plugin's", () => {
  const dist = join(JS, "dist"), lib = join(JS, "plugin", "lib");
  const built = files(dist, (p) => !p.endsWith(".d.ts"));
  assert.deepEqual(files(lib), built, "run `npm run build`");
  for (const f of built) assert.equal(readFileSync(join(lib, f), "utf8"), readFileSync(join(dist, f), "utf8"), f);
  assert.equal(readFileSync(join(JS, "plugin", "skills", "glyphh-think", "SKILL.md"), "utf8"),
    readFileSync(join(REPO, "plugin", "skills", "glyphh-think", "SKILL.md"), "utf8"));
});

test("manifests point at files that exist", () => {
  const root = join(JS, "plugin");
  const mcpJson = JSON.parse(readFileSync(join(root, ".mcp.json"), "utf8"));
  assert.equal(JSON.parse(readFileSync(join(root, ".claude-plugin", "plugin.json"), "utf8")).name, "ada");
  const args = mcpJson.mcpServers.ada.args.map((a) => a.replace("${CLAUDE_PLUGIN_ROOT}", root));
  assert.ok(existsSync(args[0]), args[0]);
  const hooks = JSON.parse(readFileSync(join(root, "hooks", "hooks.json"), "utf8")).hooks;
  for (const event of ["SessionStart", "UserPromptSubmit", "Stop"]) {
    const cmd = hooks[event][0].hooks[0].command;
    const file = cmd.match(/"\$\{CLAUDE_PLUGIN_ROOT\}\/(.+?)"/)[1];
    assert.ok(existsSync(join(root, file)), `${event}: ${file}`);
  }
});
