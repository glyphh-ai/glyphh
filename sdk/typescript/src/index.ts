/**
 * @glyphh-ai/glyphh — Ada Cloud, for one API key. Every call is one request to Ada's API at https://ada.glyphh.ai
 * (a job-backed call: one request, then its job's progress), with the key as the bearer.
 *
 *     const ada = new Ada();                                 // GLYPHH_API_KEY from the environment
 *     const d = await ada.decide("tickets", { ticket: { ... } });
 *     if (d.ask) await sendToAPerson(d);                     // d.outcome is the best guess, for them to see
 *     else act(d.outcome);
 */

/** Where Ada answers. GLYPHH_ADA_URL (or 3.0's GLYPHH_RUNTIME_URL) moves it, e.g. to a local server under test. */
export const DEFAULT_URL = "https://ada.glyphh.ai";
/** How long, in seconds, a call keeps retrying what is safe to send again before it throws. */
export const RETRY_DEADLINE = 30;
/** How long, in seconds, waiting for a job lasts before it throws (the job goes on; wait for it again by its id). */
export const JOB_TIMEOUT = 3600;
/** The longest pause, in seconds, between two looks at a job. */
export const POLL = 2;
/** Cases one record_many request carries; recordMany sends more in chunks of this many. */
export const RECORD_MANY_MAX = 1000;
/** An Ada model's functions that only read: safe to send again when Ada could not be reached. */
export const READS: readonly string[] = ["query", "facts", "probabilities", "decide"];
/** An import's format by its file's extension. */
export const FORMATS: Record<string, string> = {
  ".jsonl": "jsonl",
  ".ndjson": "jsonl",
  ".csv": "csv",
  ".sqlite": "ada_sqlite",
  ".db": "ada_sqlite",
  ".zip": "jsonl",
};
const CLUSTER_SEQ = "rrotor-cluster-seq";
const MIN_SEQ = "rrotor-min-seq";

export type Status = "done" | "needs_input" | "needs_approval" | "failed" | "expired" | "cancelled";
export type Data = Record<string, unknown>;

/** What a run answered (`POST /v1/runs`, SDK 3.0's call shape). Ada Cloud answers every run at once, `done`. */
export interface Result<T = unknown> {
  run_id: string;
  model: string;
  version: number;
  function: string;
  status: Status;
  data: T;
  step: string | null;
  prompt: string | null;
  seconds: number;
  /** A self-hosted runtime's: done but indexed nothing. The cloud refuses with `LimitError` instead. */
  limit_exceeded: boolean;
}

export interface Receipt {
  id: string;
  sim: number;
  outcome: string | null;
  hash: string;
  author: string | null;
}

/** What an Ada model's `query` answers. Trust `top` when `sufficient` and `confidence` clears your bar. */
export interface Answer {
  sufficient: boolean;
  confidence: number;
  support: number;
  count: number;
  top: string | null;
  outcomes: Record<string, number>;
  receipts: Receipt[];
}

/** One output's decision. */
export interface Decided {
  /** The outcome of least expected cost; when `ask`, the best guess, for the person to see. */
  outcome: string | null;
  expected_cost: number | null;
  probabilities: Record<string, number>;
  /** A person should decide instead: nothing is known, asking is cheaper, or the top probability is under the spec's bar. */
  ask: boolean;
  receipts: Receipt[];
  /** The nearest fact tree, when asked for (`include: ["facts"]`). */
  facts?: unknown[];
}

/**
 * `POST /v1/decide`: one call, one typed answer, from the model's active version. `outputs` when several outputs
 * were decided at once. It reads as a 3.0 `Result` too: `status` "done" and `data` (the answer as sent).
 */
export interface Decision extends Decided {
  model: string;
  version: number;
  outputs?: Record<string, Decided>;
  status: "done";
  data: Data;
}

export interface Link {
  url: string;
  expires_at: number;
}

export type JobState = "awaiting" | "queued" | "running" | "done" | "failed";

/** Work too long for a request (learn, calibrate, import, export, backtest, re-encode), as the server answers it. */
export interface Job<R = any> {
  id: string;
  model: string;
  kind: "learn" | "calibrate" | "import" | "export" | "reencode" | "backtest";
  state: JobState;
  percent: number;
  args: Data;
  result: R;
  error: { code: string; message: string; [k: string]: unknown } | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  made_by: string | null;
  /** A done export's one-hour download link. */
  download?: Link;
  /** An import's one-hour upload link, while it waits for its file. */
  upload?: Link;
}

/** A new version from a spec or settings change, or another made active: `job` when it re-encodes. */
export interface Change {
  version: number;
  active: boolean;
  job: Job | null;
}

/**
 * `GET /v1/usage`: what the org uses of Ada Cloud against its plan, in the calendar `month` counted (YYYY-MM, UTC),
 * which starts again on `resets_at` (YYYY-MM-DD): its live `models`, the `precedents` they hold, its `requests`, and
 * the calls a second the plan allows. A null `max` (or `requests_per_second`) is by contract: no cap.
 */
export interface Usage {
  plan: string;
  month: string;
  resets_at: string;
  models: number;
  precedents: { used: number; max: number | null };
  /**
   * Reads this month (decide, query, probabilities, facts; a decide of several outputs once per output). `overage`:
   * past the month they go on, metered (Basic, Pro, Team), `over` of them so far; else (Free) they are refused, LimitError
   * `requests`, until `resets_at`.
   */
  requests: { used: number; max: number | null; over: number; overage: boolean };
  requests_per_second: number | null;
}

