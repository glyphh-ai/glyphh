/**
 * The Ada memory as an MCP server (stdio, newline-delimited JSON-RPC
 * 2.0), in Node — a port of plugin/mcp/server.py with the same tools,
 * schemas and outputs, on the same store ($GLYPHH_HOME/ada, else
 * ~/.glyphh/ada). The spaces load once and refresh() before every read,
 * so rows other sessions (or the Python server) wrote always count.
 * Situations may nest, and every read takes a weights tree; `facts`
 * returns the weighted read as fact trees.
 */

import { homedir } from "node:os";
import { join } from "node:path";
import { createInterface } from "node:readline";

import { decide, encode, Space, type Situation, type Weights } from "../../kernel.js";
import { pyRound } from "../../pyjson.js";

const PROTOCOL = "2025-06-18";
const MIN_SIM = 0.4, K = 7;
const ACT_CONFIDENCE = 0.5; // the skill's bar for acting on a top answer
const CALIBRATED_COUNT = 3; // below this, precedent is a cited reminder

class ValueError extends Error {
  override name = "ValueError";
}

export function memoryDir(): string {
  return join(process.env.GLYPHH_HOME || join(homedir(), ".glyphh"), "ada");
}

/** wins + vetoes, opened lazily so the server starts even if the store
 *  can't open — the error then surfaces on the first tool call. */
export class Memory {
  private spacesCache: { wins: Space; vetoes: Space } | null = null;

  constructor(readonly path: string) {}

  spaces(): { wins: Space; vetoes: Space } {
    if (!this.spacesCache) {
      this.spacesCache = {
        wins: new Space({ minSim: MIN_SIM, k: K, path: join(this.path, "wins.db") }),
        vetoes: new Space({ minSim: MIN_SIM, k: K, path: join(this.path, "vetoes.db") }),
      };
    }
    this.spacesCache.wins.refresh();
    this.spacesCache.vetoes.refresh();
    return this.spacesCache;
  }

  query(situation: Situation, weights: Weights | null = null): Record<string, unknown> {
    const s = this.spaces();
    // the kernel's contract, with count reported (not gated) so a
    // precedent of one still surfaces as a cited reminder
    const d = decide(s.wins, s.vetoes, situation, { minConfidence: ACT_CONFIDENCE, minCount: 1, weights });
    const out = d.answer.toJson();
    const veto = d.answer.top ? s.vetoes.matches(situation, d.answer.top, null, weights) : 0;
    out.veto_match = pyRound(veto, 4);
    out.act = d.act;
    out.reason = d.reason;
    out.lifted = d.lifted; // a newer win outranks a close veto
    out.calibrated = d.answer.count >= CALIBRATED_COUNT;
    return out;
  }

  facts(situation: Situation, weights: Weights | null, top: number): Record<string, unknown> {
    const s = this.spaces();
    const read = (space: Space) => space.facts(situation, { weights, top, minScore: MIN_SIM }).map((f) => f.toJson());
    return { wins: read(s.wins), vetoes: read(s.vetoes) };
  }

  calibrate(weights: Weights | null): Record<string, unknown> {
    const wins = this.spaces().wins;
    return { store: "wins", tau: wins.calibrate({ weights }), size: wins.size };
  }

  record(store: "wins" | "vetoes", situation: Situation, outcome: string, author: string): Record<string, unknown> {
    const space = this.spaces()[store];
    space.author = author;
    return { store, id: space.record(situation, outcome), size: space.size };
  }

  check(situation: Situation, outcome: string): Record<string, unknown> {
    const s = this.spaces();
    return {
      win_match: pyRound(s.wins.matches(situation, outcome), 4),
      veto_match: pyRound(s.vetoes.matches(situation, outcome), 4),
    };
  }

  status(): Record<string, unknown> {
    const s = this.spaces();
    return { memory_dir: this.path, wins: s.wins.size, vetoes: s.vetoes.size };
  }
}

const SITUATION = {
  type: "object",
  description: "Decision-relevant attributes only, e.g. " +
    '{"task": "long_background_run", "constraint": "exceeds_tool_timeout"}. Values may nest (objects, arrays as ' +
    "sets, numbers, booleans). Incidental attributes (ids, paths, timestamps) poison neighborhoods.",
  minProperties: 1,
};
const WEIGHTS = {
  type: "object",
  description: "How much each key decides, mirroring the situation: " +
    '{"risk": 1, "team": 0.1, "plan": {"*": 0.5, "step": 2}}. A number weighs a key; an object weighs inside it, ' +
    'its own weight under "*". Unlisted keys weigh 1; 0 ignores a key.',
};
const OUTCOME = { type: "string", description: "The approach, as a short snake_case label." };
const AUTHOR = { type: "string", description: "Your agent name; receipts carry it." };

