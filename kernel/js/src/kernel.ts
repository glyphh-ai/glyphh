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

import { createHash, randomUUID } from "node:crypto";
import { mkdirSync } from "node:fs";
import { homedir } from "node:os";
import { dirname, resolve } from "node:path";
import { DatabaseSync } from "node:sqlite";

import { cmpCodePoints, pyDumps, pyRound } from "./pyjson.js";

export type Glyph = Int8Array;
/** Any JSON-shaped value: objects nest, arrays are sets, scalars are symbols. */
export type Data = string | number | boolean | null | Data[] | { [key: string]: Data };
export type Situation = { [key: string]: Data };
/** Mirrors the data: a number weighs a key; an object weighs inside it, its own weight under "*". */
export type Weights = { [key: string]: number | Weights };
export type Receipt = [id: string, sim: number, outcome: string, hash: string, author: string];

export const DIM = 4096; // default dimensionality; ~1e-3 cross-talk between random symbols
export const TAU = 0.12; // default softmax temperature (fit on Kubernetes issues; calibrate())
export const POOL = 25; // nearest precedents a probability is spread over
export const TAUS = [0.01, 0.02, 0.03, 0.05, 0.08, 0.12, 0.2, 0.3, 0.5, 1.0];
export const ENCODING = 3; // bump when encode() changes; stores re-encode on open

export const SPEC: string = "Ada kernel — substrate guidance for the agent using it\n\nWHAT THIS IS. Your state and execution layer beyond the context\nwindow. Contexts are mortal; the SQLite files a Space writes are not.\nRecord graded experience as you work; the next context (yours or\nanother agent's) reopens the files and inherits ground truth instead\nof prose about it.\n\nTHE FIVE PRIMITIVES. All glyphs are bipolar +/-1 vectors of one fixed\ndimension (default 4096); every operation returns the type it takes,\nso composites nest indefinitely.\n  symbol(key, seed=42, dim)  deterministic glyph: same inputs -> the\n      identical vector on any machine, forever. Shared seed = shared\n      vocabulary between agents; different seeds are mutual noise.\n  bind(a, b)     associate (elementwise multiply). Self-inverse; the\n      result resembles neither input. Use for role-filler pairs.\n  bundle(parts, weights=None)  superpose (majority vote); resembles\n      ALL inputs. Order-free: the same parts in any order give the same\n      glyph. weights (one per part, >= 0) give each part its voice in\n      the vote; the result is a glyph, so weighted bundles nest and\n      weights live at every level. Capacity is finite: past a few dozen\n      parts detail fades and gist survives — that is abstraction; keep\n      receipts for the detail.\n  roll(v, k)     rotate: order, position, depth. Undo with roll(v,-k).\n  sim(a, b)      cosine in [-1, 1]. Random glyphs sit near 0. For\n      situations, sim tracks the FRACTION OF SHARED ATTRIBUTE PAIRS,\n      whichever attributes they are (measured, 4 attributes: sharing\n      1/2/3 -> 0.14/0.28/0.44; 2 attributes sharing 1 -> 0.25), even\n      when the shared attributes are decision-irrelevant.\n\nDATA. encode(data, weights) is one glyph for any JSON-shaped value:\n  an object is a weighted bundle of bind(attr:key, child), an array a\n  set of its items, a scalar the symbol of its text; nested children\n  roll once so paths stay apart. weights mirror the data —\n  {\"risk\": 1.0, \"plan\": {\"*\": 0.5, \"step\": 2}}: a number weighs a key,\n  an object weighs inside it with its own weight under \"*\"; unlisted\n  keys weigh 1.0. explain(query, record, weights) -> Fact: the fact\n  tree — per key, its score (exact weighted sim of that subtree), its\n  weight, its share of the parent (shares sum to the parent's score),\n  and the glyph sim beside it. root.score is the weighted sim. A key on\n  one side only scores 0 at full weight: weigh it 0 if its absence\n  should not count. Weights are how you say which attributes decide;\n  that is rule 2, made explicit.\n\nTHE TWO CONSTRUCTS.\n  Strand: ordered meaning. append() glyphs; state(decay) folds the\n      sequence into one glyph where recent items dominate and order\n      matters. Detail recoverable a few steps back; the KIND of\n      trajectory recognizable much longer.\n  Space(dim, k, min_sim, seed, decay, author, path): graded precedent.\n      record(situation, outcome, events=None, ts=None) — one write,\n      permanent, time-stamped. A situation is an object; values may\n      nest (see DATA). Every read below takes weights=: weighted, it\n      ranks and gates on the EXACT weighted sim (the fact-tree score),\n      so min_sim means 'the weighted share of attributes that must\n      agree' and a weight can raise a match, not only lower it.\n      query(...) -> Answer(sufficient, confidence, support, count,\n      top, outcomes, receipts); only precedents clearing min_sim vote.\n      answers(...) -> [Evidence] for EVERY outcome with qualifying\n      precedent: the read for situations with more than one true\n      outcome. evidence(situation, outcome) grades one candidate.\n      matches(situation, outcome) — max sim among precedents with THAT\n      outcome: the veto primitive, undilutable by consensus.\n      facts(situation, weights=None, top=k) -> [FactTree]: every\n      precedent scored exactly, the best `top` explained as fact trees\n      (events as the key \"~events\"), each with its glyph sim and its\n      citation, and probability: P(that outcome | situation), a\n      softmax at temperature tau over the POOL (25) nearest. The read\n      to show WHY, not just what.\n      probabilities(situation, weights=None) -> {outcome: P}.\n      calibrate(sample=100, weights=None) fits tau by holding out the\n      newest precedents one at a time; saved in the file. Until then\n      tau is TAU (0.12). Calibrated, \"act at P >= 0.9\" means right\n      about 9 times in 10 — on the Kubernetes test it took confident\n      answers from 87% to 94% right.\n      refresh() pulls rows other agents wrote to a shared WAL file;\n      merge(other_path) unions another Space file by id, authors kept.\n\nTHE CONTRACT: NOTHING UNGRADED. Route every domain decision through\ndecide(wins, vetoes, situation, events) -> Decision. It is:\n  a = wins.query(situation, events)\n  if a.sufficient and a.confidence >= 0.5 and a.count >= 3:\n      if not vetoed(a.top):               # see rule 3\n          act(a.top)                      # reflex: free, cited\n      else: consult fallback              # vetoed\n  else: consult fallback                  # insufficient precedent\n  success = the WORLD grades the action   # never self-graded\n  (wins if success else vetoes).record(situation, action, events)\nFallback chain by cost: reflex (free) -> consultant (paid) -> human\n(last resort; the answer is itself a grade). Consult rate should fall\nover the Space's life — that curve is the product metric.\n\nRULES THAT DECIDE WHETHER IT WORKS.\n  1. Trust needs three gates: sufficient (similarity), confidence\n     (consensus), count (population). A consensus of one is\n     confidence 1.0 and means almost nothing — gate count >= 3.\n  2. Attribute hygiene: encode ONLY decision-relevant attributes;\n     incidental ones (ids, regions, timestamps) poison neighborhoods.\n     Size min_sim as the attribute-overlap fraction that should count\n     as 'the same kind of situation'.\n  3. Vetoes suppress, they don't erase, and the newest evidence wins:\n     a reflex is blocked while a recorded failure sits as close as the\n     wins recommending it AND is newer than the newest such win. A\n     later reproduction lifts an older veto; a later failure\n     re-imposes it. After drift, expect a few wrong firings while\n     failures arrive. Use matches(), never a consensus vote, for\n     vetoes. decide(min_veto_count=2) demands corroborated failures:\n     harder to sabotage, slower to stop.\n  4. One question, several true answers: when a situation genuinely\n     has many outcomes (a file imports five modules), confidence\n     splits across them and no single one clears 0.5. That is not\n     disagreement. Read answers() and gate each outcome on its own\n     count instead of on its share.\n  5. Precedent never overrides a proof: auth, money conservation,\n     state-machine legality stay hand-written.\n\nMORE THAN ONE AGENT. Private kernel per agent; one shared kernel per\nteam, author= set so receipts show who grounded what. Share a file\nlive (WAL + refresh) or ship and merge(). Verify before you trust:\nreplay incoming receipts against your own world before merging.\nMeaning is operational at every scale: a concept is meaningful exactly\nto the degree its glyph's neighborhood predicts the world; a\nteammate's precedent is trustworthy exactly to the degree its\nreceipts replay.\n\nSTORES OUTLIVE ENCODINGS. Every file records the encoding it was\nwritten under. Opening (or merging) a file from an older encoding\nre-encodes its glyphs from the stored situations and events, so old\nprecedent keeps matching fresh queries. Events are stored with each\nprecedent, so re-encoding is lossless (rows written before events\nwere stored re-encode without their trajectory).\n";