export interface ModelInfo {
  name: string;
  [key: string]: unknown;
}

/**
 * Sends one request; give your own to use another HTTP client. Answer the headers for Retry-After; `raw`, the body's
 * bytes, for a download (else `body` is encoded).
 */
export type Transport = (
  method: string,
  url: string,
  headers: Record<string, string>,
  body?: string | Uint8Array,
) => Promise<{ status: number; body: string; headers?: Record<string, string>; raw?: Uint8Array }>;

export type Progress = (job: Job) => void;

export interface AdaOptions {
  /** Ada's address; else GLYPHH_ADA_URL, GLYPHH_RUNTIME_URL, or https://ada.glyphh.ai. */
  url?: string;
  /** An API key; else GLYPHH_API_KEY (or 3.0's GLYPHH_RUNTIME_KEY). */
  key?: string;
  transport?: Transport;
  /** Seconds a call keeps retrying what is safe to send again; 0: never. Default 30. */
  retryDeadline?: number;
  /** A self-hosted cluster's read-your-writes (Rrotor-Min-Seq); nothing to the cloud. Default true. */
  readYourWrites?: boolean;
  /** @internal The tests' clock: seconds now, and a wait of so many seconds. */
  clock?: { now(): number; sleep(seconds: number): Promise<void> };
}

export interface WaitOptions {
  /** Wait for the job to end (default); false answers it as it stands. */
  wait?: boolean;
  /** Seconds; default an hour. */
  timeout?: number;
  /** Gets the job each time it is looked at. */
  onProgress?: Progress;
}

// Refusals

/** Ada refused, or could not be reached: `code` is the server's (E_AUTH, E_LIMIT, ...), or E_UNREACHABLE / E_CONFIG. */
export class AdaError extends Error {
  constructor(
    readonly code: string,
    message: string,
    readonly status = 0,
    /** The rest of the refusal: reason, used, max, limit, path, job, trace_id, ... */
    readonly detail: Record<string, unknown> = {},
    /** Seconds, when the server said when to ask again (Retry-After). */
    readonly retryAfter?: number,
  ) {
    super(message);
    this.name = "AdaError";
  }

  /** Quote it to support. */
  get traceId(): string | undefined {
    return this.detail.trace_id as string | undefined;
  }
}

/** E_AUTH (401): no key, or not a live API key. */
export class AuthError extends AdaError {
  override name = "AuthError";
}
const str = (value: unknown) => (typeof value === "string" ? value : undefined);
const num = (value: unknown) => (typeof value === "number" ? value : undefined);

/**
 * E_LIMIT (403): the plan's limit is reached. `reason` names it: `requests` (the month's reads are used on a plan that
 * is not metered, Free: `plan`, the plan to `upgrade` to, null when only a contract reads more, and `resetsAt`,
 * YYYY-MM-DD, when they start again), `precedents` (a write past the plan's precedents: `detail.adding`), or `cases`
 * (413, recordMany past 1,000). `used` and `max` say where the org stands.
 */
export class LimitError extends AdaError {
  override name = "LimitError";
  get reason(): string | undefined {
    return str(this.detail.reason);
  }
  get used(): number | undefined {
    return num(this.detail.used);
  }
  get max(): number | undefined {
    return num(this.detail.max);
  }
  get plan(): string | undefined {
    return str(this.detail.plan);
  }
  /** The self-serve plan that reads more (Billing on the platform, or the connector's upgrade tool); null: talk to sales. */
  get upgrade(): string | null | undefined {
    return this.detail.upgrade === null ? null : str(this.detail.upgrade);
  }
  /** When the month's requests start again, YYYY-MM-DD (UTC). */
  get resetsAt(): string | undefined {
    return str(this.detail.resets_at);
  }
}
/**
 * E_RATE (429): more calls a second than the plan allows (Free 5, Pro 50, Team 200), the org's together. The client
 * waits `retryAfter` seconds (the Retry-After header, else the body's `retry_after`) and asks again while its deadline
 * allows; thrown after that. `max` is the plan's calls a second.
 */
