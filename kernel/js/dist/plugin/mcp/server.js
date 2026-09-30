/**
 * The Ada memory as an MCP server (stdio, newline-delimited JSON-RPC
 * 2.0), in Node — a port of plugin/mcp/server.py with the same tools,
 * schemas and outputs, on the same store ($GLYPHH_HOME/ada, else
 * ~/.glyphh/ada). The spaces load once and refresh() before every read,
 * so rows other sessions (or the Python server) wrote always count.
 */
import { homedir } from "node:os";
import { join } from "node:path";
import { createInterface } from "node:readline";
import { decide, Space } from "../../kernel.js";
import { pyRound } from "../../pyjson.js";
const PROTOCOL = "2025-06-18";
const MIN_SIM = 0.4, K = 7;
const ACT_CONFIDENCE = 0.5; // the skill's bar for acting on a top answer
const CALIBRATED_COUNT = 3; // below this, precedent is a cited reminder
class ValueError extends Error {
    name = "ValueError";
}
export function memoryDir() {
    return join(process.env.GLYPHH_HOME || join(homedir(), ".glyphh"), "ada");
}
/** wins + vetoes, opened lazily so the server starts even if the store
 *  can't open — the error then surfaces on the first tool call. */
export class Memory {
    path;
    spacesCache = null;
    constructor(path) {
        this.path = path;
    }
    spaces() {
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
    query(situation) {
        const s = this.spaces();
        // the kernel's contract, with count reported (not gated) so a
        // precedent of one still surfaces as a cited reminder
        const d = decide(s.wins, s.vetoes, situation, { minConfidence: ACT_CONFIDENCE, minCount: 1 });
        const out = d.answer.toJson();
        const veto = d.answer.top ? s.vetoes.matches(situation, d.answer.top) : 0;
        out.veto_match = pyRound(veto, 4);
        out.act = d.act;
        out.reason = d.reason;
        out.lifted = d.lifted; // a newer win outranks a close veto
        out.calibrated = d.answer.count >= CALIBRATED_COUNT;
        return out;
    }
    record(store, situation, outcome, author) {
        const space = this.spaces()[store];
        space.author = author;
        return { store, id: space.record(situation, outcome), size: space.size };
    }
    check(situation, outcome) {
        const s = this.spaces();
        return {
            win_match: pyRound(s.wins.matches(situation, outcome), 4),
            veto_match: pyRound(s.vetoes.matches(situation, outcome), 4),
        };
    }
    status() {
        const s = this.spaces();
        return { memory_dir: this.path, wins: s.wins.size, vetoes: s.vetoes.size };
    }
}
const SITUATION = {
    type: "object",
    description: "Decision-relevant attributes only, e.g. " +
        '{"task": "long_background_run", "constraint": "exceeds_tool_timeout"}. Incidental ' +
        "attributes (ids, paths, timestamps) poison neighborhoods.",
    additionalProperties: { type: "string" },
    minProperties: 1,
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
        inputSchema: { type: "object", properties: { situation: SITUATION }, required: ["situation"] },
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
function situationArg(args) {
    const s = args.situation;
    if (!s || typeof s !== "object" || Array.isArray(s) || Object.keys(s).length === 0) {
        throw new ValueError("situation must be a non-empty object");
    }
    if (!Object.values(s).every((v) => typeof v === "string")) {
        throw new ValueError("situation keys and values must be strings");
    }
    return s;
}
function stringArg(args, key) {
    const v = args[key];
    if (typeof v !== "string" || !v.trim())
        throw new ValueError(`${key} must be a non-empty string`);
    return v.trim();
}
function call(memory, name, args) {
    if (name === "query")
        return memory.query(situationArg(args));
    if (name === "record" || name === "veto") {
        return memory.record(name === "record" ? "wins" : "vetoes", situationArg(args), stringArg(args, "outcome"), stringArg(args, "author"));
    }
    if (name === "check")
        return memory.check(situationArg(args), stringArg(args, "outcome"));
    if (name === "status")
        return memory.status();
    throw new Error(name);
}
/** One JSON-RPC message in, one response out (null for notifications). */
export function handle(memory, msg) {
    const method = msg.method;
    const rid = msg.id;
    if (rid === undefined || rid === null)
        return null; // notifications/initialized and friends
    const ok = (result) => ({ jsonrpc: "2.0", id: rid, result });
    const params = (msg.params ?? {});
    if (method === "initialize") {
        return ok({
            protocolVersion: params.protocolVersion || PROTOCOL,
            capabilities: { tools: {} },
            serverInfo: { name: "ada", version: "3.0.1" },
        });
    }
    if (method === "ping")
        return ok({});
    if (method === "tools/list")
        return ok({ tools: TOOLS });
    if (method === "tools/call") {
        const name = params.name;
        const args = (params.arguments ?? {});
        if (!TOOLS.some((t) => t.name === name)) {
            return { jsonrpc: "2.0", id: rid, error: { code: -32602, message: `unknown tool: ${name}` } };
        }
        let text;
        let isError = false;
        try {
            text = JSON.stringify(call(memory, name, args));
        }
        catch (e) {
            const err = e instanceof Error ? e : new Error(String(e));
            text = `${err.name}: ${err.message}`; // tool errors go back to the model, not the wire
            isError = true;
        }
        return ok({ content: [{ type: "text", text }], isError });
    }
    return { jsonrpc: "2.0", id: rid, error: { code: -32601, message: `method not found: ${method}` } };
}
function main() {
    const memory = new Memory(memoryDir());
    const rl = createInterface({ input: process.stdin, crlfDelay: Infinity });
    rl.on("line", (raw) => {
        const line = raw.trim();
        if (!line)
            return;
        let msg;
        let reply;
        try {
            msg = JSON.parse(line);
        }
        catch {
            msg = undefined;
        }
        if (msg === undefined) {
            reply = { jsonrpc: "2.0", id: null, error: { code: -32700, message: "parse error" } };
        }
        else {
            reply = msg && typeof msg === "object" && !Array.isArray(msg) ? handle(memory, msg) : null;
        }
        if (reply)
            process.stdout.write(JSON.stringify(reply) + "\n");
    });
}
main();