/** The substrate guidance. Read it before recording or querying. */
export function spec(): string {
  return SPEC;
}

// ── numpy-exact randomness ──────────────────────────────────────────
// symbol() in Python is RandomState(uint32 seed).randint(0, 2, dim,
// dtype=int8) * 2 - 1. That is MT19937 seeded with init_genrand(seed),
// and randint over [0, 2) as int8 draws one 32-bit word per four
// outputs, low byte first, keeping bit 0 of each byte (mask 1, range 1,
// so no draw is ever rejected).

function mt19937(seed: number): () => number {
  const key = new Uint32Array(624);
  key[0] = seed >>> 0;
  for (let i = 1; i < 624; i++) {
    const prev = key[i - 1] ^ (key[i - 1] >>> 30);
    key[i] = (Math.imul(1812433253, prev) + i) >>> 0;
  }
  let pos = 624;
  return () => {
    if (pos >= 624) {
      for (let i = 0; i < 624; i++) {
        const y = (key[i] & 0x80000000) | (key[(i + 1) % 624] & 0x7fffffff);
        let v = key[(i + 397) % 624] ^ (y >>> 1);
        if (y & 1) v ^= 0x9908b0df;
        key[i] = v >>> 0;
      }
      pos = 0;
    }
    let y = key[pos++];
    y ^= y >>> 11;
    y ^= (y << 7) & 0x9d2c5680;
    y ^= (y << 15) & 0xefc60000;
    y ^= y >>> 18;
    return y >>> 0;
  };
}

function bipolar(seed: number, dim: number): Glyph {
  const next = mt19937(seed);
  const out = new Int8Array(dim);
  let buf = 0;
  let left = 0;
  for (let i = 0; i < dim; i++) {
    if (left === 0) {
      buf = next();
      left = 3;
    } else {
      buf >>>= 8;
      left--;
    }
    out[i] = (buf & 1) * 2 - 1;
  }
  return out;
}

function seedOf(digest: Buffer): number {
  return digest.readUInt32LE(0);
}

function bytesOf(g: Glyph): Buffer {
  return Buffer.from(g.buffer, g.byteOffset, g.byteLength);
}

function glyphHash(g: Glyph): string {
  return createHash("sha256").update(bytesOf(g)).digest("hex");
}

// ── primitives ──────────────────────────────────────────────────────

const symbols = new Map<string, Glyph>();

/** Deterministic bipolar (+1/-1) symbol for a key. Same (key, seed, dim)
 *  gives the identical vector on any machine, in either language. */
export function symbol(key: string, seed = 42, dim = DIM): Glyph {
  const id = `${seed}\u0000${dim}\u0000${key}`;
  let g = symbols.get(id);
  if (!g) {
    const digest = createHash("sha256").update(`${seed}:${key}`, "utf8").digest();
    g = bipolar(seedOf(digest), dim);
    symbols.set(id, g);
  }
  return g.slice();
}

/** Associate two glyphs (elementwise multiply). Self-inverse. */
export function bind(a: Glyph, b: Glyph): Glyph {
  const out = new Int8Array(a.length);
  for (let i = 0; i < a.length; i++) out[i] = a[i] * b[i];
  return out;
}

/** Tie-break for a majority vote: a pseudo-random glyph seeded by the
 *  hash of the parts as a SET (their bytes, sorted). See the Python
 *  kernel for why: order-free, uncorrelated with any single part. */