export class RateError extends AdaError {
  override name = "RateError";
  get max(): number | undefined {
    return num(this.detail.max);
  }
}
/** E_INVALID: the request is not valid (`detail.problems`), or a string holds NUL. */
export class InvalidError extends AdaError {
  override name = "InvalidError";
}
/** E_TOO_LARGE (413): a body over its bound. */
export class TooLargeError extends AdaError {
  override name = "TooLargeError";
}
/** E_MODEL_MISSING (404). */
export class ModelMissingError extends AdaError {
  override name = "ModelMissingError";
}
/** E_JOB_MISSING (404). */
export class JobMissingError extends AdaError {
  override name = "JobMissingError";
}
/** E_PRECEDENT_MISSING (404). */
export class PrecedentMissingError extends AdaError {
  override name = "PrecedentMissingError";
}
/** E_VERSION_MISSING (404). */
export class VersionMissingError extends AdaError {
  override name = "VersionMissingError";
}
/** E_SPEC (422): the kernel refused the spec, or data that does not fit it; `detail.path` says where. */
export class SpecError extends AdaError {
  override name = "SpecError";
}
/** E_SPEC_LIMIT: past a cloud bound on a spec (`detail.limit`, `detail.max`). */
export class SpecLimitError extends SpecError {
  override name = "SpecLimitError";
}
/** E_SPEC_READING (422): the new spec reads a role's values differently; make a new model and import into it. */
export class SpecReadingError extends SpecError {
  override name = "SpecReadingError";
}
/** E_FEW_ROLES (422): a model over 100,000 precedents asked with under half its voting roles. */
export class FewRolesError extends AdaError {
  override name = "FewRolesError";
}
/** E_MAPPING (422): an import's CSV header the spec cannot take. */
export class MappingError extends AdaError {
  override name = "MappingError";
}
/** E_IMPORT (422): the import's file is not what its format says. */
export class ImportRefusedError extends AdaError {
  override name = "ImportRefusedError";
}
/** E_BACKTEST (422): nothing to hold out. */
export class BacktestError extends AdaError {
  override name = "BacktestError";
}
/** E_BUSY (409): an import or re-encode is open on the model (`detail.job`). */
export class BusyError extends AdaError {
  override name = "BusyError";
}
/** E_NOT_READY (409): that version is still being made. */
export class NotReadyError extends AdaError {
  override name = "NotReadyError";
}
/** E_NO_CHANGE (409): the spec or settings are the active version's already. */
export class NoChangeError extends AdaError {
  override name = "NoChangeError";
}
/** E_IDEMPOTENCY (409): this Idempotency-Key was sent before with another body. */
export class IdempotencyError extends AdaError {
  override name = "IdempotencyError";
}
/** E_CONFLICT (409). */
export class ConflictError extends AdaError {
  override name = "ConflictError";
}
/** E_VERSION_GONE (410): the version's store was dropped. */
export class VersionGoneError extends AdaError {
  override name = "VersionGoneError";
}
/** E_EXPIRED: an import whose file never came while its upload link worked. */
export class ExpiredError extends AdaError {
  override name = "ExpiredError";
}
/** E_TIMEOUT (504), or a wait for a job past its timeout (the job goes on). */
export class AdaTimeoutError extends AdaError {
  override name = "AdaTimeoutError";
}
/** E_UNAVAILABLE (503): Ada is unreachable for a moment; retried while the deadline allows. */
export class UnavailableError extends AdaError {
  override name = "UnavailableError";
}
/** A job ended `failed`: `code` and `message` are its error's; `detail.job` is the job. */
export class JobFailedError extends AdaError {
  override name = "JobFailedError";
}
/** E_NO_HEAD (503): a self-hosted cluster has no head. */
export class NoHeadError extends AdaError {
  override name = "NoHeadError";
}
/** E_HEAD_LOST (503): a self-hosted cluster's head went while it had the write. Never resent. */
export class HeadLostError extends AdaError {
  override name = "HeadLostError";
}
/** E_NOT_COMMITTED (503): a self-hosted cluster kept the write; most voters do not hold it yet. */
export class NotCommittedError extends AdaError {
  override name = "NotCommittedError";
}
/** E_RUN_LOST (410): a self-hosted cluster's node that held the run left. */
export class RunLostError extends AdaError {
  override name = "RunLostError";
}
/** E_READ_ONLY: on a self-hosted cluster's follower, a function marked `"writes": false` wrote. */
export class ReadOnlyError extends AdaError {
  override name = "ReadOnlyError";
}

export const TYPED: Record<string, typeof AdaError> = {
  E_AUTH: AuthError,
  E_UNAUTHORIZED: AuthError,
  E_LIMIT: LimitError,
  E_RATE: RateError,
  E_INVALID: InvalidError,
  E_TOO_LARGE: TooLargeError,
  E_MODEL_MISSING: ModelMissingError,
  E_JOB_MISSING: JobMissingError,
  E_PRECEDENT_MISSING: PrecedentMissingError,
  E_VERSION_MISSING: VersionMissingError,
  E_SPEC: SpecError,
  E_SPEC_LIMIT: SpecLimitError,
  E_SPEC_READING: SpecReadingError,
  E_FEW_ROLES: FewRolesError,
  E_MAPPING: MappingError,
  E_IMPORT: ImportRefusedError,
  E_BACKTEST: BacktestError,
  E_BUSY: BusyError,
  E_NOT_READY: NotReadyError,
  E_NO_CHANGE: NoChangeError,
  E_IDEMPOTENCY: IdempotencyError,
  E_CONFLICT: ConflictError,
  E_VERSION_GONE: VersionGoneError,
  E_EXPIRED: ExpiredError,
  E_TIMEOUT: AdaTimeoutError,
  E_UNAVAILABLE: UnavailableError,
  E_NO_HEAD: NoHeadError,
  E_HEAD_LOST: HeadLostError,
  E_NOT_COMMITTED: NotCommittedError,
  E_RUN_LOST: RunLostError,
  E_READ_ONLY: ReadOnlyError,
};

const BY_STATUS: Record<number, string> = { 401: "E_AUTH", 402: "E_LIMIT", 404: "E_NOT_FOUND", 429: "E_RATE" };
const TRANSIENT = ["E_UNREACHABLE", "E_UNAVAILABLE", "E_TIMEOUT"];

