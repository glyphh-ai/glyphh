/**
 * Python-compatible text: json.dumps separators and escaping, round()
 * semantics, and code-point ordering. The kernel stores and prints the
 * same bytes the Python kernel does, so either can read the other's files
 * and hook output compares equal.
 */
/** Python's str ordering: by code point, not UTF-16 unit. */
export declare function cmpCodePoints(a: string, b: string): number;
/** json.dumps(value, sort_keys=?, ensure_ascii=?) with Python's default
 *  ", " / ": " separators. Numbers use JS formatting (1.0 prints as 1). */
export declare function pyDumps(value: unknown, opts?: {
    sortKeys?: boolean;
    ensureAscii?: boolean;
}): string;
/** Python's round(x, n): round-half-even on the EXACT binary value. */
export declare function pyRound(x: number, n: number): number;