function tiebreak(parts: Glyph[]): Glyph {
  const h = createHash("sha256");
  for (const b of parts.map(bytesOf).sort(Buffer.compare)) h.update(b);
  return bipolar(seedOf(h.digest()), parts[0].length);
}

/** Superpose glyphs (majority vote). Resembles all inputs; order-free.
 *  weights: one per part, finite and >= 0 — a part's voice in the vote
 *  (0 drops it). Summed in a canonical order (parts by their bytes), so
 *  it stays order-free and bit-identical to Python. */
export function bundle(parts: Glyph[], weights?: number[] | null): Glyph {
  if (parts.length === 0) throw new Error("cannot bundle nothing");
  if (weights != null) return weightedBundle(parts, weights);
  const dim = parts[0].length;
  const total = new Int32Array(dim);
  for (const p of parts) for (let i = 0; i < dim; i++) total[i] += p[i];
  const out = new Int8Array(dim);
  let tie: Glyph | null = null;
  for (let i = 0; i < dim; i++) {
    const t = total[i];
    if (t > 0) out[i] = 1;
    else if (t < 0) out[i] = -1;
    else out[i] = (tie ??= tiebreak(parts))[i];
  }
  return out;
}

function weightedBundle(parts: Glyph[], weights: number[]): Glyph {
  if (weights.length !== parts.length) throw new ValueError(`${parts.length} parts but ${weights.length} weights`);
  const pairs = parts
    .map((p, i) => ({ p, b: bytesOf(p), w: checkWeight(weights[i]) }))
    .filter((x) => x.w > 0)
    .sort((x, y) => Buffer.compare(x.b, y.b) || x.w - y.w);
  if (pairs.length === 0) throw new ValueError("cannot bundle when every weight is 0");
  const dim = pairs[0].p.length;
  const acc = new Float64Array(dim);
  for (const { p, w } of pairs) for (let i = 0; i < dim; i++) acc[i] += w * p[i];
  const out = new Int8Array(dim);
  let tie: Glyph | null = null;
  for (let i = 0; i < dim; i++) {
    const a = acc[i];
    if (a > 0) out[i] = 1;
    else if (a < 0) out[i] = -1;
    else out[i] = (tie ??= tiebreak(pairs.map((x) => x.p)))[i];
  }
  return out;
}

function checkWeight(w: unknown): number {
  if (typeof w !== "number") throw new TypeError("weight must be a number");
  if (!Number.isFinite(w) || w < 0) throw new ValueError(`weight must be finite and >= 0, got ${text(w)}`);
  return w;
}

/** Errors named as the Python kernel names them, so tool errors read the same. */
class ValueError extends Error {
  override name = "ValueError";
}

/** Rotate a glyph (np.roll): order, position, depth. roll(v, -k) undoes. */
export function roll(v: Glyph, k = 1): Glyph {
  const n = v.length;
  const s = ((k % n) + n) % n;
  const out = new Int8Array(n);
  for (let i = 0; i < n; i++) out[(i + s) % n] = v[i];
  return out;
}

/** Cosine similarity for bipolar glyphs, in [-1, 1]. */
export function sim(a: Glyph, b: Glyph): number {
  let dot = 0;
  for (let i = 0; i < a.length; i++) dot += a[i] * b[i];
  return dot / a.length;
}

// ── data: structure in, glyph out; weighted sim, fact trees back ────
//
// Any JSON-shaped value encodes. An object is a weighted bundle of
// bind(attr:key, child); an array is a bundle of its items (a set:
// order belongs in a Strand); a scalar is the symbol of its text. A
// nested object or array is rolled once before it binds, so
// {"a": {"b": x}} and {"b": {"a": x}} stay apart. A flat object of
// strings encodes exactly as a Space situation always has.
//
// Weights mirror the data: {"risk": 1.0, "plan": {"*": 0.5, "step": 2}}.
// A number weighs that key; an object weighs inside it, its own weight
// under "*". Unlisted keys weigh 1.0; weights for absent keys are ignored.

type Inner = Weights | null;

function isObject(v: unknown): v is { [key: string]: Data } {
  return v !== null && typeof v === "object" && !Array.isArray(v);
}

/** A scalar's text, the same in every language. */
function text(v: unknown): string {
  if (typeof v === "string") return v;
  if (v === null) return "null";
  if (typeof v === "boolean") return v ? "true" : "false";
  if (typeof v === "number") return String(v);
  throw new TypeError(`cannot encode a ${typeof v}: ${String(v)}`);
}

function own<T>(o: { [key: string]: T } | null, key: string): T | undefined {
  return o && Object.hasOwn(o, key) ? o[key] : undefined;
}

function weightOf(w: unknown): [number, Inner] {
  if (w === undefined || w === null) return [1, null];
  if (isObject(w)) return [Object.hasOwn(w, "*") ? checkWeight(w["*"]) : 1, w as Weights];
  return [checkWeight(w), null];
}

function keyed(data: { [key: string]: Data }, weights: Inner, seed: number, dim: number): [Glyph[], number[]] {
  const parts: Glyph[] = [];
  const ws: number[] = [];
  for (const key of Object.keys(data).sort(cmpCodePoints)) {
    const [w, inner] = weightOf(own(weights, key));
    const value = data[key];
    let child = encodeNode(value, inner, seed, dim);
    if (value !== null && typeof value === "object") child = roll(child, 1);
    parts.push(bind(symbol(`attr:${key}`, seed, dim), child));
    ws.push(w);
  }
  return [parts, ws];
}

function encodeNode(data: Data, weights: Inner, seed: number, dim: number): Glyph {
  if (Array.isArray(data)) {
    if (data.length === 0) throw new ValueError("cannot encode an empty array");
    return bundle(data.map((x) => encodeNode(x, null, seed, dim)));
  }
  if (isObject(data)) {
    if (Object.keys(data).length === 0) throw new ValueError("cannot encode an empty object");
    const [parts, ws] = keyed(data, weights, seed, dim);
    return bundle(parts, ws);
  }
  return symbol(`val:${text(data)}`, seed, dim);
}

/** One glyph for any JSON-shaped value, with weights at every level. */
export function encode(data: Data, weights?: Weights | null, seed = 42, dim = DIM): Glyph {
  return encodeNode(data, weights ?? null, seed, dim);
}