/** Retry-After as seconds: a number of them, or an HTTP date. */
export function retryAfter(value: string | undefined): number | undefined {
  if (!value) return undefined;
  const n = Number(value);
  if (value.trim() !== "" && Number.isFinite(n)) return Math.max(0, n);
  const at = Date.parse(value);
  return Number.isNaN(at) ? undefined : Math.max(0, (at - Date.now()) / 1000);
}

/**
 * Refused before anything ran (429, a self-hosted cluster's E_NO_HEAD): any call. Ada unreachable for a moment
 * (E_UNREACHABLE, E_UNAVAILABLE, E_TIMEOUT, a proxy's 502, 503, 504): a call safe to send again, a read or a write
 * carrying an Idempotency-Key.
 */
function retryable(err: AdaError, safe: boolean): boolean {
  if (err.code === "E_NO_HEAD" || err.status === 429) return true;
  return safe && (TRANSIENT.includes(err.code) || [502, 503, 504].includes(err.status));
}

function asResult<T>(body: Omit<Result<T>, "limit_exceeded">): Result<T> {
  const data = body.data as { status?: unknown; code?: unknown; reason?: unknown } | null;
  const isObject = typeof data === "object" && data !== null;
  if (body.status === "failed" && isObject && data.code === "E_READ_ONLY") {
    const reason = typeof data.reason === "string" ? data.reason : `${body.function} wrote, and it is marked read-only`;
    throw new ReadOnlyError("E_READ_ONLY", reason, 200, { run_id: body.run_id, function: body.function });
  }
  return { ...body, limit_exceeded: body.status === "done" && isObject && data.status === "limit_exceeded" };
}

function asDecided(body: Data): Decided {
  const out: Decided = {
    outcome: (body.outcome as string | null | undefined) ?? null,
    expected_cost: (body.expected_cost as number | null | undefined) ?? null,
    probabilities: (body.probabilities as Record<string, number> | undefined) ?? {},
    ask: Boolean(body.ask),
    receipts: (body.receipts as Receipt[] | undefined) ?? [],
  };
  if (body.facts !== undefined) out.facts = body.facts as unknown[];
  return out;
}

/** A `POST /v1/decide` answer as a Decision. */
export function asDecision(body: Data): Decision {
  const decision: Decision = {
    ...asDecided(body),
    model: String(body.model ?? ""),
    version: Number(body.version ?? 0),
    status: "done",
    data: body,
  };
  const outputs = body.outputs as Record<string, Data> | undefined;
  if (outputs !== undefined) {
    decision.outputs = Object.fromEntries(Object.entries(outputs).map(([k, v]) => [k, asDecided(v)]));
    if (!("ask" in body)) decision.ask = Object.values(decision.outputs).some((d) => d.ask);
  }
  return decision;
}

function refusal(status: number, text: string, headers: Record<string, string>): AdaError {
  let parsed: unknown = {};
  try {
    parsed = text ? JSON.parse(text) : {};
  } catch {
    parsed = {};
  }
  const err = ((parsed as { error?: Record<string, unknown> } | null)?.error ?? {}) as Record<string, unknown>;
  const { code, message, ...detail } = err;
  const named = (code as string | undefined) ?? BY_STATUS[status] ?? "E_RUNTIME";
  return new (TYPED[named] ?? AdaError)(
    named,
    (message as string | undefined) ?? `Ada answered ${status}`,
    status,
    detail,
    // the header, else a refusal's own (E_RATE's retry_after)
    retryAfter(headers["retry-after"]) ?? num(detail.retry_after),
  );
}

function parsed<T>(status: number, text: string, headers: Record<string, string>): T {
  if (status >= 400) throw refusal(status, text, headers);
  try {
    return (text ? JSON.parse(text) : {}) as T;
  } catch {
    return {} as T;
  }
}

const realClock = {
  now: () => performance.now() / 1000,
  sleep: (seconds: number) => new Promise<void>((resolve) => setTimeout(resolve, seconds * 1000)),
};

function env(name: string): string | undefined {
  const p = (globalThis as { process?: { env?: Record<string, string | undefined> } }).process;
  const value = p?.env?.[name];
  return value === "" ? undefined : value;
}

const fetchTransport: Transport = async (method, url, headers, body) => {
  const res = await fetch(url, body === undefined ? { method, headers } : { method, headers, body: body as BodyInit });
  const answered: Record<string, string> = {};
  res.headers.forEach((value, name) => (answered[name] = value));
  const raw = new Uint8Array(await res.arrayBuffer());
  return { status: res.status, body: new TextDecoder().decode(raw), headers: answered, raw };
};

function newKey(): string {
  const c = (globalThis as { crypto?: { randomUUID?: () => string } }).crypto;
  return c?.randomUUID ? c.randomUUID().replace(/-/g, "") : `${Date.now().toString(16)}${Math.random().toString(16).slice(2)}`;
}

function drop<T extends Record<string, unknown>>(values: T): Partial<T> {
  return Object.fromEntries(Object.entries(values).filter(([, v]) => v !== undefined)) as Partial<T>;
}

const q = encodeURIComponent;

/** Node's file system, loaded only when a path is given (the SDK has no dependencies and runs in browsers too). */
type Files = { readFile(path: string): Promise<Uint8Array>; writeFile(path: string, data: Uint8Array): Promise<void> };
const FS = "node:fs/promises";
const files = async (): Promise<Files> => (await import(FS)) as Files;

