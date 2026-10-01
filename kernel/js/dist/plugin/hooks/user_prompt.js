/**
 * UserPromptSubmit: inject precedent relevant to the incoming prompt
 * (Node port of plugin/hooks/user_prompt.py — same tokens, tiers,
 * weights, threshold and output, byte for byte).
 *
 * The doorbell of the memory: fast, deterministic, model-free. It rings
 * when the prompt lexically resembles stored experience — situations,
 * outcomes (wins AND vetoes), and user-defined aliases. Matching, most
 * to least certain: exact token, shared prefix/stem, one edit away.
 */
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { cmpCodePoints, pyDumps } from "../../pyjson.js";
import { memoryDir, readInput, rows } from "./common.js";
const STOP_WORDS = new Set(`the a an and or to of in for on at is are it this that with as be do can you your we
our i me my please then now just also how what when why not no should would could will was were has have had does
did his her their them they she there here about into over out let lets like need want get got make made use using
used one some any all but if so up down`.split(/\s+/));
const EXACT = 1.0, NEAR = 0.8, FUZZY = 0.6; // match-quality tiers
const SITUATION_W = 1.0, OUTCOME_W = 0.75; // where the stored token lives
const THRESHOLD = 1.2; // min score to ring the bell
const MAX_INJECT = 3; // top situations injected
const SUFFIXES = ["ing", "edly", "ed", "es", "s", "er", "ers", "ly"];
/** snake_case, camelCase, kebab-case, digits — all become words. */
function split(text) {
    return text.replace(/([a-z])([A-Z])/g, "$1 $2").toLowerCase().match(/[a-z]{3,}/g) ?? [];
}
function stem(token) {
    for (const s of SUFFIXES)
        if (token.endsWith(s) && token.length - s.length >= 3)
            return token.slice(0, -s.length);
    return token;
}
export function tokens(text) {
    return new Set(split(text).filter((t) => !STOP_WORDS.has(t)));
}
/** Within one edit (sub/ins/del or adjacent swap), both >= 5 chars. */
function edit1(a, b) {
    if (Math.min(a.length, b.length) < 5 || Math.abs(a.length - b.length) > 1)
        return false;
    if (a.length === b.length) {
        const diff = [];
        for (let i = 0; i < a.length; i++)
            if (a[i] !== b[i])
                diff.push(i);
        if (diff.length <= 1)
            return true;
        return diff.length === 2 && diff[1] === diff[0] + 1 && a[diff[0]] === b[diff[1]] && a[diff[1]] === b[diff[0]];
    }
    if (a.length > b.length)
        [a, b] = [b, a];
    for (let i = 0; i < b.length; i++)
        if (b.slice(0, i) + b.slice(i + 1) === a)
            return true;
    return false;
}
function matchQuality(stored, promptTokens, promptStems) {
    if (promptTokens.has(stored))
        return EXACT;
    const s = stem(stored);
    if (promptStems.has(s) || promptTokens.has(s))
        return NEAR;
    let best = 0;
    for (const p of promptTokens) {
        if (stored.length >= 4 && p.length >= 4 && (p.startsWith(stored) || stored.startsWith(p)))
            return NEAR;
        if (edit1(stored, p))
            best = FUZZY;
    }
    return best;
}
/** aliases.json maps a surface form to canonical tokens. */
function loadAliases(mem) {
    const path = join(mem, "aliases.json");
    const out = new Map();
    if (!existsSync(path))
        return out;
    try {
        const raw = JSON.parse(readFileSync(path, "utf8"));
        for (const [k, vals] of Object.entries(raw)) {
            if (Array.isArray(vals))
                out.set(String(k).toLowerCase(), vals.map((v) => String(v).toLowerCase()));
        }
    }
    catch { /* no aliases */ }
    return out;
}
function main() {
    const data = readInput();
    if (!data)
        return;
    const mem = memoryDir();
    const promptTokens = tokens(String(data.prompt ?? ""));
    if (promptTokens.size === 0)
        return;
    for (const [surface, canonicals] of loadAliases(mem)) {
        if (promptTokens.has(surface))
            for (const c of canonicals)
                promptTokens.add(c);
    }
    const promptStems = new Set([...promptTokens].map(stem));
    const wins = rows(join(mem, "wins.db"));
    const vetoes = rows(join(mem, "vetoes.db"));
    if (!wins.length && !vetoes.length)
        return;
    // group identical situations; collect their outcome vocabulary
    const grouped = new Map();
    const entry = (key) => {
        let e = grouped.get(key);
        if (!e)
            grouped.set(key, (e = { wins: new Map(), vetoes: new Set() }));
        return e;
    };
    for (const [situation, outcome] of wins) {
        const w = entry(pyDumps(situation, { sortKeys: true })).wins;
        w.set(outcome, (w.get(outcome) ?? 0) + 1);
    }
    for (const [situation, outcome] of vetoes)
        entry(pyDumps(situation, { sortKeys: true })).vetoes.add(outcome);
    const scored = [];
    for (const [key, e] of grouped) {
        const situation = JSON.parse(key);
        const situationTokens = new Set();
        for (const [k, v] of Object.entries(situation)) {
            for (const t of tokens(String(k)))
                situationTokens.add(t);
            // nested values tokenize as their JSON text
            for (const t of tokens(typeof v === "string" ? v : pyDumps(v)))
                situationTokens.add(t);
        }
        const outcomeTokens = new Set();
        for (const o of [...e.wins.keys(), ...[...e.vetoes].sort(cmpCodePoints)])
            for (const t of tokens(o))
                outcomeTokens.add(t);
        for (const t of situationTokens)
            outcomeTokens.delete(t);
        // summed in sorted order, like the Python hook, so the threshold is stable
        let score = 0;
        for (const t of [...situationTokens].sort(cmpCodePoints))
            score += SITUATION_W * matchQuality(t, promptTokens, promptStems);
        let outcomeScore = 0;
        for (const t of [...outcomeTokens].sort(cmpCodePoints))
            outcomeScore += OUTCOME_W * matchQuality(t, promptTokens, promptStems);
        score += outcomeScore;
        if (score >= THRESHOLD)
            scored.push([score, key, e]);
    }
    if (!scored.length)
        return;
    scored.sort((a, b) => b[0] - a[0]);
    const lines = ["ada memory hits for this prompt (lexical doorbell; run a similarity query for anything borderline):"];
    for (const [, key, e] of scored.slice(0, MAX_INJECT)) {
        const parts = [];
        if (e.wins.size) {
            const worked = [...e.wins.entries()].sort((a, b) => b[1] - a[1]).map(([o, n]) => `${o} (x${n})`).join(", ");
            parts.push(`worked: ${worked}`);
        }
        if (e.vetoes.size)
            parts.push(`VETOED: ${[...e.vetoes].sort(cmpCodePoints).join(", ")}`);
        lines.push(`- ${key} -> ${parts.join("; ")}`);
    }
    process.stdout.write(lines.join("\n") + "\n");
}
main();
