import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { adaApi, ApiError, readResponse } from './client';
import { useMe } from './queries';
import type { CloudUsage, IsoDate, Uuid } from './types';

/**
 * Ada Cloud's API (`glyphh_ada/api` in the server, at https://ada.glyphh.ai), reached through /api/ada/v1 with the
 * platform's own sign-in. Shapes as the server answers them; dates are ISO strings.
 */

/**
 * Whether Ada Cloud is on, as the account API says (`ada_cloud` on /v1/me); undefined until it is read. A refusal is
 * off, so today's pages show it (and asking again on their mount does not hide them meanwhile).
 */
export function useAdaCloud(): boolean | undefined {
  const me = useMe();
  if (me.data) return me.data.ada_cloud === true;
  return me.errorUpdateCount > 0 ? false : undefined;
}

// The spec, as far as the platform reads it; the kernel checks the rest.
export type SpecRole = {
  name: string;
  similarity_weight?: number;
  security_weight?: number;
  key_part?: boolean;
  numeric_config?: { min_value: number; max_value: number; bin_width: number } | null;
  text_encoding?: 'bag_of_words' | null;
  lexicons?: string[];
};
export type SpecSegment = { name: string; roles: SpecRole[]; similarity_weight?: number; security_weight?: number };
export type SpecLayer = { name: string; segments: SpecSegment[]; similarity_weight?: number; security_weight?: number };
export type SpecOutput = { report?: string[]; costs?: Record<string, Record<string, number>>; ask?: number; ask_below?: number; values?: string[] };
export type Spec = {
  name: string;
  layers: SpecLayer[];
  dimension?: number;
  seed?: number;
  output?: SpecOutput;
  outputs?: Record<string, SpecOutput>;
  settings?: Record<string, unknown>;
  [field: string]: unknown;
};

/** One of the org's models, as `GET /v1/models` lists it. */
export type AdaModelRow = { name: string; id: Uuid; version: number; precedents: number; created_at: IsoDate };
/** One model with its active spec. */
export type AdaModel = AdaModelRow & { spec: Spec };

/** One change of spec or settings: where (`settings.k`, `layers[a].segments[s].roles[color]`), from and to (null: not there), and whether it rewrites the stored cases. */
export type SpecChange = { path: string; from: unknown; to: unknown; restates: boolean };
/** What a store had learned, per output (`default` and each named one): roles' weights, words per text role, pairs, the temperature. */
export type LearnedSummary = Record<string, { roles?: Record<string, number>; words?: Record<string, number>; pairs?: unknown[]; tau?: number }>;
/** The newest backtest that scored a version. */
export type VersionScores = {
  job: string;
  at: IsoDate | null;
  output: string | null;
  n?: number;
  accuracy?: number;
  top_accuracy?: number;
  log_loss?: number;
  ask_rate?: number;
  accuracy_answered?: number | null;
  coverage?: number;
  calibration_error?: number;
  cost_mean?: number;
};
/** A version's stored cases: the live store, kept for a rollback (from `drop_after` the next re-encode may drop it), being made, or dropped. */
export type VersionStore = { status: 'active' | 'kept' | 'making' | 'dropped'; drop_after: IsoDate | null };

/** A version: who made it and why, active or not, what changed against the one before, what it learned, its newest backtest, its store. */
export type AdaVersion = {
  version: number;
  note: string;
  made_by: string;
  made_at: IsoDate;
  active: boolean;
  backtest: string | null;
  ready: boolean;
  gone: boolean;
  retired_at: IsoDate | null;
  reencoded: boolean;
  /** Made a store of its own (a re-encode) where the version before read another. */
  new_store: boolean;
  /** Against the version before; null for the first. */
  changes: SpecChange[] | null;
  /** The precedents the model held when it was made; null when made before this was kept. */
  precedents_at: number | null;
  learned: LearnedSummary | null;
  scores: VersionScores | null;
  store: VersionStore;
};
/** One version whole: its spec and every lever its settings stand at. */
export type AdaVersionDetail = AdaVersion & { spec: Spec; settings: Record<string, LeverValue> };
/** What making `version` live would change from `against`. */
export type VersionDiff = { version: number; against: number; changes: SpecChange[] };

export type JobState = 'awaiting' | 'queued' | 'running' | 'done' | 'failed';
export type AdaJob = {
  id: Uuid;
  model: string;
  kind: 'import' | 'export' | 'learn' | 'calibrate' | 'reencode' | 'backtest' | string;
  state: JobState;
  percent: number | null;
  args: Record<string, unknown>;
  result: Record<string, unknown> | null;
  error: { code: string; message: string; [detail: string]: unknown } | null;
  created_at: IsoDate;
  started_at: IsoDate | null;
  finished_at: IsoDate | null;
  made_by: string;
  /** A done export's one-hour link. */
  download?: { url: string; expires_at: number };
};
export const jobEnded = (job: AdaJob | undefined) => job?.state === 'done' || job?.state === 'failed';