const ABSENT: unique symbol = Symbol("absent");
type Side = Data | typeof ABSENT;

/** Python's repr() of a float, for values stored as text. */
function pyRepr(x: number): string {
  return Number.isInteger(x) ? `${x}.0` : String(x);
}

function two(x: number): string {
  return (pyRound(x, 2) + 0).toFixed(2); // no "-0.00"
}

function four(x: number): number {
  return pyRound(x, 4) + 0; // no -0
}

/** Python's format(x, "g"): 6 significant digits, exponent outside [1e-4, 1e6). */
function formatG(x: number): string {
  if (x === 0) return "0";
  const [mant, expText] = x.toExponential(5).split("e");
  const exp = Number(expText);
  const strip = (s: string) => (s.includes(".") ? s.replace(/0+$/, "").replace(/\.$/, "") : s);
  if (exp < -4 || exp >= 6) return `${strip(mant)}e${exp < 0 ? "-" : "+"}${String(Math.abs(exp)).padStart(2, "0")}`;
  return strip(x.toFixed(Math.max(0, 5 - exp)));
}

/** One node of a fact tree: how one part of a query compares with the
 *  same part of a record. score: the exact weighted sim of this subtree;
 *  share: weight * score / the siblings' total weight (shares sum to the
 *  parent's score); sim: the glyph sim of the two subtrees. */
export class Fact {
  constructor(
    public key: string,
    public weight: number,
    public score: number,
    public share: number,
    public sim: number,
    public status: "both" | "query_only" | "record_only",
    public query: Side,
    public record: Side,
    public children: Fact[],
  ) {}

  toJson(): Record<string, unknown> {
    const out: Record<string, unknown> = {
      key: this.key, weight: this.weight, score: four(this.score),
      share: four(this.share), sim: four(this.sim), status: this.status,
    };
    if (this.children.length === 0) {
      if (this.query !== ABSENT) out.query = this.query;
      if (this.record !== ABSENT) out.record = this.record;
    } else {
      out.children = this.children.map((c) => c.toJson());
    }
    return out;
  }

  toText(depth = 0): string {
    const pad = "  ".repeat(depth);
    const dump = (v: Side) => pyDumps(v, { ensureAscii: false });
    let head: string;
    if (this.children.length) head = `${pad}${this.key || "."}`;
    else if (this.status === "both") {
      head = `${pad}${this.key} = ${dump(this.record)}`;
      if (dump(this.query) !== dump(this.record)) head += ` (query ${dump(this.query)})`;
    } else head = `${pad}${this.key}: not in the ${this.status === "query_only" ? "record" : "query"}`;
    const line = `${head}  score ${two(this.score)} × w ${formatG(this.weight)} → ${two(this.share)}`;
    return [line, ...this.children.map((c) => c.toText(depth + 1))].join("\n");
  }
}

/** Each child's share of its parent; returns the parent's score. */
function tally(children: Fact[]): number {
  let total = 0;
  for (const c of children) total += c.weight;
  let score = 0;
  for (const c of children) {
    c.share = total ? (c.weight * c.score) / total : 0;
    score += c.share;
  }
  return score;
}

function explainNode(key: string, weight: number, q: Side, r: Side, weights: Inner,
  seed: number, dim: number, glyphs = true): Fact {
  if (q === ABSENT || r === ABSENT) {
    return new Fact(key, weight, 0, 0, 0, q === ABSENT ? "record_only" : "query_only", q, r, []);
  }
  if (!(isObject(q) && isObject(r))) {
    const leaf = sim(encodeNode(q, weights, seed, dim), encodeNode(r, weights, seed, dim));
    return new Fact(key, weight, leaf, 0, leaf, "both", q, r, []);
  }
  const keys = [...new Set([...Object.keys(q), ...Object.keys(r)])].sort(cmpCodePoints);
  const children = keys.map((k) => {
    const [w, inner] = weightOf(own(weights, k));
    return explainNode(k, w, Object.hasOwn(q, k) ? q[k] : ABSENT, Object.hasOwn(r, k) ? r[k] : ABSENT,
      inner, seed, dim, glyphs);
  });
  const glyphSim = glyphs ? sim(encodeNode(q, weights, seed, dim), encodeNode(r, weights, seed, dim)) : 0;
  return new Fact(key, weight, tally(children), 0, glyphSim, "both", q, r, children);
}

/** The fact tree for one query against one record: per key, how close,
 *  with what weight, and its share of the whole. root.score is the
 *  weighted sim. A key on one side only scores 0 at full weight. */
export function explain(query: Data, record: Data, weights?: Weights | null, seed = 42, dim = DIM): Fact {
  const root = explainNode("", 1, query, record, weights ?? null, seed, dim);
  root.share = root.score;
  return root;
}

// ── Strand: ordered meaning ─────────────────────────────────────────

/** A sequence of glyphs whose ORDER is part of the meaning. */
export class Strand {
  codons: Glyph[];

  constructor(codons: Glyph[] = []) {
    this.codons = [...codons];
  }

  append(codon: Glyph): this {
    this.codons.push(codon);
    return this;
  }

  state(decay = 0.7): Glyph {
    if (this.codons.length === 0) throw new Error("empty strand has no state");
    const dim = this.codons[0].length;
    const acc = new Float64Array(dim);
    const rolled: Glyph[] = [];
    const reversed = [...this.codons].reverse();
    reversed.forEach((codon, age) => {
      const shifted = roll(codon, age);
      rolled.push(shifted);
      const w = decay ** age;
      for (let i = 0; i < dim; i++) acc[i] += w * shifted[i];
    });
    const out = new Int8Array(dim);
    let tie: Glyph | null = null;
    for (let i = 0; i < dim; i++) {
      const a = acc[i];
      if (a > 0) out[i] = 1;
      else if (a < 0) out[i] = -1;
      else out[i] = (tie ??= tiebreak(rolled))[i];
    }
    return out;
  }

  get length(): number {
    return this.codons.length;
  }
}

// ── Space: graded precedent ─────────────────────────────────────────

/** What a Space says. Trust `top` only when sufficient, confident, and
 *  count is more than a couple. */