/**
 * Ada Cloud, for one API key. Calls safe to send again (reads, and writes, which carry an Idempotency-Key) are retried
 * while Ada is unreachable for a moment, with backoff (Retry-After honoured), for up to `retryDeadline` seconds.
 */
export class Ada {
  readonly url: string;
  readonly retryDeadline: number;
  readonly readYourWrites: boolean;
  readonly #key: string;
  readonly #send: Transport;
  readonly #clock: { now(): number; sleep(seconds: number): Promise<void> };
  #seq = 0;

  constructor(options: AdaOptions = {}) {
    this.url = (options.url ?? env("GLYPHH_ADA_URL") ?? env("GLYPHH_RUNTIME_URL") ?? DEFAULT_URL).replace(/\/+$/, "");
    this.#key = options.key ?? env("GLYPHH_API_KEY") ?? env("GLYPHH_RUNTIME_KEY") ?? "";
    if (!this.#key) {
      throw new AdaError(
        "E_CONFIG",
        "An API key is needed: set GLYPHH_API_KEY (make one on the platform's API Keys page, or ask Claude through the Glyphh connector).",
      );
    }
    this.#send = options.transport ?? fetchTransport;
    this.retryDeadline = options.retryDeadline ?? RETRY_DEADLINE;
    this.readYourWrites = options.readYourWrites ?? true;
    this.#clock = options.clock ?? realClock;
  }

  /** A self-hosted cluster's highest `Rrotor-Cluster-Seq` answered (0: none; always 0 against the cloud). */
  get clusterSeq(): number {
    return this.#seq;
  }

