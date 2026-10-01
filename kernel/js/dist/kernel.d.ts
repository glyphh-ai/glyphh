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
/** Any JSON-shaped value: objects nest, arrays are sets, scalars are symbols. */
export type Data = string | number | boolean | null | Data[] | {
    [key: string]: Data;
};
export type Situation = {
    [key: string]: Data;
};
/** Mirrors the data: a number weighs a key; an object weighs inside it, its own weight under "*". */
export type Weights = {
    [key: string]: number | Weights;
};
export type Receipt = [id: string, sim: number, outcome: string, hash: string, author: string];
export declare const DIM = 4096;
export declare const TAU = 0.12;
export declare const POOL = 25;
export declare const TAUS: number[];
export declare const ENCODING = 3;
export declare const SPEC: string;
/** The substrate guidance. Read it before recording or querying. */
export declare function spec(): string;
/** Deterministic bipolar (+1/-1) symbol for a key. Same (key, seed, dim)
 *  gives the identical vector on any machine, in either language. */
export declare function symbol(key: string, seed?: number, dim?: number): Glyph;
/** Associate two glyphs (elementwise multiply). Self-inverse. */
export declare function bind(a: Glyph, b: Glyph): Glyph;
/** Superpose glyphs (majority vote). Resembles all inputs; order-free.
 *  weights: one per part, finite and >= 0 — a part's voice in the vote
 *  (0 drops it). Summed in a canonical order (parts by their bytes), so
 *  it stays order-free and bit-identical to Python. */
export declare function bundle(parts: Glyph[], weights?: number[] | null): Glyph;
/** Rotate a glyph (np.roll): order, position, depth. roll(v, -k) undoes. */
export declare function roll(v: Glyph, k?: number): Glyph;
/** Cosine similarity for bipolar glyphs, in [-1, 1]. */
export declare function sim(a: Glyph, b: Glyph): number;
/** One glyph for any JSON-shaped value, with weights at every level. */
export declare function encode(data: Data, weights?: Weights | null, seed?: number, dim?: number): Glyph;
declare const ABSENT: unique symbol;
type Side = Data | typeof ABSENT;
/** One node of a fact tree: how one part of a query compares with the
 *  same part of a record. score: the exact weighted sim of this subtree;
 *  share: weight * score / the siblings' total weight (shares sum to the
 *  parent's score); sim: the glyph sim of the two subtrees. */
export declare class Fact {
    key: string;
    weight: number;
    score: number;
    share: number;
    sim: number;
    status: "both" | "query_only" | "record_only";
    query: Side;
    record: Side;
    children: Fact[];
    constructor(key: string, weight: number, score: number, share: number, sim: number, status: "both" | "query_only" | "record_only", query: Side, record: Side, children: Fact[]);
    toJson(): Record<string, unknown>;
    toText(depth?: number): string;
}
/** The fact tree for one query against one record: per key, how close,
 *  with what weight, and its share of the whole. root.score is the
 *  weighted sim. A key on one side only scores 0 at full weight. */
export declare function explain(query: Data, record: Data, weights?: Weights | null, seed?: number, dim?: number): Fact;
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
    /** probability temperature: given, else the file's calibrated one, else TAU */
    tau?: number;
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
    tau: number;
    private tauGiven;
    private ids;
    private outcomesOf;
    private authors;
    private tsOf;
    private situations;
    private trajs;
    private glyphs;
    private db;
    constructor(opts?: SpaceOptions);
    get size(): number;
    /** A situation is an object (values may nest — see encode()); optional
     *  events fold in as a strand so order-carrying situations keep their
     *  order; weights weigh the situation's keys. */
    encode(situation: Situation, events?: Glyph[] | null, weights?: Weights | null): Glyph;
    private traj;
    private push;
    record(situation: Situation, outcome: string, opts?: {
        events?: Glyph[];
        rid?: string;
        ts?: number;
    }): string;
    private sims;
    /** Precedent i explained against the situation; events, when either
     *  side has them, are one more key: "~events". */
    private exact;
    /** The similarity every read ranks and gates on: the glyph sim, or —
     *  when the caller weighs the keys — the exact weighted sim. */
    private scores;
    private topIndices;
    private hashOf;
    /** weights: the query's weights tree. Weighted, every similarity is the
     *  exact weighted sim (a fact tree's score); unweighted, the glyph sim. */
    query(situation: Situation, events?: Glyph[] | null, weights?: Weights | null): Answer;
    private evidenceFrom;
    /** Support for ONE candidate outcome, over every precedent. */
    evidence(situation: Situation, outcome: string, opts?: {
        events?: Glyph[];
        minSim?: number;
        weights?: Weights | null;
    }): Evidence;
    /** Every outcome with qualifying precedent, strongest first (SPEC rule 4). */
    answers(situation: Situation, opts?: {
        events?: Glyph[];
        minCount?: number;
        weights?: Weights | null;
    }): Evidence[];
    /** Max similarity among precedents with THIS outcome: the veto primitive. */
    matches(situation: Situation, outcome: string, events?: Glyph[] | null, weights?: Weights | null): number;
    /** The exact read: every precedent scored by weighted sim (unweighted
     *  keys weigh 1), the `top` (default k) best each explained as a fact
     *  tree with its glyph sim and citation. Ranked by score, then glyph
     *  sim, newest, id; rows under minScore (if given) are left out. */
    facts(situation: Situation, opts?: {
        events?: Glyph[];
        weights?: Weights | null;
        top?: number;
        minScore?: number;
    }): FactTree[];
    /** P(outcome | situation) over the POOL nearest by exact weighted sim:
     *  a softmax of their scores at temperature tau, summed per outcome. */
    probabilities(situation: Situation, opts?: {
        events?: Glyph[];
        weights?: Weights | null;
    }): Record<string, number>;
    private probs;
    /** Fit tau by holding out each of the `sample` newest precedents in
     *  turn (least log-loss over TAUS); saved in the file. Returns tau. */
    calibrate(opts?: {
        sample?: number;
        weights?: Weights | null;
    }): number;
    private open;
    /** Pull in rows other agents wrote to this file since open. */
    refresh(): number;
    /** Union another Space file into this one (by precedent id). Rows from
     *  an older encoding are re-encoded on the way in. */
    merge(otherPath: string): number;
    close(): void;
}
/** One precedent explained against a situation (Space.facts()). score is
 *  the exact weighted sim; sim the glyph sim; the rest cites it. */
export declare class FactTree {
    id: string;
    outcome: string;
    author: string;
    ts: number;
    hash: string;
    sim: number;
    root: Fact;
    probability: number;
    constructor(id: string, outcome: string, author: string, ts: number, hash: string, sim: number, root: Fact, probability?: number);
    get score(): number;
    toJson(): Record<string, unknown>;
    toText(): string;
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
    weights?: Weights | null;
}): Decision;
/** Re-encode every precedent's glyph from its stored situation and events
 *  under the current encoding, and stamp the file. Returns rows re-encoded. */
export declare function reencodeStore(path: string, opts?: SpaceOptions): number;
export {};