export class Answer {
  constructor(
    public sufficient: boolean,
    public confidence: number,
    public support: number,
    public count: number,
    public top: string | null,
    public outcomes: Record<string, number>,
    public receipts: Receipt[],
  ) {}

  toJson(): Record<string, unknown> {
    return {
      sufficient: this.sufficient,
      confidence: pyRound(this.confidence, 4),
      support: pyRound(this.support, 4),
      count: this.count,
      top: this.top,
      outcomes: Object.fromEntries(Object.entries(this.outcomes).map(([k, v]) => [k, pyRound(v, 4)])),
      receipts: this.receipts.map(([id, s, outcome, hash, author]) => ({
        id, sim: pyRound(s, 4), outcome, hash, author,
      })),
    };
  }
}

/** Support for one outcome in one situation, judged on its own. */
export class Evidence {
  constructor(
    public outcome: string,
    public count: number,
    public support: number,
    public nearest: number,
    public latest: number,
    public authors: string[],
  ) {}

  toJson(): Record<string, unknown> {
    return {
      outcome: this.outcome, count: this.count,
      support: pyRound(this.support, 4), nearest: pyRound(this.nearest, 4),
      latest: this.latest, authors: this.authors,
    };
  }
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
export class Space {
  readonly dim: number;
  k: number;
  minSim: number;
  readonly seed: number;
  decay: number;
  author: string;
  tau: number;
  private tauGiven: boolean;
  private ids: string[] = [];
  private outcomesOf: string[] = [];
  private authors: string[] = [];
  private tsOf: number[] = [];
  private situations: unknown[] = [];
  private trajs: (Glyph | null)[] = [];
  private glyphs: Glyph[] = [];
  private db: DatabaseSync | null = null;

  constructor(opts: SpaceOptions = {}) {
    this.dim = opts.dim ?? DIM;
    this.k = opts.k ?? 15;
    this.minSim = opts.minSim ?? 0.1;
    this.seed = opts.seed ?? 42;
    this.decay = opts.decay ?? 0.7;
    this.author = opts.author ?? "anon";
    this.tau = opts.tau ?? TAU;
    this.tauGiven = opts.tau !== undefined;
    if (opts.path) this.open(opts.path);
  }

  get size(): number {
    return this.ids.length;
  }

  /** A situation is an object (values may nest — see encode()); optional
   *  events fold in as a strand so order-carrying situations keep their
   *  order; weights weigh the situation's keys. */
  encode(situation: Situation, events?: Glyph[] | null, weights?: Weights | null): Glyph {
    if (!isObject(situation)) throw new TypeError("a situation is an object of attributes");
    const [parts, ws] = keyed(situation, weights ?? null, this.seed, this.dim);
    if (events && events.length) {
      parts.push(bind(symbol("trajectory", this.seed, this.dim), new Strand(events).state(this.decay)));
      ws.push(1);
    }
    if (parts.length === 0) throw new Error("cannot encode an empty situation");
    return bundle(parts, ws);
  }

  private traj(events?: Glyph[] | null): Glyph | null {
    return events && events.length ? new Strand(events).state(this.decay) : null;
  }

  private push(rid: string, outcome: string, glyph: Glyph, author: string, ts: number,
    situation: unknown, traj: Glyph | null): void {
    this.ids.push(rid);
    this.situations.push(situation);
    this.trajs.push(traj);
    this.outcomesOf.push(outcome);
    this.authors.push(author);
    this.tsOf.push(Number(ts));
    this.glyphs.push(glyph);
  }

  record(situation: Situation, outcome: string,
    opts: { events?: Glyph[]; rid?: string; ts?: number } = {}): string {
    const rid = opts.rid ?? randomUUID().slice(0, 12);
    const ts = opts.ts ?? Date.now() / 1000;
    const glyph = this.encode(situation, opts.events);
    this.push(rid, outcome, glyph, this.author, ts, situation, this.traj(opts.events));
    if (this.db) {
      this.db.prepare(
        "INSERT OR REPLACE INTO precedents (id, situation, outcome, dim, glyph, author, ts, events)" +
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
      ).run(rid, pyDumps(situation, { ensureAscii: false }), outcome, this.dim,
        bytesOf(glyph), this.author, ts, eventsBlob(opts.events));
    }
    return rid;
  }

  private sims(situation: Situation, events?: Glyph[] | null): Float64Array {
    const q = this.encode(situation, events);
    const out = new Float64Array(this.glyphs.length);
    for (let r = 0; r < this.glyphs.length; r++) out[r] = sim(this.glyphs[r], q);
    return out;
  }

  /** Precedent i explained against the situation; events, when either
   *  side has them, are one more key: "~events". */
  private exact(i: number, situation: Situation, traj: Glyph | null, weights: Weights | null,
    glyphs = false): Fact {
    const root = explainNode("", 1, situation, this.situations[i] as Data, weights, this.seed, this.dim, glyphs);
    const theirs = this.trajs[i];
    if ((traj || theirs) && root.children.length) {
      const [w] = weightOf(own(weights, "~events"));
      if (traj && theirs) {
        const s = sim(traj, theirs);
        root.children.push(new Fact("~events", w, s, 0, s, "both", "…", "…", []));
      } else {
        root.children.push(new Fact("~events", w, 0, 0, 0, theirs ? "record_only" : "query_only",
          traj ? "…" : ABSENT, theirs ? "…" : ABSENT, []));
      }
      root.score = tally(root.children);
    }
    root.share = root.score;
    return root;
  }

  /** The similarity every read ranks and gates on: the glyph sim, or —
   *  when the caller weighs the keys — the exact weighted sim. */
  private scores(situation: Situation, events?: Glyph[] | null, weights?: Weights | null): Float64Array {
    if (weights == null) return this.sims(situation, events);
    this.encode(situation, events, weights); // same errors either way
    const traj = this.traj(events);
    const out = new Float64Array(this.size);
    for (let i = 0; i < this.size; i++) out[i] = this.exact(i, situation, traj, weights).score;
    return out;
  }

  private topIndices(sims: Float64Array, k = this.k): number[] {
    // highest first; equal sims, later row first
    const idx = Array.from(sims.keys());
    idx.sort((a, b) => sims[b] - sims[a] || b - a);
    return idx.slice(0, k);
  }