/** A spec or settings change, or a rollback: active at once, or once its job (a re-encode or calibration) is done. */
export type VersionChange = { version: number; active: boolean; job: AdaJob | null };

export type LeverValue = number | boolean | string | null;
/** Every lever as it stands on the active version. */
export type Levers = { version: number; settings: Record<string, LeverValue> };

export type Receipt = { id: string; sim: number; outcome: string | null; hash: string; author: string };
/** `POST /v1/decide`: the outcome of least expected cost, its probabilities, whether a person should decide, and the precedents. */
export type Decision = {
  outcome: string | null;
  expected_cost: number | null;
  probabilities: Record<string, number>;
  ask: boolean;
  receipts: Receipt[];
  model: string;
  version: number;
};

/**
 * `GET /v1/usage`: the org's models, the precedents they hold and the requests this month, against the plan's (the
 * same shape as `cloud` on /v1/me and /v1/billing).
 */
export type AdaUsage = CloudUsage;

/**
 * Ada's plan refusals, with what the platform says beside the server's words: 429 E_RATE (more calls a second than the
 * plan allows; again after Retry-After), and 403 E_LIMIT, `requests` (the month's are used, on a plan that is not
 * metered: `upgrade` names the plan that reads more, null for talk to us, `resets_at` when they start again) or
 * `precedents` (a write past the plan's precedents).
 */
export type AdaRefusal =
  | { kind: 'rate'; retryAfter: number | null }
  | { kind: 'requests'; plan: string | null; upgrade: string | null; resetsAt: string | null }
  | { kind: 'precedents'; used: number | null; max: number | null };

const numberOr = (value: unknown) => (typeof value === 'number' ? value : null);
const stringOr = (value: unknown) => (typeof value === 'string' ? value : null);

/** Which plan refusal this is, if it is one: from a call's ApiError, or a failed job's error. */
export function adaRefusal(error: unknown): AdaRefusal | null {
  const detail: Record<string, unknown> | null =
    error instanceof ApiError ? error.detail : typeof error === 'object' && error !== null && 'code' in error ? (error as Record<string, unknown>) : null;
  if (!detail) return null;
  if (detail.code === 'E_RATE') {
    const header = error instanceof ApiError ? error.retryAfter : undefined;
    return { kind: 'rate', retryAfter: header ?? numberOr(detail.retry_after) };
  }
  if (detail.code !== 'E_LIMIT') return null;
  if (detail.reason === 'requests') return { kind: 'requests', plan: stringOr(detail.plan), upgrade: stringOr(detail.upgrade), resetsAt: stringOr(detail.resets_at) };
  if (detail.reason === 'precedents') return { kind: 'precedents', used: numberOr(detail.used), max: numberOr(detail.max) };
  return null;
}

export type CloudKey = { id: Uuid; name: string; clearance: number; created_at: IsoDate; expires_at: IsoDate | null; revoked_at: IsoDate | null };
export type NewCloudKey = CloudKey & { key: string };

export type ImportFormat = 'csv' | 'jsonl';
export type ImportStarted = AdaJob & { upload: { url: string; expires_at: number } };
/** A done import's result. */
export type Imported = { rows: number; recorded: number; added: number; replaced: number; refused: number; refusals: Array<{ row: number; path: string; message: string }> };

export type Candidate = { settings?: Record<string, LeverValue>; spec_version?: number; name?: string };
export type Scores = {
  candidate: Candidate;
  n?: number;
  accuracy?: number;
  top_accuracy?: number;
  log_loss?: number;
  ask_rate?: number;
  accuracy_answered?: number | null;
  coverage?: number;
  calibration_error?: number;
  cost?: number;
  cost_mean?: number;
  change?: Record<string, number>;
  learn?: true | string;
  error?: { code: string; message: string };
};
/** A done backtest's result. */
export type BacktestResult = { version: number; trained: number; held_out: number; output: string; active: Scores; candidates: Scores[] };

