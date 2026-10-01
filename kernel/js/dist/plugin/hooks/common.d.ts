/**
 * Shared helpers for the Ada hooks (Node port of plugin/hooks/common.py).
 *
 * Hooks read the memory's SQLite files directly — no kernel encoding —
 * so they run in milliseconds. The kernel is only needed by the MCP
 * server, for real similarity queries and writes.
 */
export type Row = [situation: Record<string, unknown>, outcome: string, author: string];
export declare const MARKER_DIR: string;
/** The one memory, the same in every session wherever it runs:
 *  $GLYPHH_HOME/ada, else ~/.glyphh/ada. */
export declare function memoryDir(): string;
/** (situation, outcome, author) for every precedent in a store. */
export declare function rows(dbPath: string): Row[];
export declare function count(dbPath: string): number;
export declare function markerPath(sessionId: string): string;
export declare function readMarker(sessionId: string): Record<string, unknown>;
export declare function writeMarker(sessionId: string, data: Record<string, unknown>): void;
/** The hook's JSON input on stdin, or null when it isn't JSON. */
export declare function readInput(): Record<string, unknown> | null;