  private hashOf(i: number): string {
    return glyphHash(this.glyphs[i]).slice(0, 16);
  }

  /** weights: the query's weights tree. Weighted, every similarity is the
   *  exact weighted sim (a fact tree's score); unweighted, the glyph sim. */
  query(situation: Situation, events?: Glyph[] | null, weights?: Weights | null): Answer {
    if (this.size === 0) return new Answer(false, 0, 0, 0, null, {}, []);
    const sims = this.scores(situation, events, weights);
    const top = this.topIndices(sims);
    const receipts: Receipt[] = top.map((i) => [
      this.ids[i], sims[i], this.outcomesOf[i], this.hashOf(i), this.authors[i],
    ]);
    const voters = top.filter((i) => sims[i] >= this.minSim);
    if (voters.length === 0) return new Answer(false, 0, Math.max(sims[top[0]], 0), 0, null, {}, receipts);
    let wsum = 0;
    for (const i of voters) wsum += sims[i];
    wsum = wsum || 1;
    const outcomes: Record<string, number> = {};
    for (const i of voters) outcomes[this.outcomesOf[i]] = (outcomes[this.outcomesOf[i]] ?? 0) + sims[i];
    for (const o of Object.keys(outcomes)) outcomes[o] /= wsum;
    let topOutcome = Object.keys(outcomes)[0];
    for (const o of Object.keys(outcomes)) if (outcomes[o] > outcomes[topOutcome]) topOutcome = o;
    let mean = 0;
    for (const i of voters) mean += sims[i];
    mean /= voters.length;
    return new Answer(true, outcomes[topOutcome], mean, voters.length, topOutcome, outcomes, receipts);
  }

  private evidenceFrom(sims: Float64Array, outcome: string, bar: number): Evidence {
    const idx: number[] = [];
    for (let i = 0; i < this.size; i++) if (this.outcomesOf[i] === outcome && sims[i] >= bar) idx.push(i);
    if (idx.length === 0) return new Evidence(outcome, 0, 0, 0, 0, []);
    let sum = 0;
    let max = -Infinity;
    let latest = -Infinity;
    for (const i of idx) {
      sum += sims[i];
      max = Math.max(max, sims[i]);
      latest = Math.max(latest, this.tsOf[i]);
    }
    const who = [...new Set(idx.map((i) => this.authors[i]))].sort(cmpCodePoints);
    return new Evidence(outcome, idx.length, sum / idx.length, max, latest, who);
  }

  /** Support for ONE candidate outcome, over every precedent. */
  evidence(situation: Situation, outcome: string,
    opts: { events?: Glyph[]; minSim?: number; weights?: Weights | null } = {}): Evidence {
    if (this.size === 0) return new Evidence(outcome, 0, 0, 0, 0, []);
    return this.evidenceFrom(this.scores(situation, opts.events, opts.weights), outcome, opts.minSim ?? this.minSim);
  }

  /** Every outcome with qualifying precedent, strongest first (SPEC rule 4). */
  answers(situation: Situation, opts: { events?: Glyph[]; minCount?: number; weights?: Weights | null } = {}): Evidence[] {
    if (this.size === 0) return [];
    const sims = this.scores(situation, opts.events, opts.weights);
    const found = new Set<string>();
    for (let i = 0; i < this.size; i++) if (sims[i] >= this.minSim) found.add(this.outcomesOf[i]);
    return [...found]
      .map((o) => this.evidenceFrom(sims, o, this.minSim))
      .filter((e) => e.count >= (opts.minCount ?? 1))
      .sort((a, b) => b.count - a.count || b.support - a.support || cmpCodePoints(a.outcome, b.outcome));
  }

  /** Max similarity among precedents with THIS outcome: the veto primitive. */
  matches(situation: Situation, outcome: string, events?: Glyph[] | null, weights?: Weights | null): number {
    if (!this.outcomesOf.includes(outcome)) return 0;
    const sims = this.scores(situation, events, weights);
    let best = -Infinity;
    for (let i = 0; i < this.size; i++) if (this.outcomesOf[i] === outcome) best = Math.max(best, sims[i]);
    return best;
  }

  /** The exact read: every precedent scored by weighted sim (unweighted
   *  keys weigh 1), the `top` (default k) best each explained as a fact
   *  tree with its glyph sim and citation. Ranked by score, then glyph
   *  sim, newest, id; rows under minScore (if given) are left out. */
  facts(situation: Situation,
    opts: { events?: Glyph[]; weights?: Weights | null; top?: number; minScore?: number } = {}): FactTree[] {
    if (this.size === 0) return [];
    const sims = this.sims(situation, opts.events);
    const scores = this.scores(situation, opts.events, opts.weights ?? {});
    const order = Array.from(scores.keys())
      .filter((i) => opts.minScore === undefined || scores[i] >= opts.minScore)
      .sort((a, b) => scores[b] - scores[a] || sims[b] - sims[a] || this.tsOf[b] - this.tsOf[a] ||
        cmpCodePoints(this.ids[a], this.ids[b]));
    const traj = this.traj(opts.events);
    const probs = this.probs(scores, this.tau);
    return order.slice(0, opts.top ?? this.k).map((i) => new FactTree(
      this.ids[i], this.outcomesOf[i], this.authors[i], this.tsOf[i], this.hashOf(i), sims[i],
      this.exact(i, situation, traj, opts.weights ?? null, true), probs[this.outcomesOf[i]] ?? 0));
  }

  /** P(outcome | situation) over the POOL nearest by exact weighted sim:
   *  a softmax of their scores at temperature tau, summed per outcome. */
  probabilities(situation: Situation, opts: { events?: Glyph[]; weights?: Weights | null } = {}): Record<string, number> {
    if (this.size === 0) return {};
    return this.probs(this.scores(situation, opts.events, opts.weights ?? {}), this.tau);
  }