  /**
   * One request, sent again while it may be and the deadline allows. `read`: safe to send again (a GET by default);
   * a write with an `idempotencyKey` is safe too.
   */
  async call<T = unknown>(method: string, path: string, body?: unknown, read = method === "GET", idempotencyKey?: string): Promise<T> {
    const raw = body === undefined ? undefined : JSON.stringify(body);
    const safe = read || idempotencyKey !== undefined;
    const deadline = this.#clock.now() + this.retryDeadline;
    for (let attempt = 0; ; attempt++) {
      try {
        return await this.#once<T>(method, path, raw, idempotencyKey);
      } catch (e) {
        if (!(e instanceof AdaError) || !retryable(e, safe)) throw e;
        // Retry-After, else 0.25 s doubling to 2 s, jittered by up to half
        const wait = e.retryAfter ?? Math.min(2, 0.25 * 2 ** attempt) * (0.5 + Math.random() / 2);
        if (this.#clock.now() + wait > deadline) throw e;
        await this.#clock.sleep(wait);
      }
    }
  }

  /** A write to the cloud: it carries an Idempotency-Key (the caller's, or a new one), so it is made once. */
  write<T = unknown>(method: string, path: string, body?: unknown, idempotencyKey?: string): Promise<T> {
    return this.call<T>(method, path, body, false, idempotencyKey ?? newKey());
  }

  /** @internal One exchange with any URL (an upload or download link carries its own credential). */
  async exchange(
    method: string,
    url: string,
    headers: Record<string, string>,
    body?: string | Uint8Array,
  ): Promise<{ status: number; body: string; headers: Record<string, string>; raw?: Uint8Array }> {
    let answer: Awaited<ReturnType<Transport>>;
    try {
      answer = await this.#send(method, url, headers, body);
    } catch (e) {
      throw new AdaError("E_UNREACHABLE", `Ada could not be reached: ${(e as Error).message}`);
    }
    const got: Record<string, string> = {};
    for (const [k, v] of Object.entries(answer.headers ?? {})) got[k.toLowerCase()] = String(v);
    const out: { status: number; body: string; headers: Record<string, string>; raw?: Uint8Array } = {
      status: answer.status,
      body: answer.body,
      headers: got,
    };
    if (answer.raw !== undefined) out.raw = answer.raw;
    return out;
  }

  async #once<T>(method: string, path: string, raw: string | undefined, idempotencyKey: string | undefined): Promise<T> {
    const headers: Record<string, string> = { authorization: `Bearer ${this.#key}`, accept: "application/json" };
    if (raw !== undefined) headers["content-type"] = "application/json";
    if (idempotencyKey !== undefined) headers["idempotency-key"] = idempotencyKey;
    if (this.readYourWrites && this.#seq) headers[MIN_SEQ] = String(this.#seq);
    const answer = await this.exchange(method, `${this.url}${path}`, headers, raw);
    const seq = Number(answer.headers[CLUSTER_SEQ]);
    if (Number.isInteger(seq) && seq > this.#seq) this.#seq = seq;
    return parsed<T>(answer.status, answer.body, answer.headers);
  }

  // models

  /** The org's models: each one's name, active version and how many precedents it holds. */
  async models(): Promise<ModelInfo[]> {
    return (await this.call<{ models: ModelInfo[] }>("GET", "/v1/models")).models;
  }

  model(name: string): AdaModel {
    return new AdaModel(this, name);
  }

  /** A model from its JSON spec, checked by the kernel and the cloud's bounds: version 1, empty. `created` is the answer. */
  async createModel(name: string, spec: Data, options: { idempotencyKey?: string } = {}): Promise<AdaModel> {
    const made = await this.write<Data>("POST", "/v1/models", { name, spec }, options.idempotencyKey);
    return new AdaModel(this, name, made);
  }

  /** Delete a model and every precedent it holds. Not undone. */
  deleteModel(name: string): Promise<{ name: string; deleted: boolean }> {
    return this.write("DELETE", `/v1/models/${q(name)}?confirm=${q(name)}`);
  }

  // asking

  /**
   * The headline, `POST /v1/decide`: one call, one typed answer. `outputs` decides several of the model's named
   * outputs at once; `include: ["facts"]` adds the nearest fact tree; `clearance` reads with less than the key's.
   */
  async decide(model: string, data: Data, options: DecideOptions = {}): Promise<Decision> {
    const body = drop({ model, data, output: options.output, outputs: options.outputs, include: options.include, clearance: options.clearance });
    return asDecision(await this.call<Data>("POST", "/v1/decide", body, true));
  }

  // jobs

  /** A job's state and progress. */
  job<R = any>(id: string): Promise<Job<R>> {
    return this.call("GET", `/v1/jobs/${q(id)}`);
  }

  /** Wait for a job to end: the done job, or `JobFailedError` with the job's own error. */
  async wait<R = any>(job: Job<R> | string, options: { timeout?: number; poll?: number; onProgress?: Progress } = {}): Promise<Job<R>> {
    let current = typeof job === "string" ? await this.job<R>(job) : job;
    const timeout = options.timeout ?? JOB_TIMEOUT;
    const deadline = this.#clock.now() + timeout;
    let pause = 0.25;
    for (;;) {
      options.onProgress?.(current);
      if (current.state === "failed") {
        const { code, message, ...rest } = current.error ?? { code: "E_JOB_FAILED", message: "" };
        throw new JobFailedError(code || "E_JOB_FAILED", message || `The ${current.kind} job failed.`, 0, { ...rest, job: current });
      }
      if (current.state === "done") return current;
      if (this.#clock.now() + pause > deadline) {
        throw new AdaTimeoutError(
          "E_TIMEOUT",
          `The ${current.kind} job ${current.id} did not end within ${timeout} s; it goes on: wait for it again by its id.`,
          0,
          { job: current.id },
        );
      }
      await this.#clock.sleep(pause);
      pause = Math.min(options.poll ?? POLL, pause * 2);
      current = await this.job<R>(current.id);
    }
  }

  /** A done export's file, by its job or its download URL: the link is its own credential, for an hour. */
  async download(job: Job | string): Promise<Uint8Array> {
    const url = typeof job === "string" ? job : job.download?.url;
    if (!url) throw new AdaError("E_INVALID", "This job has no download link: export, and wait for it to be done.");
    const answer = await this.exchange("GET", url, { accept: "*/*" });
    if (answer.status >= 400) throw refusal(answer.status, answer.body, answer.headers);
    return answer.raw ?? new TextEncoder().encode(answer.body);
  }

  /** The org's plan, its models, and the precedents they hold against its cap. */
  usage(): Promise<Usage> {
    return this.call("GET", "/v1/usage");
  }

  // SDK 3.0's calls for a self-hosted runtime: the cloud keeps no runs and deploys no repos

  /** A self-hosted runtime's. The cloud has no deploys: a model is its spec (`createModel`, `setSpec`). */
  deploy(repo: string, commit: string, token?: string): Promise<{ model: string; version: number; commit_sha: string }> {
    return this.call("POST", "/v1/models/deploy", token === undefined ? { repo, commit } : { repo, commit, token });
  }

  /** A self-hosted runtime's run. The cloud answers every run at once and keeps none (E_RUN_MISSING). */
  run(runId: string): Promise<Record<string, unknown>> {
    return this.call("GET", `/v1/runs/${q(runId)}`);
  }

  async log(runId: string): Promise<unknown[]> {
    return (await this.call<{ lines: unknown[] }>("GET", `/v1/runs/${q(runId)}/log`)).lines;
  }

  /** A self-hosted runtime's run that waits. The cloud never waits: a decision says `ask` instead. */
  async resume<T = unknown>(runId: string, answer: unknown): Promise<Result<T>> {
    return asResult(await this.call("POST", `/v1/runs/${q(runId)}/continue`, { answer }));
  }

  async cancel<T = unknown>(runId: string): Promise<Result<T>> {
    return asResult(await this.call("POST", `/v1/runs/${q(runId)}/cancel`, {}));
  }
}

export interface CallOptions {
  version?: number;
  /** Who asks, 0 to 1: the model's secured roles are cut from the answer below their weight. */
  clearance?: number;
  /** A named output; left out, the default one. */
  output?: string;
}

export interface DecideOptions {
  output?: string;
  outputs?: string[];
  include?: "facts"[];
  clearance?: number;
}

export interface ChangeOptions extends WaitOptions {
  /** Why: kept with the version. */
  note?: string;
  /** The backtest job this change was chosen by: kept with the version. */
  backtest?: string;
  idempotencyKey?: string;
}

export interface Case {
  data: Data;
  outcome?: string;
  outcomes?: Record<string, string>;
  ts?: number;
}

export interface Candidate {
  settings?: Data;
  spec_version?: number;
  spec?: Data;
  name?: string;
}

/** One model of the org. 3.0's calls (`call`, `record`, `query`, `facts`, `probabilities`, `learn`) answer a Result. */
export class AdaModel {
  constructor(
    readonly ada: Ada,
    readonly name: string,
    /** createModel's answer. */
    readonly created?: Data,
  ) {}

  #path(rest = ""): string {
    return `/v1/models/${q(this.name)}${rest}`;
  }

  async #change(made: Change, options: WaitOptions): Promise<Change> {
    if (made.job && options.wait !== false) made.job = await this.ada.wait(made.job, options);
    return made;
  }

