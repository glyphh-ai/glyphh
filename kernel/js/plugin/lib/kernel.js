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
export const DIM = 4096; // default dimensionality; ~1e-3 cross-talk between random symbols
export const ENCODING = 2; // bump when encode() changes; stores re-encode on open
export const SPEC = "Ada kernel — substrate guidance for the agent using it\n\nWHAT THIS IS. Your state and execution layer beyond the context\nwindow. Contexts are mortal; the SQLite files a Space writes are not.\nRecord graded experience as you work; the next context (yours or\nanother agent's) reopens the files and inherits ground truth instead\nof prose about it.\n\nTHE FIVE PRIMITIVES. All glyphs are bipolar +/-1 vectors of one fixed\ndimension (default 4096); every operation returns the type it takes,\nso composites nest indefinitely.\n  symbol(key, seed=42, dim)  deterministic glyph: same inputs -> the\n      identical vector on any machine, forever. Shared seed = shared\n      vocabulary between agents; different seeds are mutual noise.\n  bind(a, b)     associate (elementwise multiply). Self-inverse; the\n      result resembles neither input. Use for role-filler pairs.\n  bundle(parts)  superpose (majority vote); resembles ALL inputs.\n      Order-free: the same parts in any order give the same glyph.\n      Capacity is finite: past a few dozen parts detail fades and gist\n      survives — that is abstraction; keep receipts for the detail.\n  roll(v, k)     rotate: order, position, depth. Undo with roll(v,-k).\n  sim(a, b)      cosine in [-1, 1]. Random glyphs sit near 0. For\n      situations, sim tracks the FRACTION OF SHARED ATTRIBUTE PAIRS,\n      whichever attributes they are (measured, 4 attributes: sharing\n      1/2/3 -> 0.14/0.28/0.44; 2 attributes sharing 1 -> 0.25), even\n      when the shared attributes are decision-irrelevant.\n\nTHE TWO CONSTRUCTS.\n  Strand: ordered meaning. append() glyphs; state(decay) folds the\n      sequence into one glyph where recent items dominate and order\n      matters. Detail recoverable a few steps back; the KIND of\n      trajectory recognizable much longer.\n  Space(dim, k, min_sim, seed, decay, author, path): graded precedent.\n      record(situation, outcome, events=None, ts=None) — one write,\n      permanent, time-stamped.\n      query(...) -> Answer(sufficient, confidence, support, count,\n      top, outcomes, receipts); only precedents clearing min_sim vote.\n      answers(...) -> [Evidence] for EVERY outcome with qualifying\n      precedent: the read for situations with more than one true\n      outcome. evidence(situation, outcome) grades one candidate.\n      matches(situation, outcome) — max sim among precedents with THAT\n      outcome: the veto primitive, undilutable by consensus.\n      refresh() pulls rows other agents wrote to a shared WAL file;\n      merge(other_path) unions another Space file by id, authors kept.\n\nTHE CONTRACT: NOTHING UNGRADED. Route every domain decision through\ndecide(wins, vetoes, situation, events) -> Decision. It is:\n  a = wins.query(situation, events)\n  if a.sufficient and a.confidence >= 0.5 and a.count >= 3:\n      if not vetoed(a.top):               # see rule 3\n          act(a.top)                      # reflex: free, cited\n      else: consult fallback              # vetoed\n  else: consult fallback                  # insufficient precedent\n  success = the WORLD grades the action   # never self-graded\n  (wins if success else vetoes).record(situation, action, events)\nFallback chain by cost: reflex (free) -> consultant (paid) -> human\n(last resort; the answer is itself a grade). Consult rate should fall\nover the Space's life — that curve is the product metric.\n\nRULES THAT DECIDE WHETHER IT WORKS.\n  1. Trust needs three gates: sufficient (similarity), confidence\n     (consensus), count (population). A consensus of one is\n     confidence 1.0 and means almost nothing — gate count >= 3.\n  2. Attribute hygiene: encode ONLY decision-relevant attributes;\n     incidental ones (ids, regions, timestamps) poison neighborhoods.\n     Size min_sim as the attribute-overlap fraction that should count\n     as 'the same kind of situation'.\n  3. Vetoes suppress, they don't erase, and the newest evidence wins:\n     a reflex is blocked while a recorded failure sits as close as the\n     wins recommending it AND is newer than the newest such win. A\n     later reproduction lifts an older veto; a later failure\n     re-imposes it. After drift, expect a few wrong firings while\n     failures arrive. Use matches(), never a consensus vote, for\n     vetoes. decide(min_veto_count=2) demands corroborated failures:\n     harder to sabotage, slower to stop.\n  4. One question, several true answers: when a situation genuinely\n     has many outcomes (a file imports five modules), confidence\n     splits across them and no single one clears 0.5. That is not\n     disagreement. Read answers() and gate each outcome on its own\n     count instead of on its share.\n  5. Precedent never overrides a proof: auth, money conservation,\n     state-machine legality stay hand-written.\n\nMORE THAN ONE AGENT. Private kernel per agent; one shared kernel per\nteam, author= set so receipts show who grounded what. Share a file\nlive (WAL + refresh) or ship and merge(). Verify before you trust:\nreplay incoming receipts against your own world before merging.\nMeaning is operational at every scale: a concept is meaningful exactly\nto the degree its glyph's neighborhood predicts the world; a\nteammate's precedent is trustworthy exactly to the degree its\nreceipts replay.\n\nSTORES OUTLIVE ENCODINGS. Every file records the encoding it was\nwritten under. Opening (or merging) a file from an older encoding\nre-encodes its glyphs from the stored situations and events, so old\nprecedent keeps matching fresh queries. Events are stored with each\nprecedent, so re-encoding is lossless (rows written before events\nwere stored re-encode without their trajectory).\n";
/** The substrate guidance. Read it before recording or querying. */
export function spec() {
    return SPEC;
}
// ── numpy-exact randomness ──────────────────────────────────────────
// symbol() in Python is RandomState(uint32 seed).randint(0, 2, dim,
// dtype=int8) * 2 - 1. That is MT19937 seeded with init_genrand(seed),
// and randint over [0, 2) as int8 draws one 32-bit word per four
// outputs, low byte first, keeping bit 0 of each byte (mask 1, range 1,
// so no draw is ever rejected).
function mt19937(seed) {
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
                if (y & 1)
                    v ^= 0x9908b0df;
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
function bipolar(seed, dim) {
    const next = mt19937(seed);
    const out = new Int8Array(dim);
    let buf = 0;
    let left = 0;
    for (let i = 0; i < dim; i++) {
        if (left === 0) {
            buf = next();
            left = 3;
        }
        else {
            buf >>>= 8;
            left--;
        }
        out[i] = (buf & 1) * 2 - 1;
    }
    return out;
}
function seedOf(digest) {
    return digest.readUInt32LE(0);
}
function bytesOf(g) {
    return Buffer.from(g.buffer, g.byteOffset, g.byteLength);
}
function glyphHash(g) {
    return createHash("sha256").update(bytesOf(g)).digest("hex");
}
// ── primitives ──────────────────────────────────────────────────────
const symbols = new Map();
/** Deterministic bipolar (+1/-1) symbol for a key. Same (key, seed, dim)
 *  gives the identical vector on any machine, in either language. */
export function symbol(key, seed = 42, dim = DIM) {
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
export function bind(a, b) {
    const out = new Int8Array(a.length);
    for (let i = 0; i < a.length; i++)
        out[i] = a[i] * b[i];
    return out;
}
/** Tie-break for a majority vote: a pseudo-random glyph seeded by the
 *  hash of the parts as a SET (their bytes, sorted). See the Python
 *  kernel for why: order-free, uncorrelated with any single part. */
function tiebreak(parts) {
    const h = createHash("sha256");
    for (const b of parts.map(bytesOf).sort(Buffer.compare))
        h.update(b);
    return bipolar(seedOf(h.digest()), parts[0].length);
}
/** Superpose glyphs (majority vote). Resembles all inputs; order-free. */
export function bundle(parts) {
    if (parts.length === 0)
        throw new Error("cannot bundle nothing");
    const dim = parts[0].length;
    const total = new Int32Array(dim);
    for (const p of parts)
        for (let i = 0; i < dim; i++)
            total[i] += p[i];
    const out = new Int8Array(dim);
    let tie = null;
    for (let i = 0; i < dim; i++) {
        const t = total[i];
        if (t > 0)
            out[i] = 1;
        else if (t < 0)
            out[i] = -1;
        else
            out[i] = (tie ??= tiebreak(parts))[i];
    }
    return out;
}
/** Rotate a glyph (np.roll): order, position, depth. roll(v, -k) undoes. */
export function roll(v, k = 1) {
    const n = v.length;
    const s = ((k % n) + n) % n;
    const out = new Int8Array(n);
    for (let i = 0; i < n; i++)
        out[(i + s) % n] = v[i];
    return out;
}
/** Cosine similarity for bipolar glyphs, in [-1, 1]. */
export function sim(a, b) {
    let dot = 0;
    for (let i = 0; i < a.length; i++)
        dot += a[i] * b[i];
    return dot / a.length;
}
// ── Strand: ordered meaning ─────────────────────────────────────────
/** A sequence of glyphs whose ORDER is part of the meaning. */
export class Strand {
    codons;
    constructor(codons = []) {
        this.codons = [...codons];
    }
    append(codon) {
        this.codons.push(codon);
        return this;
    }
    state(decay = 0.7) {
        if (this.codons.length === 0)
            throw new Error("empty strand has no state");
        const dim = this.codons[0].length;
        const acc = new Float64Array(dim);
        const rolled = [];
        const reversed = [...this.codons].reverse();
        reversed.forEach((codon, age) => {
            const shifted = roll(codon, age);
            rolled.push(shifted);
            const w = decay ** age;
            for (let i = 0; i < dim; i++)
                acc[i] += w * shifted[i];
        });
        const out = new Int8Array(dim);
        let tie = null;
        for (let i = 0; i < dim; i++) {
            const a = acc[i];
            if (a > 0)
                out[i] = 1;
            else if (a < 0)
                out[i] = -1;
            else
                out[i] = (tie ??= tiebreak(rolled))[i];
        }
        return out;
    }
    get length() {
        return this.codons.length;
    }
}
// ── Space: graded precedent ─────────────────────────────────────────
/** What a Space says. Trust `top` only when sufficient, confident, and
 *  count is more than a couple. */
export class Answer {
    sufficient;
    confidence;
    support;
    count;
    top;
    outcomes;
    receipts;
    constructor(sufficient, confidence, support, count, top, outcomes, receipts) {
        this.sufficient = sufficient;
        this.confidence = confidence;
        this.support = support;
        this.count = count;
        this.top = top;
        this.outcomes = outcomes;
        this.receipts = receipts;
    }
    toJson() {
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
    outcome;
    count;
    support;
    nearest;
    latest;
    authors;
    constructor(outcome, count, support, nearest, latest, authors) {
        this.outcome = outcome;
        this.count = count;
        this.support = support;
        this.nearest = nearest;
        this.latest = latest;
        this.authors = authors;
    }
    toJson() {
        return {
            outcome: this.outcome, count: this.count,
            support: pyRound(this.support, 4), nearest: pyRound(this.nearest, 4),
            latest: this.latest, authors: this.authors,
        };
    }
}
/** Precedent memory: record graded experience, answer by similarity.
 *  Encode only decision-relevant attributes; see SPEC. */
export class Space {
    dim;
    k;
    minSim;
    seed;
    decay;
    author;
    ids = [];
    outcomesOf = [];
    authors = [];
    tsOf = [];
    glyphs = [];
    db = null;
    constructor(opts = {}) {
        this.dim = opts.dim ?? DIM;
        this.k = opts.k ?? 15;
        this.minSim = opts.minSim ?? 0.1;
        this.seed = opts.seed ?? 42;
        this.decay = opts.decay ?? 0.7;
        this.author = opts.author ?? "anon";
        if (opts.path)
            this.open(opts.path);
    }
    get size() {
        return this.ids.length;
    }
    /** A situation is a dict of attributes; optional events fold in as a
     *  strand so order-carrying situations keep their order. */
    encode(situation, events) {
        const parts = Object.entries(situation)
            .sort(([a], [b]) => cmpCodePoints(a, b))
            .map(([a, v]) => bind(symbol(`attr:${a}`, this.seed, this.dim), symbol(`val:${v}`, this.seed, this.dim)));
        if (events && events.length) {
            parts.push(bind(symbol("trajectory", this.seed, this.dim), new Strand(events).state(this.decay)));
        }
        if (parts.length === 0)
            throw new Error("cannot encode an empty situation");
        return bundle(parts);
    }
    push(rid, outcome, glyph, author, ts) {
        this.ids.push(rid);
        this.outcomesOf.push(outcome);
        this.authors.push(author);
        this.tsOf.push(Number(ts));
        this.glyphs.push(glyph);
    }
    record(situation, outcome, opts = {}) {
        const rid = opts.rid ?? randomUUID().slice(0, 12);
        const ts = opts.ts ?? Date.now() / 1000;
        const glyph = this.encode(situation, opts.events);
        this.push(rid, outcome, glyph, this.author, ts);
        if (this.db) {
            this.db.prepare("INSERT OR REPLACE INTO precedents (id, situation, outcome, dim, glyph, author, ts, events)" +
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)").run(rid, pyDumps(situation, { ensureAscii: false }), outcome, this.dim, bytesOf(glyph), this.author, ts, eventsBlob(opts.events));
        }
        return rid;
    }
    sims(situation, events) {
        const q = this.encode(situation, events);
        const out = new Float64Array(this.glyphs.length);
        for (let r = 0; r < this.glyphs.length; r++)
            out[r] = sim(this.glyphs[r], q);
        return out;
    }
    topIndices(sims) {
        // np.argsort(sims)[::-1]: highest first; equal sims, later row first
        const idx = Array.from(sims.keys());
        idx.sort((a, b) => sims[b] - sims[a] || b - a);
        return idx.slice(0, this.k);
    }
    query(situation, events) {
        if (this.size === 0)
            return new Answer(false, 0, 0, 0, null, {}, []);
        const sims = this.sims(situation, events);
        const top = this.topIndices(sims);
        const receipts = top.map((i) => [
            this.ids[i], sims[i], this.outcomesOf[i], glyphHash(this.glyphs[i]).slice(0, 16), this.authors[i],
        ]);
        const voters = top.filter((i) => sims[i] >= this.minSim);
        if (voters.length === 0)
            return new Answer(false, 0, Math.max(sims[top[0]], 0), 0, null, {}, receipts);
        let wsum = 0;
        for (const i of voters)
            wsum += sims[i];
        wsum = wsum || 1;
        const outcomes = {};
        for (const i of voters)
            outcomes[this.outcomesOf[i]] = (outcomes[this.outcomesOf[i]] ?? 0) + sims[i];
        for (const o of Object.keys(outcomes))
            outcomes[o] /= wsum;
        let topOutcome = Object.keys(outcomes)[0];
        for (const o of Object.keys(outcomes))
            if (outcomes[o] > outcomes[topOutcome])
                topOutcome = o;
        let mean = 0;
        for (const i of voters)
            mean += sims[i];
        mean /= voters.length;
        return new Answer(true, outcomes[topOutcome], mean, voters.length, topOutcome, outcomes, receipts);
    }
    evidenceFrom(sims, outcome, bar) {
        const idx = [];
        for (let i = 0; i < this.size; i++)
            if (this.outcomesOf[i] === outcome && sims[i] >= bar)
                idx.push(i);
        if (idx.length === 0)
            return new Evidence(outcome, 0, 0, 0, 0, []);
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
    evidence(situation, outcome, opts = {}) {
        if (this.size === 0)
            return new Evidence(outcome, 0, 0, 0, 0, []);
        return this.evidenceFrom(this.sims(situation, opts.events), outcome, opts.minSim ?? this.minSim);
    }
    /** Every outcome with qualifying precedent, strongest first (SPEC rule 4). */
    answers(situation, opts = {}) {
        if (this.size === 0)
            return [];
        const sims = this.sims(situation, opts.events);
        const found = new Set();
        for (let i = 0; i < this.size; i++)
            if (sims[i] >= this.minSim)
                found.add(this.outcomesOf[i]);
        return [...found]
            .map((o) => this.evidenceFrom(sims, o, this.minSim))
            .filter((e) => e.count >= (opts.minCount ?? 1))
            .sort((a, b) => b.count - a.count || b.support - a.support || cmpCodePoints(a.outcome, b.outcome));
    }
    /** Max similarity among precedents with THIS outcome: the veto primitive. */
    matches(situation, outcome, events) {
        if (!this.outcomesOf.includes(outcome))
            return 0;
        const sims = this.sims(situation, events);
        let best = -Infinity;
        for (let i = 0; i < this.size; i++)
            if (this.outcomesOf[i] === outcome)
                best = Math.max(best, sims[i]);
        return best;
    }
    // persistence: one portable file; WAL so several agents can share it
    open(path) {
        const p = expand(path);
        mkdirSync(dirname(p), { recursive: true });
        this.db = new DatabaseSync(p);
        this.db.exec("PRAGMA journal_mode=WAL");
        this.db.exec("PRAGMA busy_timeout=10000");
        ensureSchema(this.db);
        if (fileEncoding(this.db) < ENCODING)
            reencodeRows(this.db, this);
        this.refresh();
    }
    /** Pull in rows other agents wrote to this file since open. */
    refresh() {
        if (!this.db)
            return 0;
        const known = new Set(this.ids);
        let added = 0;
        for (const r of this.db.prepare("SELECT id, outcome, dim, glyph, author, ts FROM precedents ORDER BY ts, rowid").all()) {
            const rid = r.id;
            if (known.has(rid))
                continue;
            if (Number(r.dim) !== this.dim)
                throw new Error(`precedent ${rid} has dim ${r.dim}, space is ${this.dim}`);
            this.push(rid, r.outcome, toGlyph(r.glyph), r.author, Number(r.ts));
            added++;
        }
        return added;
    }
    /** Union another Space file into this one (by precedent id). Rows from
     *  an older encoding are re-encoded on the way in. */
    merge(otherPath) {
        const other = new DatabaseSync(expand(otherPath));
        try {
            const cols = new Set(other.prepare("PRAGMA table_info(precedents)").all().map((c) => c.name));
            const stale = fileEncoding(other) < ENCODING;
            const sql = "SELECT id, situation, outcome, dim, glyph, " +
                `${cols.has("author") ? "author" : "'anon'"} AS author, ` +
                `${cols.has("ts") ? "ts" : "0.0"} AS ts, ` +
                `${cols.has("events") ? "events" : "NULL"} AS events FROM precedents`;
            const known = new Set(this.ids);
            let added = 0;
            if (this.db)
                this.db.exec("BEGIN");
            for (const r of other.prepare(sql).all()) {
                const rid = r.id;
                if (known.has(rid))
                    continue;
                const dim = Number(r.dim);
                if (dim !== this.dim)
                    throw new Error(`precedent ${rid} has dim ${dim}, space is ${this.dim}`);
                const glyph = stale
                    ? this.encode(JSON.parse(r.situation), eventsFromBlob(r.events, dim))
                    : toGlyph(r.glyph);
                this.push(rid, r.outcome, glyph, r.author, Number(r.ts));
                this.db?.prepare("INSERT OR REPLACE INTO precedents (id, situation, outcome, dim, glyph, author, ts, events)" +
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?)").run(rid, r.situation, r.outcome, dim, bytesOf(glyph), r.author, Number(r.ts), r.events ?? null);
                added++;
            }
            if (this.db)
                this.db.exec("COMMIT");
            return added;
        }
        finally {
            other.close();
        }
    }
    close() {
        this.db?.close();
        this.db = null;
    }
}
// ── the contract as a function ──────────────────────────────────────
/** What decide() concluded. Act on `outcome` only when `act`. */
export class Decision {
    act;
    outcome;
    reason;
    answer;
    veto;
    lifted;
    constructor(act, outcome, reason, answer, veto, lifted) {
        this.act = act;
        this.outcome = outcome;
        this.reason = reason;
        this.answer = answer;
        this.veto = veto;
        this.lifted = lifted;
    }
    toJson() {
        return {
            act: this.act, outcome: this.outcome, reason: this.reason, lifted: this.lifted,
            veto: this.veto ? this.veto.toJson() : null, answer: this.answer.toJson(),
        };
    }
}
/** THE CONTRACT (see SPEC): three trust gates on the wins, then the veto
 *  check, with the newest evidence winning. */
export function decide(wins, vetoes, situation, opts = {}) {
    const minConfidence = opts.minConfidence ?? 0.5;
    const minCount = opts.minCount ?? 3;
    const minVetoCount = opts.minVetoCount ?? 1;
    const answer = wins.query(situation, opts.events);
    if (!answer.sufficient)
        return new Decision(false, null, "insufficient", answer, null, false);
    const top = answer.top;
    const veto = vetoes.evidence(situation, top, { events: opts.events, minSim: Math.max(answer.support, 1e-9) });
    const win = wins.evidence(situation, top, { events: opts.events });
    const close = veto.count >= minVetoCount;
    const lifted = close && win.latest > veto.latest;
    if (close && !lifted)
        return new Decision(false, top, "vetoed", answer, veto, false);
    const shown = veto.count ? veto : null;
    if (answer.count < minCount)
        return new Decision(false, top, "uncalibrated", answer, shown, lifted);
    if (answer.confidence < minConfidence)
        return new Decision(false, top, "low_confidence", answer, shown, lifted);
    return new Decision(true, top, "reflex", answer, shown, lifted);
}
/** Re-encode every precedent's glyph from its stored situation and events
 *  under the current encoding, and stamp the file. Returns rows re-encoded. */
export function reencodeStore(path, opts = {}) {
    const db = new DatabaseSync(expand(path));
    try {
        ensureSchema(db);
        return reencodeRows(db, new Space({ ...opts, path: undefined }));
    }
    finally {
        db.close();
    }
}
// ── store schema and migration ──────────────────────────────────────
function expand(path) {
    return resolve(path.startsWith("~") ? homedir() + path.slice(1) : path);
}
function toGlyph(blob) {
    return new Int8Array(blob.buffer, blob.byteOffset, blob.byteLength).slice();
}
function eventsBlob(events) {
    if (!events || events.length === 0)
        return null;
    const out = new Int8Array(events.length * events[0].length);
    events.forEach((e, i) => out.set(e, i * e.length));
    return bytesOf(out);
}
function eventsFromBlob(blob, dim) {
    if (!blob || blob.byteLength === 0)
        return null;
    const flat = toGlyph(blob);
    const out = [];
    for (let i = 0; i < flat.length; i += dim)
        out.push(flat.slice(i, i + dim));
    return out;
}
function ensureSchema(db) {
    db.exec("CREATE TABLE IF NOT EXISTS precedents (" +
        " id TEXT PRIMARY KEY, situation TEXT NOT NULL," +
        " outcome TEXT NOT NULL, dim INTEGER NOT NULL," +
        " glyph BLOB NOT NULL, author TEXT NOT NULL DEFAULT 'anon'," +
        " ts REAL NOT NULL DEFAULT 0, events BLOB)");
    db.exec("CREATE TABLE IF NOT EXISTS meta ( key TEXT PRIMARY KEY, value TEXT NOT NULL)");
    const cols = new Set(db.prepare("PRAGMA table_info(precedents)").all().map((c) => c.name));
    if (!cols.has("author"))
        db.exec("ALTER TABLE precedents ADD COLUMN author TEXT NOT NULL DEFAULT 'anon'");
    if (!cols.has("ts"))
        db.exec("ALTER TABLE precedents ADD COLUMN ts REAL NOT NULL DEFAULT 0");
    if (!cols.has("events"))
        db.exec("ALTER TABLE precedents ADD COLUMN events BLOB");
    const rows = Number(db.prepare("SELECT COUNT(*) AS n FROM precedents").get().n);
    const stamped = db.prepare("SELECT value FROM meta WHERE key = 'encoding'").get();
    if (!stamped)
        db.prepare("INSERT INTO meta VALUES ('encoding', ?)").run(String(rows === 0 ? ENCODING : 1));
}
function fileEncoding(db) {
    try {
        const row = db.prepare("SELECT value FROM meta WHERE key = 'encoding'").get();
        if (row)
            return Number(row.value);
    }
    catch { /* no meta table: an old file */ }
    try {
        const n = Number(db.prepare("SELECT COUNT(*) AS n FROM precedents").get().n);
        return n === 0 ? ENCODING : 1;
    }
    catch {
        return ENCODING;
    }
}
function reencodeRows(db, space) {
    const rows = db.prepare("SELECT id, situation, dim, events FROM precedents").all();
    let done = 0;
    db.exec("BEGIN");
    try {
        const update = db.prepare("UPDATE precedents SET glyph = ?, dim = ? WHERE id = ?");
        for (const r of rows) {
            let glyph;
            try {
                glyph = space.encode(JSON.parse(r.situation), eventsFromBlob(r.events, space.dim));
            }
            catch {
                continue; // no usable situation stored: keep the old glyph
            }
            update.run(bytesOf(glyph), space.dim, r.id);
            done++;
        }
        db.prepare("INSERT OR REPLACE INTO meta VALUES ('encoding', ?)").run(String(ENCODING));
        db.exec("COMMIT");
    }
    catch (e) {
        db.exec("ROLLBACK");
        throw e;
    }
    return done;
}