  private probs(scores: Float64Array, tau: number, skip = -1): Record<string, number> {
    const order = this.topIndices(scores, scores.length).filter((i) => i !== skip).slice(0, POOL);
    if (order.length === 0) return {};
    const top = scores[order[0]];
    const mass: Record<string, number> = {};
    for (const i of order) {
      const o = this.outcomesOf[i];
      mass[o] = (mass[o] ?? 0) + Math.exp((scores[i] - top) / tau);
    }
    let z = 0;
    for (const m of Object.values(mass)) z += m;
    return Object.fromEntries(Object.entries(mass).map(([o, m]) => [o, m / z]));
  }

  /** Fit tau by holding out each of the `sample` newest precedents in
   *  turn (least log-loss over TAUS); saved in the file. Returns tau. */
  calibrate(opts: { sample?: number; weights?: Weights | null } = {}): number {
    if (this.size < 10) throw new ValueError("calibrate needs at least 10 precedents");
    const held = Array.from(this.ids.keys()).slice(-(opts.sample ?? 100));
    const scored = held.map((h) => [h, this.scores(this.situations[h] as Situation, null, opts.weights ?? {})] as const);
    let best: [number, number] = [Infinity, TAU];
    for (const tau of TAUS) {
      let loss = 0;
      for (const [h, scores] of scored) {
        loss -= Math.log(Math.max(this.probs(scores, tau, h)[this.outcomesOf[h]] ?? 0, 1e-6));
      }
      if (loss < best[0]) best = [loss, tau];
    }
    this.tau = best[1];
    this.tauGiven = false;
    this.db?.prepare("INSERT OR REPLACE INTO meta VALUES ('tau', ?)").run(pyRepr(this.tau));
    return this.tau;
  }

  // persistence: one portable file; WAL so several agents can share it
  private open(path: string): void {
    const p = expand(path);
    mkdirSync(dirname(p), { recursive: true });
    this.db = new DatabaseSync(p);
    this.db.exec("PRAGMA journal_mode=WAL");
    this.db.exec("PRAGMA busy_timeout=10000");
    ensureSchema(this.db);
    if (fileEncoding(this.db) < ENCODING) reencodeRows(this.db, this);
    const saved = this.db.prepare("SELECT value FROM meta WHERE key = 'tau'").get();
    if (saved && !this.tauGiven) this.tau = Number(saved.value);
    this.refresh();
  }

  /** Pull in rows other agents wrote to this file since open. */
  refresh(): number {
    if (!this.db) return 0;
    const known = new Set(this.ids);
    let added = 0;
    for (const r of this.db.prepare(
      "SELECT id, situation, outcome, dim, glyph, author, ts, events FROM precedents ORDER BY ts, rowid").all()) {
      const rid = r.id as string;
      if (known.has(rid)) continue;
      if (Number(r.dim) !== this.dim) throw new Error(`precedent ${rid} has dim ${r.dim}, space is ${this.dim}`);
      this.push(rid, r.outcome as string, toGlyph(r.glyph as Uint8Array), r.author as string, Number(r.ts),
        situationOf(r.situation as string), this.traj(eventsFromBlob(r.events as Uint8Array | null, this.dim)));
      added++;
    }
    return added;
  }

  /** Union another Space file into this one (by precedent id). Rows from
   *  an older encoding are re-encoded on the way in. */
  merge(otherPath: string): number {
    const other = new DatabaseSync(expand(otherPath));
    try {
      const cols = new Set(other.prepare("PRAGMA table_info(precedents)").all().map((c) => c.name as string));
      const stale = fileEncoding(other) < ENCODING;
      const sql = "SELECT id, situation, outcome, dim, glyph, " +
        `${cols.has("author") ? "author" : "'anon'"} AS author, ` +
        `${cols.has("ts") ? "ts" : "0.0"} AS ts, ` +
        `${cols.has("events") ? "events" : "NULL"} AS events FROM precedents`;
      const known = new Set(this.ids);
      let added = 0;
      if (this.db) this.db.exec("BEGIN");
      for (const r of other.prepare(sql).all()) {
        const rid = r.id as string;
        if (known.has(rid)) continue;
        const dim = Number(r.dim);
        if (dim !== this.dim) throw new Error(`precedent ${rid} has dim ${dim}, space is ${this.dim}`);
        const glyph = stale
          ? this.encode(JSON.parse(r.situation as string), eventsFromBlob(r.events as Uint8Array | null, dim))
          : toGlyph(r.glyph as Uint8Array);
        this.push(rid, r.outcome as string, glyph, r.author as string, Number(r.ts),
          situationOf(r.situation as string), this.traj(eventsFromBlob(r.events as Uint8Array | null, dim)));
        this.db?.prepare(
          "INSERT OR REPLACE INTO precedents (id, situation, outcome, dim, glyph, author, ts, events)" +
          " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ).run(rid, r.situation as string, r.outcome as string, dim, bytesOf(glyph),
          r.author as string, Number(r.ts), (r.events as Uint8Array | null) ?? null);
        added++;
      }
      if (this.db) this.db.exec("COMMIT");
      return added;
    } finally {
      other.close();
    }
  }

  close(): void {
    this.db?.close();
    this.db = null;
  }
}

/** One precedent explained against a situation (Space.facts()). score is
 *  the exact weighted sim; sim the glyph sim; the rest cites it. */
export class FactTree {
  constructor(
    public id: string,
    public outcome: string,
    public author: string,
    public ts: number,
    public hash: string,
    public sim: number,
    public root: Fact,
    public probability = 0,
  ) {}

  get score(): number {
    return this.root.score;
  }

  toJson(): Record<string, unknown> {
    return {
      id: this.id, outcome: this.outcome, probability: four(this.probability),
      score: four(this.score), sim: four(this.sim),
      author: this.author, ts: this.ts, hash: this.hash, tree: this.root.toJson(),
    };
  }

  toText(): string {
    return `${this.outcome}  p ${two(this.probability)}  score ${two(this.score)}  (sim ${two(this.sim)}, ` +
      `${this.id} by ${this.author})\n` +
      this.root.toText(1);
  }
}

// ── the contract as a function ──────────────────────────────────────

/** What decide() concluded. Act on `outcome` only when `act`. */
export class Decision {
  constructor(
    public act: boolean,
    public outcome: string | null,
    public reason: "reflex" | "insufficient" | "uncalibrated" | "low_confidence" | "vetoed",
    public answer: Answer,
    public veto: Evidence | null,
    public lifted: boolean,
  ) {}