export const TOOLS = [
  {
    name: "query",
    description: "Ask the wins store what worked in similar situations. Returns the top outcome with confidence, " +
      "support, count, receipts, the nearest veto of that outcome, and `act` (sufficient, confidence >= 0.5, and no " +
      "veto as close as the wins unless a newer win outranks it; `reason` says which gate decided, `lifted` whether a " +
      "newer win lifted a veto). With `calibrated` false treat it as a cited reminder, not a settled rule.",
    inputSchema: { type: "object", properties: { situation: SITUATION, weights: WEIGHTS }, required: ["situation"] },
  },
  {
    name: "facts",
    description: "Why, not just what: the nearest wins and vetoes, each explained against this situation as a fact " +
      "tree — per key its score, weight and share of the whole — and ranked by exact weighted score, each with its " +
      "id, author, and `probability` of its outcome. Only precedents scoring 0.4 or more.",
    inputSchema: {
      type: "object",
      properties: {
        situation: SITUATION, weights: WEIGHTS,
        top: { type: "integer", minimum: 1, maximum: 50, description: "Precedents per store (default 3)." },
      },
      required: ["situation"],
    },
  },
  {
    name: "calibrate",
    description: "Fit the wins store's probability temperature to its own graded record (needs 10+ wins), so " +
      "`probability` in `facts` means what it says. Saved in the store; rerun after the store grows a lot. Pass the " +
      "weights you query with.",
    inputSchema: { type: "object", properties: { weights: WEIGHTS } },
  },
  {
    name: "record",
    description: "Record a graded WIN: this outcome worked in this situation. Only after the outcome is actually known.",
    inputSchema: { type: "object", properties: { situation: SITUATION, outcome: OUTCOME, author: AUTHOR }, required: ["situation", "outcome", "author"] },
  },
  {
    name: "veto",
    description: "Record a graded FAILURE: this outcome failed (or the user rejected it) in this situation.",
    inputSchema: { type: "object", properties: { situation: SITUATION, outcome: OUTCOME, author: AUTHOR }, required: ["situation", "outcome", "author"] },
  },
  {
    name: "check",
    description: "How close is the nearest recorded win and the nearest recorded veto of THIS outcome to this " +
      "situation? Use before an approach you are considering.",
    inputSchema: { type: "object", properties: { situation: SITUATION, outcome: OUTCOME }, required: ["situation", "outcome"] },
  },
  {
    name: "status",
    description: "Where the memory lives and how many wins and vetoes it holds.",
    inputSchema: { type: "object", properties: {} },
  },
];

function situationArg(args: Record<string, unknown>): Situation {
  const s = args.situation;
  if (!s || typeof s !== "object" || Array.isArray(s) || Object.keys(s).length === 0) {
    throw new ValueError("situation must be a non-empty object");
  }
  encode(s as Situation); // nested, non-empty, encodable — or the error says why
  return s as Situation;
}

function weightsArg(args: Record<string, unknown>): Weights | null {
  const w = args.weights;
  if (w === undefined || w === null) return null;
  if (typeof w !== "object" || Array.isArray(w)) throw new ValueError("weights must be an object");
  return w as Weights;
}

function topArg(args: Record<string, unknown>): number {
  const top = args.top ?? 3;
  if (typeof top !== "number" || !Number.isInteger(top) || top < 1 || top > 50) {
    throw new ValueError("top must be an integer from 1 to 50");
  }
  return top;
}

function stringArg(args: Record<string, unknown>, key: string): string {
  const v = args[key];
  if (typeof v !== "string" || !v.trim()) throw new ValueError(`${key} must be a non-empty string`);
  return v.trim();
}

function call(memory: Memory, name: string, args: Record<string, unknown>): Record<string, unknown> {
  if (name === "query") return memory.query(situationArg(args), weightsArg(args));
  if (name === "calibrate") return memory.calibrate(weightsArg(args));
  if (name === "facts") return memory.facts(situationArg(args), weightsArg(args), topArg(args));
  if (name === "record" || name === "veto") {
    return memory.record(name === "record" ? "wins" : "vetoes", situationArg(args),
      stringArg(args, "outcome"), stringArg(args, "author"));
  }
  if (name === "check") return memory.check(situationArg(args), stringArg(args, "outcome"));
  if (name === "status") return memory.status();
  throw new Error(name);
}

/** One JSON-RPC message in, one response out (null for notifications). */
export function handle(memory: Memory, msg: Record<string, unknown>): Record<string, unknown> | null {
  const method = msg.method;
  const rid = msg.id;
  if (rid === undefined || rid === null) return null; // notifications/initialized and friends
  const ok = (result: unknown) => ({ jsonrpc: "2.0", id: rid, result });
  const params = (msg.params ?? {}) as Record<string, unknown>;
  if (method === "initialize") {
    return ok({
      protocolVersion: (params.protocolVersion as string) || PROTOCOL,
      capabilities: { tools: {} },
      serverInfo: { name: "ada", version: "3.0.1" },
    });
  }
  if (method === "ping") return ok({});
  if (method === "tools/list") return ok({ tools: TOOLS });
  if (method === "tools/call") {
    const name = params.name as string;
    const args = (params.arguments ?? {}) as Record<string, unknown>;
    if (!TOOLS.some((t) => t.name === name)) {
      return { jsonrpc: "2.0", id: rid, error: { code: -32602, message: `unknown tool: ${name}` } };
    }
    let text: string;
    let isError = false;
    try {
      text = JSON.stringify(call(memory, name, args));
    } catch (e) {
      const err = e instanceof Error ? e : new Error(String(e));
      text = `${err.name}: ${err.message}`; // tool errors go back to the model, not the wire
      isError = true;
    }
    return ok({ content: [{ type: "text", text }], isError });
  }
  return { jsonrpc: "2.0", id: rid, error: { code: -32601, message: `method not found: ${method}` } };
}

function main(): void {
  const memory = new Memory(memoryDir());
  const rl = createInterface({ input: process.stdin, crlfDelay: Infinity });
  rl.on("line", (raw) => {
    const line = raw.trim();
    if (!line) return;
    let msg: unknown;
    let reply: Record<string, unknown> | null;
    try {
      msg = JSON.parse(line);
    } catch {
      msg = undefined;
    }
    if (msg === undefined) {
      reply = { jsonrpc: "2.0", id: null, error: { code: -32700, message: "parse error" } };
    } else {
      reply = msg && typeof msg === "object" && !Array.isArray(msg) ? handle(memory, msg as Record<string, unknown>) : null;
    }
    if (reply) process.stdout.write(JSON.stringify(reply) + "\n");
  });
}

main();