  async #job<R>(rest: string, body: unknown, options: WaitOptions): Promise<Job<R>> {
    const job = await this.ada.write<Job<R>>("POST", this.#path(rest), body ?? {});
    return options.wait === false ? job : this.ada.wait(job, options);
  }

  // the model

  /** The model: its active version and spec, and how many precedents it holds. */
  info(): Promise<{ name: string; id: string; version: number; precedents: number; created_at: string; spec: Data }> {
    return this.ada.call("GET", this.#path());
  }

  delete(): Promise<{ name: string; deleted: boolean }> {
    return this.ada.deleteModel(this.name);
  }

  /** The active version's spec. */
  async spec(): Promise<Data> {
    return (await this.info()).spec;
  }

  /**
   * A new version from a whole spec: active at once when it reads the stored cases as they are; else `job` re-encodes
   * them while the old version serves (waited for unless `wait: false`). A role read another way: `SpecReadingError`.
   */
  async setSpec(spec: Data, options: ChangeOptions = {}): Promise<Change> {
    const body = drop({ spec, note: options.note, backtest: options.backtest });
    return this.#change(await this.ada.write<Change>("PUT", this.#path("/spec"), body, options.idempotencyKey), options);
  }

  /** No changes: every lever as it stands. With changes: a new version with them, as `setSpec`. */
  settings(): Promise<{ version: number; settings: Data }>;
  settings(changes: Data, options?: ChangeOptions): Promise<Change>;
  async settings(changes?: Data, options: ChangeOptions = {}): Promise<Change | { version: number; settings: Data }> {
    if (changes === undefined) return this.ada.call("GET", this.#path("/settings"));
    const body = drop({ changes, note: options.note, backtest: options.backtest });
    return this.#change(await this.ada.write<Change>("PATCH", this.#path("/settings"), body, options.idempotencyKey), options);
  }

  /** Every version: who made it and why, which is active. */
  async versions(): Promise<Data[]> {
    return (await this.ada.call<{ versions: Data[] }>("GET", this.#path("/versions"))).versions;
  }

  /** Make another version active (a rollback): at once, or by a job bringing its store up to date first. */
  async activate(version: number, options: WaitOptions = {}): Promise<Change> {
    return this.#change(await this.ada.write<Change>("POST", this.#path(`/versions/${Math.trunc(version)}/activate`), {}), options);
  }

  // cases

  /**
   * Cases, a thousand a request, each request one transaction: {ids, added, replaced, precedents}. Each request
   * carries an Idempotency-Key (`idempotencyKey`, with the chunk's number after the first), so it is made once.
   */
  async recordMany(
    cases: Iterable<Case>,
    options: { idempotencyKey?: string } = {},
  ): Promise<{ ids: string[]; added: number; replaced: number; precedents: number }> {
    const total = { ids: [] as string[], added: 0, replaced: 0, precedents: 0 };
    let batch: Case[] = [];
    let sent = 0;
    const send = async () => {
      const key = options.idempotencyKey === undefined ? undefined : sent === 0 ? options.idempotencyKey : `${options.idempotencyKey}.${sent}`;
      const got = await this.ada.write<{ ids?: string[]; added?: number; replaced?: number; precedents?: number }>(
        "POST",
        this.#path("/record_many"),
        { cases: batch },
        key,
      );
      total.ids.push(...(got.ids ?? []));
      total.added += got.added ?? 0;
      total.replaced += got.replaced ?? 0;
      total.precedents = got.precedents ?? total.precedents;
      sent += 1;
    };
    for (const c of cases) {
      batch.push(c);
      if (batch.length === RECORD_MANY_MAX) {
        await send();
        batch = [];
      }
    }
    if (batch.length || sent === 0) await send();
    return total;
  }

  /** One output's outcome on a case already recorded (null takes it away). */
  grade(id: string, value: string | null, options: { output?: string } = {}): Promise<Data> {
    return this.ada.write("POST", this.#path("/grade"), { id, value, ...drop({ output: options.output }) });
  }

  /** Forget one case; what was learned from it stays until the next learn. */
  forget(id: string): Promise<Data> {
    return this.ada.write("DELETE", this.#path(`/precedents/${q(id)}`));
  }

  // asking

  /** `Ada.decide` for this model. */
  decide(data: Data, options: DecideOptions = {}): Promise<Decision> {
    return this.ada.decide(this.name, data, options);
  }

  // learning and tuning, as jobs

  /** `learn` as the job it is, with its progress: the weights from the graded precedents, then calibration. */
  learnJob(options: WaitOptions = {}): Promise<Job> {
    return this.#job("/learn", {}, options);
  }

  /** Fit the temperature alone, so the probabilities mean what they say (or decide best, by the costs). */
  calibrate(options: WaitOptions = {}): Promise<Job> {
    return this.#job("/calibrate", {}, options);
  }

  /**
   * Score the active version and up to ten candidates on the model's own held-out precedents (`holdout` {newest: n},
   * 200 by default, or {fraction, seed}), each learned on the rest. The live model is never touched.
   */
  backtest(
    candidates: Candidate[] = [],
    options: WaitOptions & { holdout?: { newest?: number; fraction?: number; seed?: number }; output?: string; clearance?: number } = {},
  ): Promise<Job> {
    const body = drop({ candidates, holdout: options.holdout, output: options.output, clearance: options.clearance });
    return this.#job("/backtest", body, options);
  }

  // in and out

  /**
   * A file of cases into the model, as a job: JSON Lines, CSV (with `mapping`), `ada_sqlite`, or a model's own export
   * (a zip). A path (Node) or the bytes; the format from the extension when not given. The file goes to a one-hour
   * signed upload link, then the import runs; rows the spec refuses are named in the result.
   */
  async importFile(
    source: string | Uint8Array,
    options: WaitOptions & { format?: string; mapping?: Record<string, string | null>; partial?: boolean; learn?: boolean } = {},
  ): Promise<Job> {
    let content: Uint8Array;
    let format = options.format;
    if (typeof source === "string") {
      const dot = source.lastIndexOf(".");
      format ??= dot >= 0 ? FORMATS[source.slice(dot).toLowerCase()] : undefined;
      if (format === undefined) throw new AdaError("E_INVALID", `The format of ${source} is not known by its extension: say it.`);
      content = new Uint8Array(await (await files()).readFile(source));
    } else {
      content = source;
      if (format === undefined) throw new AdaError("E_INVALID", "Say the format of a file given as bytes: jsonl, csv or ada_sqlite.");
    }
    const body = drop({ format, mapping: options.mapping, partial: options.partial ?? false, learn: options.learn ?? true });
    const job = await this.ada.write<Job>("POST", this.#path("/imports"), body);
    if (!job.upload?.url) throw new AdaError("E_IMPORT", "The import answered no upload link.", 0, { job });
    const sent = await this.ada.exchange("PUT", job.upload.url, { "content-type": "application/octet-stream", accept: "application/json" }, content);
    const queued = parsed<Job>(sent.status, sent.body, sent.headers);
    return options.wait === false ? queued : this.ada.wait(queued, options);
  }

  /**
   * Everything of the model, as a job: `jsonl` (a zip of the precedents as stored situations, every spec version and
   * what was learned) or `ada_sqlite`. The done job's `download` is a one-hour link; `to` (Node) also writes the file.
   */
  async export(options: WaitOptions & { format?: "jsonl" | "ada_sqlite"; to?: string } = {}): Promise<Job> {
    const wait = options.to !== undefined ? { ...options, wait: true } : options;
    const job = await this.#job("/export", { format: options.format ?? "jsonl" }, wait);
    if (options.to !== undefined) {
      await (await files()).writeFile(options.to, await this.ada.download(job));
    }
    return job;
  }

  // SDK 3.0's calls, through POST /v1/runs: each answers a Result, as it did

  async call<T = unknown>(fn = "start", inputs: Data = {}, options: CallOptions = {}): Promise<Result<T>> {
    const body: Data = { model: this.name, function: fn, inputs };
    if (options.version !== undefined) body.version = options.version;
    if (options.clearance !== undefined) body.clearance = options.clearance;
    return asResult(await this.ada.call("POST", "/v1/runs", body, READS.includes(fn)));
  }

  resume<T = unknown>(runId: string, answer: unknown): Promise<Result<T>> {
    return this.ada.resume(runId, answer);
  }

  /** One case, with its outcome when known: `data` {id, precedents}. */
  record(data: Data, outcome?: string, more: { outcomes?: Record<string, string>; ts?: number } = {}): Promise<Result<{ id: string; precedents: number }>> {
    return this.call("record", { data, ...drop({ outcome, outcomes: more.outcomes, ts: more.ts }) });
  }

  /** The nearest precedents' vote. */
  query(data: Data, options: CallOptions = {}): Promise<Result<Answer>> {
    const { output, ...rest } = options;
    return this.call("query", { data, ...drop({ output }) }, rest);
  }

  facts(data: Data, options: CallOptions & { top?: number } = {}): Promise<Result<unknown[]>> {
    const { top, output, ...rest } = options;
    return this.call("facts", { data, ...drop({ top, output }) }, rest);
  }

  probabilities(data: Data, options: CallOptions = {}): Promise<Result<Record<string, number>>> {
    const { output, ...rest } = options;
    return this.call("probabilities", { data, ...drop({ output }) }, rest);
  }

  /**
   * The model weighs its roles from its own precedents and calibrates: `data` the roles' weights. A learn that
   * outlasts the call's minute is waited for as the job it is (`learnJob` for the job itself).
   */
  async learn(options: CallOptions & { sample?: number; timeout?: number; onProgress?: Progress } = {}): Promise<Result<any>> {
    const { sample, timeout, onProgress, ...rest } = options;
    const r = await this.call<any>("learn", sample === undefined ? {} : { sample }, rest);
    const data = r.data as { job?: Job } | null;
    if (data && typeof data === "object" && Object.keys(data).length === 1 && data.job && typeof data.job === "object") {
      const job = await this.ada.wait(data.job, drop({ timeout, onProgress }));
      return { ...r, data: job.result };
    }
    return r;
  }
}
