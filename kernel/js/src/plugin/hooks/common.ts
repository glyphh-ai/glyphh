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

export type Row = [situation: Record<string, unknown>, outcome: string, author: string];

// per-session markers live in the system temp dir ($TMPDIR on macOS),
// the same directory the Python hooks use
export const MARKER_DIR = join(tmpdir(), "ada-hooks");

/** The one memory, the same in every session wherever it runs:
 *  $GLYPHH_HOME/ada, else ~/.glyphh/ada. */
export function memoryDir(): string {
  return join(process.env.GLYPHH_HOME || join(homedir(), ".glyphh"), "ada");
}

/** (situation, outcome, author) for every precedent in a store. */
export function rows(dbPath: string): Row[] {
  if (!existsSync(dbPath)) return [];
  try {
    const db = new DatabaseSync(dbPath, { readOnly: true });
    try {
      const cols = new Set(db.prepare("PRAGMA table_info(precedents)").all().map((c) => c.name as string));
      const sql = cols.has("author")
        ? "SELECT situation, outcome, author FROM precedents"
        : "SELECT situation, outcome, 'anon' AS author FROM precedents";
      const out: Row[] = [];
      for (const r of db.prepare(sql).all()) {
        try {
          out.push([JSON.parse(r.situation as string), r.outcome as string, r.author as string]);
        } catch { /* skip unreadable rows */ }
      }
      return out;
    } finally {
      db.close();
    }
  } catch {
    return [];
  }
}

export function count(dbPath: string): number {
  if (!existsSync(dbPath)) return 0;
  try {
    const db = new DatabaseSync(dbPath, { readOnly: true });
    try {
      return Number(db.prepare("SELECT COUNT(*) AS n FROM precedents").get()!.n);
    } finally {
      db.close();
    }
  } catch {
    return 0;
  }
}

export function markerPath(sessionId: string): string {
  mkdirSync(MARKER_DIR, { recursive: true });
  return join(MARKER_DIR, `${sessionId}.json`);
}

export function readMarker(sessionId: string): Record<string, unknown> {
  const p = markerPath(sessionId);
  if (existsSync(p)) {
    try {
      return JSON.parse(readFileSync(p, "utf8"));
    } catch { /* fall through */ }
  }
  return {};
}

export function writeMarker(sessionId: string, data: Record<string, unknown>): void {
  writeFileSync(markerPath(sessionId), JSON.stringify(data));
}

/** The hook's JSON input on stdin, or null when it isn't JSON. */
export function readInput(): Record<string, unknown> | null {
  try {
    const v = JSON.parse(readFileSync(0, "utf8"));
    return v && typeof v === "object" ? v : null;
  } catch {
    return null;
  }
}
