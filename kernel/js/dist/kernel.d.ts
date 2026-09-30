/**
 * Ada kernel — the AI-native kernel, in TypeScript. Node >= 22.13, no
 * dependencies (node:crypto + node:sqlite).
 *
 * A bit-identical port of ../glyphh_kernel.py: every symbol, bind,
 * bundle, roll, Strand state and Space encoding is the same vector,
 * byte for byte, as the Python kernel produces, and both read and write
 * the same SQLite store files. The parity tests in ../test hold the two
 * to that. If you are an agent reading this: call spec() first.
 */
export type Glyph = Int8Array;
export type Situation = Record<string, string>;
export type Receipt = [id: string, sim: number, outcome: string, hash: string, author: string];
export declare const DIM = 4096;
export declare const ENCODING = 2;
export declare const SPEC: string;
/** The substrate guidance. Read it before recording or querying. */
export declare function spec(): string;
/** Deterministic bipolar (+1/-1) symbol for a key. Same (key, seed, dim)
 *  gives the identical vector on any machine, in either language. */
export declare function symbol(key: string, seed?: number, dim?: number): Glyph;
/** Associate two glyphs (elementwise multiply). Self-inverse. */
export declare function bind(a: Glyph, b: Glyph): Glyph;
/** Superpose glyphs (majority vote). Resembles all inputs; order-free. */
export declare function bundle(parts: Glyph[]): Glyph;
/** Rotate a glyph (np.roll): order, position, depth. roll(v, -k) undoes. */
export declare function roll(v: Glyph, k?: number): Glyph;
/** Cosine similarity for bipolar glyphs, in [-1, 1]. */
export declare function sim(a: Glyph, b: Glyph): number;
/** A sequence of glyphs whose ORDER is part of the meaning. */
export declare class Strand {
    codons: Glyph[];
    constructor(codons?: Glyph[]);
    append(codon: Glyph): this;
    state(decay?: number): Glyph;
    get length(): number;
}
/** What a Space says. Trust `top` only when sufficient, confident, and
 *  count is more than a couple. */
export declare class Answer {
    sufficient: boolean;
    confidence: number;
    support: number;
    count: number;
    top: string | null;
    outcomes: Record<string, number>;
    receipts: Receipt[];
    constructor(sufficient: boolean, confidence: number, support: number, count: number, top: string | null, outcomes: Record<string, number>, receipts: Receipt[]);
    toJson(): Record<string, unknown>;
}
/** Support for one outcome in one situation, judged on its own. */
export declare class Evidence {
    outcome: string;
    count: number;
    support: number;
    nearest: number;
    latest: number;
    authors: string[];
    constructor(outcome: string, count: number, support: number, nearest: number, latest: number, authors: string[]);
    toJson(): Record<string, unknown>;
}
export interface SpaceOptions {
    dim?: number;
    k?: number;
    minSim?: number;
    seed?: number;
    decay?: number;
    author?: string;
    path?: string;
}
/** Precedent memory: record graded experience, answer by similarity.
 *  Encode only decision-relevant attributes; see SPEC. */
export declare class Space {
    readonly dim: number;
    k: number;
    minSim: number;
    readonly seed: number;
    decay: number;
    author: string;
    private ids;
    private outcomesOf;
    private authors;
    private tsOf;
    private glyphs;
    private db;
    constructor(opts?: SpaceOptions);
    get size(): number;
    /** A situation is a dict of attributes; optional events fold in as a
     *  strand so order-carrying situations keep their order. */
    encode(situation: Situation, events?: Glyph[] | null): Glyph;
    private push;
    record(situation: Situation, outcome: string, opts?: {
        events?: Glyph[];
        rid?: string;
        ts?: number;
    }): string;
    private sims;
    private topIndices;
    query(situation: Situation, events?: Glyph[] | null): Answer;
    private evidenceFrom;
    /** Support for ONE candidate outcome, over every precedent. */
    evidence(situation: Situation, outcome: string, opts?: {
        events?: Glyph[];
        minSim?: number;
    }): Evidence;
    /** Every outcome with qualifying precedent, strongest first (SPEC rule 4). */
    answers(situation: Situation, opts?: {
        events?: Glyph[];
        minCount?: number;
    }): Evidence[];
    /** Max similarity among precedents with THIS outcome: the veto primitive. */
    matches(situation: Situation, outcome: string, events?: Glyph[] | null): number;
    private open;
    /** Pull in rows other agents wrote to this file since open. */
    refresh(): number;
    /** Union another Space file into this one (by precedent id). Rows from
     *  an older encoding are re-encoded on the way in. */
    merge(otherPath: string): number;
    close(): void;
}
/** What decide() concluded. Act on `outcome` only when `act`. */
export declare class Decision {
    act: boolean;
    outcome: string | null;
    reason: "reflex" | "insufficient" | "uncalibrated" | "low_confidence" | "vetoed";
    answer: Answer;
    veto: Evidence | null;
    lifted: boolean;
    constructor(act: boolean, outcome: string | null, reason: "reflex" | "insufficient" | "uncalibrated" | "low_confidence" | "vetoed", answer: Answer, veto: Evidence | null, lifted: boolean);
    toJson(): Record<string, unknown>;
}
/** THE CONTRACT (see SPEC): three trust gates on the wins, then the veto
 *  check, with the newest evidence winning. */
export declare function decide(wins: Space, vetoes: Space, situation: Situation, opts?: {
    events?: Glyph[];
    minConfidence?: number;
    minCount?: number;
    minVetoCount?: number;
}): Decision;
/** Re-encode every precedent's glyph from its stored situation and events
 *  under the current encoding, and stamp the file. Returns rows re-encoded. */
export declare function reencodeStore(path: string, opts?: SpaceOptions): number;
