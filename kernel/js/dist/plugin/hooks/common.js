/**
 * Shared helpers for the Ada hooks (Node port of plugin/hooks/common.py).
 *
 * Hooks read the memory's SQLite files directly — no kernel encoding —
 * so they run in milliseconds. The kernel is only needed by the MCP
 * server, for real similarity queries and writes.
 */
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { homedir, tmpdir } from "node:os";
import { join } from "node:path";
import { DatabaseSync } from "node:sqlite";
// per-session markers live in the system temp dir ($TMPDIR on macOS),
// the same directory the Python hooks use
export const MARKER_DIR = join(tmpdir(), "ada-hooks");
/** The one memory, the same in every session wherever it runs:
 *  $GLYPHH_HOME/ada, else ~/.glyphh/ada. */
export function memoryDir() {
    return join(process.env.GLYPHH_HOME || join(homedir(), ".glyphh"), "ada");
}
/** (situation, outcome, author) for every precedent in a store. */
export function rows(dbPath) {
    if (!existsSync(dbPath))
        return [];
    try {
        const db = new DatabaseSync(dbPath, { readOnly: true });
        try {
            const cols = new Set(db.prepare("PRAGMA table_info(precedents)").all().map((c) => c.name));
            const sql = cols.has("author")
                ? "SELECT situation, outcome, author FROM precedents"
                : "SELECT situation, outcome, 'anon' AS author FROM precedents";
            const out = [];
            for (const r of db.prepare(sql).all()) {
                try {
                    out.push([JSON.parse(r.situation), r.outcome, r.author]);
                }
                catch { /* skip unreadable rows */ }
            }
            return out;
        }
        finally {
            db.close();
        }
    }
    catch {
        return [];
    }
}
export function count(dbPath) {
    if (!existsSync(dbPath))
        return 0;
    try {
        const db = new DatabaseSync(dbPath, { readOnly: true });
        try {
            return Number(db.prepare("SELECT COUNT(*) AS n FROM precedents").get().n);
        }
        finally {
            db.close();
        }
    }
    catch {
        return 0;
    }
}
export function markerPath(sessionId) {
    mkdirSync(MARKER_DIR, { recursive: true });
    return join(MARKER_DIR, `${sessionId}.json`);
}
export function readMarker(sessionId) {
    const p = markerPath(sessionId);
    if (existsSync(p)) {
        try {
            return JSON.parse(readFileSync(p, "utf8"));
        }
        catch { /* fall through */ }
    }
    return {};
}
export function writeMarker(sessionId, data) {
    writeFileSync(markerPath(sessionId), JSON.stringify(data));
}
/** The hook's JSON input on stdin, or null when it isn't JSON. */
export function readInput() {
    try {
        const v = JSON.parse(readFileSync(0, "utf8"));
        return v && typeof v === "object" ? v : null;
    }
    catch {
        return null;
    }
}