/** One UTC day of a model: its reads by kind, its decides answered (every output’s) and how many of them asked a person. */
export type ModelDay = { day: string; reads: { decide: number; query: number; probabilities: number; facts: number }; decided: number; asked: number };
/** One output’s decides in the window (output null: the default): how many, how many asked a person, how sure, and a day each. */
export type OutputAnswers = { output: string | null; decided: number; asked: number; sure: number[]; days: Array<{ decided: number; asked: number }> };
/** `GET /v1/models/{name}/stats`: the model's dashboard, from its store and its days counted as they happen. */
export type ModelStats = {
  name: string;
  version: number;
  precedents: number;
  created_at: IsoDate;
  active: { version: number; note: string; made_by: string; made_at: IsoDate };
  /** The org's precedents, all models together, against the plan's (null: no limit). */
  plan: { plan: string; precedents: { used: number; max: number | null } };
  /** Precedents by output (null: the default) and outcome (null: ungraded), the most common first. */
  outcomes: Array<{ output: string | null; value: string | null; n: number }>;
  /** Each output’s values past the most common, together: how many values, how many precedents. */
  others?: Array<{ output: string | null; values: number; n: number }>;
  /** Outcomes and growth estimated from a sample: the model is too big to count on every look. */
  estimated?: boolean;
  /** Each output’s decides apart, the default first. */
  answers?: OutputAnswers[];
  /** Precedents by the day of each case (its time, or when it was recorded). */
  growth: Array<{ day: string; n: number }>;
  jobs: AdaJob[];
  days: ModelDay[];
  /** The window's decides by how sure they were (the decided outcome's probability), in tenths: 0–0.1 up to 0.9–1. */
  sure: number[];
};
/** One precedent in the 3D view: its glyph's bits packed (base64), null when it has nothing in the layer shown. */
export type MapPoint = { id: string; outcome: string | null; outcomes: Record<string, string>; bits: string | null };
/** `GET /v1/models/{name}/map`: a sample of the model's precedents and each one's nearest in it, [i, j, similarity]. */
export type ModelMap = { version: number; dim: number; layers: string[]; layer: string | null; total: number; points: MapPoint[]; edges: Array<[number, number, number]> };
/** `GET /v1/models/{name}/precedents/{id}`: one case, as stored, cut to the caller's clearance. */
export type Precedent = { id: string; situation: Record<string, unknown>; outcome: string | null; outcomes: Record<string, string>; author: string; ts: number };

const jobPoll = 1000;

export const adaKeys = {
  all: ['ada'] as const,
  models: ['ada', 'models'] as const,
  model: (name: string) => ['ada', 'models', name] as const,
  usage: ['ada', 'usage'] as const,
  keys: ['ada', 'keys'] as const,
  job: (id: string) => ['ada', 'jobs', id] as const,
};

const path = (name: string) => `/models/${encodeURIComponent(name)}`;

// Reads

export const useAdaModels = () =>
  useQuery({ queryKey: adaKeys.models, queryFn: async () => (await adaApi.get<{ models: AdaModelRow[] }>('/models')).models });
export const useAdaModel = (name: string) => useQuery({ queryKey: [...adaKeys.model(name), 'view'], queryFn: () => adaApi.get<AdaModel>(path(name)) });
export const useAdaVersions = (name: string) =>
  useQuery({ queryKey: [...adaKeys.model(name), 'versions'], queryFn: async () => (await adaApi.get<{ versions: AdaVersion[] }>(`${path(name)}/versions`)).versions });
export const useAdaVersion = (name: string, version: number | null) =>
  useQuery({
    queryKey: [...adaKeys.model(name), 'versions', version ?? 0],
    enabled: version !== null,
    queryFn: () => adaApi.get<AdaVersionDetail>(`${path(name)}/versions/${version}`),
  });
/** What making `version` live would change from the live one. */
export const useVersionDiff = (name: string, version: number | null) =>
  useQuery({
    queryKey: [...adaKeys.model(name), 'versions', version ?? 0, 'diff'],
    enabled: version !== null,
    queryFn: () => adaApi.get<VersionDiff>(`${path(name)}/versions/${version}/diff`),
  });
export const useAdaLevers = (name: string) => useQuery({ queryKey: [...adaKeys.model(name), 'settings'], queryFn: () => adaApi.get<Levers>(`${path(name)}/settings`) });
export const useAdaStats = (name: string) => useQuery({ queryKey: [...adaKeys.model(name), 'stats'], queryFn: () => adaApi.get<ModelStats>(`${path(name)}/stats`) });
export const useAdaMap = (name: string, layer: string | null) =>
  useQuery({
    queryKey: [...adaKeys.model(name), 'map', layer ?? ''],
    queryFn: () => adaApi.get<ModelMap>(`${path(name)}/map${layer ? `?layer=${encodeURIComponent(layer)}` : ''}`),
    staleTime: 60_000,
  });
export const useAdaPrecedent = (name: string, id: string | null) =>
  useQuery({
    queryKey: [...adaKeys.model(name), 'precedent', id ?? ''],
    enabled: Boolean(id),
    queryFn: () => adaApi.get<Precedent>(`${path(name)}/precedents/${encodeURIComponent(id ?? '')}`),
  });