  toJson(): Record<string, unknown> {
    return {
      act: this.act, outcome: this.outcome, reason: this.reason, lifted: this.lifted,
      veto: this.veto ? this.veto.toJson() : null, answer: this.answer.toJson(),
    };
  }
}

/** THE CONTRACT (see SPEC): three trust gates on the wins, then the veto
 *  check, with the newest evidence winning. */
export function decide(wins: Space, vetoes: Space, situation: Situation,
  opts: { events?: Glyph[]; minConfidence?: number; minCount?: number; minVetoCount?: number;
    weights?: Weights | null } = {}): Decision {
  const minConfidence = opts.minConfidence ?? 0.5;
  const minCount = opts.minCount ?? 3;
  const minVetoCount = opts.minVetoCount ?? 1;
  const answer = wins.query(situation, opts.events, opts.weights);
  if (!answer.sufficient) return new Decision(false, null, "insufficient", answer, null, false);
  const top = answer.top!;
  const veto = vetoes.evidence(situation, top,
    { events: opts.events, minSim: Math.max(answer.support, 1e-9), weights: opts.weights });
  const win = wins.evidence(situation, top, { events: opts.events, weights: opts.weights });
  const close = veto.count >= minVetoCount;
  const lifted = close && win.latest > veto.latest;
  if (close && !lifted) return new Decision(false, top, "vetoed", answer, veto, false);
  const shown = veto.count ? veto : null;
  if (answer.count < minCount) return new Decision(false, top, "uncalibrated", answer, shown, lifted);
  if (answer.confidence < minConfidence) return new Decision(false, top, "low_confidence", answer, shown, lifted);
  return new Decision(true, top, "reflex", answer, shown, lifted);
}

/** Re-encode every precedent's glyph from its stored situation and events
 *  under the current encoding, and stamp the file. Returns rows re-encoded. */
export function reencodeStore(path: string, opts: SpaceOptions = {}): number {
  const db = new DatabaseSync(expand(path));
  try {
    ensureSchema(db);
    return reencodeRows(db, new Space({ ...opts, path: undefined }));
  } finally {
    db.close();
  }
}

// ── store schema and migration ──────────────────────────────────────

function expand(path: string): string {
  return resolve(path.startsWith("~") ? homedir() + path.slice(1) : path);
}

function toGlyph(blob: Uint8Array): Glyph {
  return new Int8Array(blob.buffer, blob.byteOffset, blob.byteLength).slice();
}

function eventsBlob(events?: Glyph[] | null): Uint8Array | null {
  if (!events || events.length === 0) return null;
  const out = new Int8Array(events.length * events[0].length);
  events.forEach((e, i) => out.set(e, i * e.length));
  return bytesOf(out);
}

function situationOf(text: string | null | undefined): unknown {
  try {
    return text ? JSON.parse(text) : null;
  } catch {
    return null;
  }
}

function eventsFromBlob(blob: Uint8Array | null | undefined, dim: number): Glyph[] | null {
  if (!blob || blob.byteLength === 0) return null;
  const flat = toGlyph(blob);
  const out: Glyph[] = [];
  for (let i = 0; i < flat.length; i += dim) out.push(flat.slice(i, i + dim));
  return out;
}

function ensureSchema(db: DatabaseSync): void {
  db.exec(
    "CREATE TABLE IF NOT EXISTS precedents (" +
    " id TEXT PRIMARY KEY, situation TEXT NOT NULL," +
    " outcome TEXT NOT NULL, dim INTEGER NOT NULL," +
    " glyph BLOB NOT NULL, author TEXT NOT NULL DEFAULT 'anon'," +
    " ts REAL NOT NULL DEFAULT 0, events BLOB)");
  db.exec("CREATE TABLE IF NOT EXISTS meta ( key TEXT PRIMARY KEY, value TEXT NOT NULL)");
  const cols = new Set(db.prepare("PRAGMA table_info(precedents)").all().map((c) => c.name as string));
  if (!cols.has("author")) db.exec("ALTER TABLE precedents ADD COLUMN author TEXT NOT NULL DEFAULT 'anon'");
  if (!cols.has("ts")) db.exec("ALTER TABLE precedents ADD COLUMN ts REAL NOT NULL DEFAULT 0");
  if (!cols.has("events")) db.exec("ALTER TABLE precedents ADD COLUMN events BLOB");
  const rows = Number(db.prepare("SELECT COUNT(*) AS n FROM precedents").get()!.n);
  const stamped = db.prepare("SELECT value FROM meta WHERE key = 'encoding'").get();
  if (!stamped) db.prepare("INSERT INTO meta VALUES ('encoding', ?)").run(String(rows === 0 ? ENCODING : 1));
}

function fileEncoding(db: DatabaseSync): number {
  try {
    const row = db.prepare("SELECT value FROM meta WHERE key = 'encoding'").get();
    if (row) return Number(row.value);
  } catch { /* no meta table: an old file */ }
  try {
    const n = Number(db.prepare("SELECT COUNT(*) AS n FROM precedents").get()!.n);
    return n === 0 ? ENCODING : 1;
  } catch {
    return ENCODING;
  }
}

function reencodeRows(db: DatabaseSync, space: Space): number {
  const rows = db.prepare("SELECT id, situation, dim, events FROM precedents").all();
  let done = 0;
  db.exec("BEGIN");
  try {
    const update = db.prepare("UPDATE precedents SET glyph = ?, dim = ? WHERE id = ?");
    for (const r of rows) {
      let glyph: Glyph;
      try {
        glyph = space.encode(JSON.parse(r.situation as string),
          eventsFromBlob(r.events as Uint8Array | null, space.dim));
      } catch {
        continue; // no usable situation stored: keep the old glyph
      }
      update.run(bytesOf(glyph), space.dim, r.id as string);
      done++;
    }
    db.prepare("INSERT OR REPLACE INTO meta VALUES ('encoding', ?)").run(String(ENCODING));
    db.exec("COMMIT");
  } catch (e) {
    db.exec("ROLLBACK");
    throw e;
  }
  return done;
}