export const useAdaUsage = () => useQuery({ queryKey: adaKeys.usage, queryFn: () => adaApi.get<AdaUsage>('/usage') });
export const useCloudKeys = () => useQuery({ queryKey: adaKeys.keys, queryFn: () => adaApi.get<CloudKey[]>('/keys') });

/** A job, read again every second until it is done or failed. */
export const useAdaJob = (id: string | null) =>
  useQuery({
    queryKey: adaKeys.job(id ?? ''),
    enabled: Boolean(id),
    queryFn: () => adaApi.get<AdaJob>(`/jobs/${id}`),
    refetchInterval: (query) => (jobEnded(query.state.data) ? false : jobPoll),
    staleTime: 0,
  });

// Writes: each refreshes what it changed.

function useAdaWrite<TArgs, TResult>(fn: (args: TArgs) => Promise<TResult>, refresh: (args: TArgs) => ReadonlyArray<readonly string[]>) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: (_, args) => Promise.all(refresh(args).map((queryKey) => client.invalidateQueries({ queryKey }))),
  });
}

/** Everything about a model: its view, versions and settings, the list and the usage. */
export const modelReads = (name: string) => [adaKeys.model(name), adaKeys.models, adaKeys.usage];

export const useCreateAdaModel = () =>
  useAdaWrite((body: { name: string; spec: Spec }) => adaApi.post<AdaModel>('/models', body), () => [adaKeys.models, adaKeys.usage]);
export const useDeleteAdaModel = () =>
  useAdaWrite((name: string) => adaApi.delete(`${path(name)}?confirm=${encodeURIComponent(name)}`), () => [adaKeys.models, adaKeys.usage]);
export const usePutSpec = (name: string) =>
  useAdaWrite((body: { spec: Spec; note?: string }) => adaApi.put<VersionChange>(`${path(name)}/spec`, body), () => modelReads(name));
export const usePatchSettings = (name: string) =>
  useAdaWrite(
    (body: { changes: Record<string, LeverValue>; note?: string; backtest?: string }) => adaApi.patch<VersionChange>(`${path(name)}/settings`, body),
    () => modelReads(name),
  );
export const useActivate = (name: string) =>
  useAdaWrite((version: number) => adaApi.post<VersionChange>(`${path(name)}/versions/${version}/activate`), () => modelReads(name));
/** A version's note (its release notes) written again. */
export const useVersionNote = (name: string) =>
  useAdaWrite(
    (body: { version: number; note: string }) => adaApi.patch<{ version: number; note: string }>(`${path(name)}/versions/${body.version}`, { note: body.note }),
    () => [[...adaKeys.model(name), 'versions']],
  );
/** A decide is a read: the model's dashboard and the month's usage count it. */
export const useDecide = () =>
  useAdaWrite(
    (body: { model: string; data: Record<string, unknown>; output?: string }) => adaApi.post<Decision>('/decide', body),
    (body) => [[...adaKeys.model(body.model), 'stats'], adaKeys.usage],
  );
export const useStartImport = (name: string) =>
  useMutation({
    mutationFn: (body: { format: ImportFormat; mapping?: Record<string, string | null> }) => adaApi.post<ImportStarted>(`${path(name)}/imports`, body),
  });
export const useStartBacktest = (name: string) =>
  useMutation({
    mutationFn: (body: { candidates: Candidate[]; holdout: { newest: number }; output?: string }) => adaApi.post<AdaJob>(`${path(name)}/backtest`, body),
  });
export const useStartExport = (name: string) =>
  useMutation({ mutationFn: (format: 'jsonl' | 'ada_sqlite') => adaApi.post<AdaJob>(`${path(name)}/export`, { format }) });

export const useCreateCloudKey = () =>
  useAdaWrite(
    (body: { name: string; expires_in_days: number | null; clearance: number }) =>
      adaApi.post<NewCloudKey>('/keys', body.expires_in_days === null ? { name: body.name, clearance: body.clearance } : body),
    () => [adaKeys.keys],
  );
export const useRevokeCloudKey = () => useAdaWrite((id: string) => adaApi.delete<CloudKey>(`/keys/${id}`), () => [adaKeys.keys]);

/**
 * An import's file, to its upload link through the platform (`PUT /api/ada/v1/uploads/<link>`): the link the server
 * answers is at Ada's host; its last part is the link itself.
 */
export async function uploadFile(uploadUrl: string, file: Blob, contentType: string): Promise<AdaJob> {
  const link = uploadUrl.slice(uploadUrl.lastIndexOf('/') + 1);
  const response = await fetch(`/api/ada/v1/uploads/${link}`, {
    method: 'PUT',
    credentials: 'same-origin',
    headers: { accept: 'application/json', 'content-type': contentType },
    body: file,
  });
  return readResponse<AdaJob>(response);
}
